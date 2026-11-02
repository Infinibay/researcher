"""Reserve exact candidate checks and persist original-owned observations without replay or acceptance authority."""

import json
import re
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.check_contracts import CandidateSubject, CheckSpec
from backend.runtime.check_workspace import PreparedCheckWorkspace
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, text
from backend.runtime.development_state import DevelopmentWorkspaces
from backend.runtime.development_workspace import PreparedDevelopmentWorkspace
from backend.runtime.git_capsule import PrivateAllocation


class CodeChecks:
    """Keep reservations, physical view identity and result events in the original run store's transactions."""

    def __init__(self, runs):
        """Retain existing authority/clock/events; this store never launches a process or accepts a task."""
        self.runs = runs
        self.candidates = CodeCandidates(runs)

    @staticmethod
    def _row(conn, project_id, check_id):
        """Read one check only inside its actual project, including interrupted historical records."""
        row = conn.execute(
            "SELECT * FROM runtime_code_checks WHERE project_id=? AND id=?",
            (project_id, check_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Code check not found")
        return dict(row)

    @staticmethod
    def _origin(row, lease):
        """Prevent another original owner/fence/context from adopting the check's observations."""
        if any(
            row[name] != getattr(lease, name)
            for name in (
                "attempt_id",
                "run_id",
                "project_id",
                "task_id",
                "context_version",
                "fence",
                "owner_id",
            )
        ):
            raise RunConflict("Code check belongs to another original owner")

    def _current(self, conn, lease):
        """Require live development authority and the unchanged ready candidate that this attempt captured."""
        self.candidates._current(conn, lease)
        candidate = self.candidates._row(conn, lease.project_id, lease.attempt_id)
        self.candidates._origin(candidate, lease)
        if candidate["state"] != "ready":
            raise RunConflict("Checks require a ready exact candidate")
        return candidate, CandidateSubject.from_row(candidate)

    def plan(self, lease, operation_key, spec):
        """Reserve one recipe/path before effects; a repeated key returns data without authorizing another execution."""
        command_key(operation_key)
        if not isinstance(spec, CheckSpec):
            raise TypeError("Host-selected CheckSpec required")
        with self.runs._transaction(write=True) as conn:
            _candidate, subject = self._current(conn, lease)
            old = conn.execute(
                "SELECT id FROM runtime_code_checks WHERE run_id=? AND operation_key=?",
                (lease.run_id, operation_key),
            ).fetchone()
            if old:
                row = self._row(conn, lease.project_id, old["id"])
                self._origin(row, lease)
                if (
                    json.loads(row["subject_json"]) != asdict(subject)
                    or row["spec_sha256"] != spec.sha256
                ):
                    raise RunConflict(
                        "Check operation already names another recipe or candidate"
                    )
                return row, False
            preparation = DevelopmentWorkspaces._row(
                conn, lease.project_id, lease.attempt_id
            )
            check_id = str(uuid4())
            allocation = Path(preparation["allocation"]) / "checks" / check_id
            now = self.runs.clock()
            conn.execute(
                """INSERT INTO runtime_code_checks(id,attempt_id,run_id,project_id,task_id,context_version,fence,owner_id,
            operation_key,subject_json,spec_json,spec_sha256,allocation,state,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'preparing',?,?)""",
                (
                    check_id,
                    lease.attempt_id,
                    lease.run_id,
                    lease.project_id,
                    lease.task_id,
                    lease.context_version,
                    lease.fence,
                    lease.owner_id,
                    operation_key,
                    json.dumps(asdict(subject), sort_keys=True),
                    json.dumps(asdict(spec), sort_keys=True),
                    spec.sha256,
                    str(allocation),
                    now,
                    now,
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_check.reserved",
                {
                    "run_id": lease.run_id,
                    "check_id": check_id,
                    "subject_sha256": subject.sha256,
                    "spec_sha256": spec.sha256,
                },
            )
            return self._row(conn, lease.project_id, check_id), True

    @staticmethod
    def workspace(row):
        """Reconstruct prepared data for a host caller; admission separately revalidates live authority and physical identity."""
        if row["workspace"] is None:
            raise RunConflict("Check copy is not prepared")
        subject = CandidateSubject(**json.loads(row["subject_json"]))
        return PreparedCheckWorkspace(
            PreparedDevelopmentWorkspace(
                subject.repository_id,
                row["workspace"],
                row["device"],
                row["inode"],
                subject.head_sha,
                subject.tree_sha,
            ),
            PrivateAllocation(
                row["metadata"], row["metadata_device"], row["metadata_inode"]
            ),
        )

    def prepared(self, lease, check_id, prepared):
        """Record only the exact private child and protected metadata of this reserved candidate head/tree."""
        if not isinstance(prepared, PreparedCheckWorkspace):
            raise TypeError("Prepared check copy required")
        with self.runs._transaction(write=True) as conn:
            _candidate, subject = self._current(conn, lease)
            row = self._row(conn, lease.project_id, check_id)
            self._origin(row, lease)
            copy = PrivateAllocation.capture(prepared.view.workspace)
            metadata = PrivateAllocation.capture(prepared.metadata.path)
            if (
                json.loads(row["subject_json"]) != asdict(subject)
                or Path(prepared.view.workspace)
                != Path(row["allocation"]) / "repository"
                or Path(prepared.metadata.path)
                != Path(row["allocation"]) / "validation-git"
                or (prepared.view.base_sha, prepared.view.base_tree_sha)
                != (subject.head_sha, subject.tree_sha)
                or (copy.device, copy.inode)
                != (prepared.view.device, prepared.view.inode)
                or metadata != prepared.metadata
            ):
                raise RunConflict(
                    "Check copy differs from its reserved exact candidate"
                )
            values = (
                prepared.view.workspace,
                copy.device,
                copy.inode,
                metadata.path,
                metadata.device,
                metadata.inode,
            )
            if (
                row["state"] == "ready"
                and tuple(
                    row[k]
                    for k in (
                        "workspace",
                        "device",
                        "inode",
                        "metadata",
                        "metadata_device",
                        "metadata_inode",
                    )
                )
                == values
            ):
                return row
            if row["state"] != "preparing":
                raise RunConflict(
                    "Check preparation requires original recovery, not replay"
                )
            conn.execute(
                "UPDATE runtime_code_checks SET state='ready',workspace=?,device=?,inode=?,metadata=?,metadata_device=?,metadata_inode=?,updated_at=? WHERE id=?",
                (*values, self.runs.clock(), check_id),
            )
            return self._row(conn, lease.project_id, check_id)

    def bind_peer(self, lease, check_id, peer_id):
        """Bind one still-prepared original command peer before its gate can run the recipe."""
        with self.runs._transaction(write=True) as conn:
            self._current(conn, lease)
            row = self._row(conn, lease.project_id, check_id)
            self._origin(row, lease)
            peer = conn.execute(
                "SELECT * FROM runtime_peers WHERE id=?", (peer_id,)
            ).fetchone()
            if (
                row["state"] != "ready"
                or peer is None
                or (peer["attempt_id"], peer["fence"], peer["kind"], peer["state"])
                != (lease.attempt_id, lease.fence, "command", "prepared")
            ):
                raise RunConflict("Check requires its original prepared command peer")
            conn.execute(
                "UPDATE runtime_code_checks SET state='running',peer_id=?,updated_at=? WHERE id=?",
                (peer_id, self.runs.clock(), check_id),
            )
            return self._row(conn, lease.project_id, check_id)

    def complete(
        self,
        lease,
        check_id,
        observed,
        *,
        operation_id,
        stdout,
        stderr,
        collector_issue=None,
    ):
        """Classify/persist actual terminal observations and the durable event together under current candidate authority."""
        # Minimal broker/recovery bootstrap uses stdlib only; load the report
        # parser solely in the host path that actually completes a check.
        from backend.runtime.check_results import evaluate_check

        if not isinstance(operation_id, str) or not re.fullmatch(
            "[0-9a-f]{64}", operation_id
        ):
            raise RunConflict("Original check operation identity required")
        if collector_issue is not None:
            text(collector_issue, "Check collector issue", 128)
        with self.runs._transaction(write=True) as conn:
            _candidate, subject = self._current(conn, lease)
            row = self._row(conn, lease.project_id, check_id)
            self._origin(row, lease)
            spec_data = json.loads(row["spec_json"])
            spec_data["argv"] = tuple(spec_data["argv"])
            spec = CheckSpec(**spec_data)
            if any(
                not isinstance(data, bytes) or len(data) > spec.output_bytes
                for data in (stdout, stderr)
            ):
                raise RunConflict("Check output exceeds its explicit evidence budget")
            peer = conn.execute(
                "SELECT * FROM runtime_peers WHERE id=?", (row["peer_id"],)
            ).fetchone()
            if (
                not observed.execution_closed
                or peer is None
                or peer["state"] != "closed"
                or peer["bound_at"] is None
            ):
                raise RunConflict("Check physical closure is unconfirmed")
            outcome = evaluate_check(subject, spec, observed)
            result = json.dumps(asdict(outcome), sort_keys=True)
            values = (
                operation_id,
                result,
                stdout,
                stderr,
                observed.junit_xml,
                collector_issue,
            )
            if (
                row["state"] == "finished"
                and tuple(
                    row[k]
                    for k in (
                        "operation_id",
                        "result_json",
                        "stdout",
                        "stderr",
                        "junit_xml",
                        "issue",
                    )
                )
                == values
            ):
                return row
            if row["state"] != "running":
                raise RunConflict("Check result requires original running reservation")
            conn.execute(
                "UPDATE runtime_code_checks SET state='finished',operation_id=?,result_json=?,stdout=?,stderr=?,junit_xml=?,issue=?,updated_at=? WHERE id=?",
                (*values, self.runs.clock(), check_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_check.finished",
                {
                    "run_id": lease.run_id,
                    "check_id": check_id,
                    "status": outcome.status,
                    "reason": outcome.reason,
                    "subject_sha256": outcome.subject.sha256,
                    "spec_sha256": outcome.spec_sha256,
                },
            )
            return self._row(conn, lease.project_id, check_id)

    def observe_failure(self, lease, check_id, issue):
        """Retain the original owner's interrupted record even after context/lease authority ends."""
        text(issue, "Check issue", 4096)
        with self.runs._transaction(write=True) as conn:
            row = self._row(conn, lease.project_id, check_id)
            self._origin(row, lease)
            if row["state"] == "finished":
                return row
            conn.execute(
                "UPDATE runtime_code_checks SET state='reconciling',issue=?,updated_at=? WHERE id=?",
                (issue, self.runs.clock(), check_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_check.interrupted",
                {"run_id": lease.run_id, "check_id": check_id, "issue": issue},
            )
            return self._row(conn, lease.project_id, check_id)

    def inspect(self, project_id, check_id):
        """Return original check data without granting execution, acceptance or retry permission."""
        with self.runs._transaction() as conn:
            return self._row(conn, project_id, check_id)
