"""Persist exact private code candidates under their original fenced attempt and context.

Only host capture results and closed-operation observations enter this store.
A ready row is evidence for later checks/review, never task acceptance or publish
permission. Interrupted allocations survive and cannot be automatically replayed.
"""

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from backend.runtime.code_candidate import CapturedCodeCandidate
from backend.runtime.contracts import RunConflict, RunNotFound, text
from backend.runtime.development_state import DevelopmentWorkspaces
from backend.runtime.development_workspace import _SHA, MAX_OUTPUT_BYTES
from backend.runtime.git_capsule import PrivateAllocation

_HEX = re.compile(r"[0-9a-f]{64}\Z")


class CodeCandidates:
    """Own durable candidate reservation, exact completion and historical inspection without granting process authority."""

    def __init__(self, runs):
        """Use the existing run store's transactions, clock, original authority and durable events."""
        self.runs = runs

    @staticmethod
    def _row(conn, project_id, attempt_id):
        """Read one original attempt's candidate only in its actual project scope."""
        row = conn.execute(
            "SELECT * FROM runtime_code_candidates WHERE project_id=? AND attempt_id=?",
            (project_id, attempt_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Code candidate not found")
        return dict(row)

    @staticmethod
    def _origin(row, lease):
        """Reject observations from another original task, version, fence or owner, even after authority ended."""
        if any(
            row[name] != getattr(lease, name)
            for name in (
                "run_id",
                "attempt_id",
                "project_id",
                "task_id",
                "context_version",
                "fence",
                "owner_id",
            )
        ):
            raise RunConflict("Code candidate belongs to another original owner")

    def _current(self, conn, lease):
        """Validate the live development lease, ready private view and unchanged original registration together."""
        run = self.runs._authority(conn, lease)
        if run["execution_kind"] != "development":
            raise RunConflict("Code capture requires a development attempt")
        view = DevelopmentWorkspaces.read_view(conn, lease.project_id, lease.attempt_id)
        self.runs._bound_workspace(conn, run, view.workspace)
        return view

    def plan(self, lease):
        """Reserve the sole host-selected capture path before filesystem work; repeats do not permit recapture."""
        with self.runs._transaction(write=True) as conn:
            view = self._current(conn, lease)
            existing = conn.execute(
                "SELECT 1 FROM runtime_code_candidates WHERE attempt_id=?",
                (lease.attempt_id,),
            ).fetchone()
            if existing:
                row = self._row(conn, lease.project_id, lease.attempt_id)
                self._origin(row, lease)
                return row, False
            prepared = DevelopmentWorkspaces._row(
                conn, lease.project_id, lease.attempt_id
            )
            allocation = Path(prepared["allocation"]) / "candidate"
            now = self.runs.clock()
            conn.execute(
                """INSERT INTO runtime_code_candidates
            (attempt_id,run_id,project_id,task_id,repository_id,context_version,fence,owner_id,source_json,prepared_json,base_sha,base_tree_sha,allocation,state,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'capturing',?,?)""",
                (
                    lease.attempt_id,
                    lease.run_id,
                    lease.project_id,
                    lease.task_id,
                    view.source.repository_id,
                    lease.context_version,
                    lease.fence,
                    lease.owner_id,
                    json.dumps(asdict(view.source), sort_keys=True),
                    json.dumps(asdict(view), sort_keys=True),
                    view.base_sha,
                    view.base_tree_sha,
                    str(allocation),
                    now,
                    now,
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_candidate.reserved",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "base_sha": view.base_sha,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id), True

    @staticmethod
    def _proof(proof):
        """Accept only bounded host observations that every listed original-domain operation is physically closed."""
        if (
            not isinstance(proof, dict)
            or set(proof) != {"grant_id", "operations"}
            or not isinstance(proof["grant_id"], str)
            or not _HEX.fullmatch(proof["grant_id"])
        ):
            raise RunConflict("Original writer closure proof is incomplete")
        operations = proof["operations"]
        if not isinstance(operations, list) or not 1 <= len(operations) <= 512:
            raise RunConflict("Original writer closure proof is incomplete")
        ids = []
        for operation in operations:
            if (
                not isinstance(operation, dict)
                or set(operation) != {"operation_id", "execution_closed"}
                or operation["execution_closed"] is not True
                or not isinstance(operation["operation_id"], str)
                or not _HEX.fullmatch(operation["operation_id"])
            ):
                raise RunConflict("Original writer closure proof is incomplete")
            ids.append(operation["operation_id"])
        if len(set(ids)) != len(ids):
            raise RunConflict("Writer closure proof repeats an operation")
        return json.dumps(
            {
                "grant_id": proof["grant_id"],
                "operations": sorted(operations, key=lambda item: item["operation_id"]),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def complete(self, lease, captured, writer_proof):
        """Commit exact closed capture evidence only while its original development/context authority remains current."""
        if not isinstance(captured, CapturedCodeCandidate):
            raise TypeError("A host-captured code candidate is required")
        proof = self._proof(writer_proof)
        if (
            not _SHA.fullmatch(captured.head_sha)
            or not _SHA.fullmatch(captured.tree_sha)
            or not isinstance(captured.diff, bytes)
            or len(captured.diff) > MAX_OUTPUT_BYTES
            or captured.diff_sha256 != hashlib.sha256(captured.diff).hexdigest()
        ):
            raise RunConflict(
                "Candidate content identities are incomplete or inconsistent"
            )
        with self.runs._transaction(write=True) as conn:
            view = self._current(conn, lease)
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            try:
                physical = PrivateAllocation.capture(captured.workspace)
            except (ValueError, OSError) as exc:
                raise RunConflict(
                    "Candidate directory is not its private allocation"
                ) from exc
            if (
                captured.repository_id != row["repository_id"]
                or captured.base_sha != row["base_sha"]
                or json.loads(row["prepared_json"]) != asdict(view)
                or Path(captured.workspace) != Path(row["allocation"]) / "repository"
                or (captured.device, captured.inode)
                != (physical.device, physical.inode)
            ):
                raise RunConflict(
                    "Candidate differs from its original repository, base or private allocation"
                )
            if conn.execute(
                "SELECT 1 FROM runtime_peers WHERE attempt_id=? AND state='bound' LIMIT 1",
                (lease.attempt_id,),
            ).fetchone():
                raise RunConflict("Candidate writers still have bound peers")
            if conn.execute(
                "SELECT 1 FROM runtime_jobs WHERE attempt_id=? AND status!='exited' LIMIT 1",
                (lease.attempt_id,),
            ).fetchone():
                raise RunConflict(
                    "Candidate command effects still require reconciliation"
                )
            values = {
                "workspace": captured.workspace,
                "device": captured.device,
                "inode": captured.inode,
                "head_sha": captured.head_sha,
                "tree_sha": captured.tree_sha,
                "diff": captured.diff,
                "diff_sha256": captured.diff_sha256,
                "writer_proof_json": proof,
            }
            if row["state"] == "ready" and all(
                row[key] == value for key, value in values.items()
            ):
                return row
            if row["state"] != "capturing":
                raise RunConflict(
                    "Original candidate requires inspection, not capture replay"
                )
            conn.execute(
                """UPDATE runtime_code_candidates SET state='ready',workspace=?,device=?,inode=?,head_sha=?,tree_sha=?,diff=?,diff_sha256=?,writer_proof_json=?,updated_at=? WHERE attempt_id=?""",
                (*values.values(), self.runs.clock(), lease.attempt_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_candidate.ready",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "repository_id": captured.repository_id,
                    "base_sha": captured.base_sha,
                    "head_sha": captured.head_sha,
                    "tree_sha": captured.tree_sha,
                    "diff_sha256": captured.diff_sha256,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def observe_failure(self, lease, issue):
        """Retain an original owner's bounded interruption observation without restoring current authority."""
        text(issue, "Candidate capture issue", 4096)
        with self.runs._transaction(write=True) as conn:
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            if row["state"] != "capturing":
                return row
            conn.execute(
                "UPDATE runtime_code_candidates SET state='reconciling',issue=?,updated_at=? WHERE attempt_id=?",
                (issue, self.runs.clock(), lease.attempt_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_candidate.interrupted",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "issue": issue,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def inspect(self, project_id, run_id):
        """Inspect the current attempt's retained candidate without opening a process or granting any permission."""
        with self.runs._transaction() as conn:
            row = self.runs._row(conn, project_id, run_id)
            return self._row(conn, project_id, row["current_attempt_id"])
