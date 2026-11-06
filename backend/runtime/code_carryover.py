"""Reuse exact earlier native code or selected historic files as attributed input to fresh development, without transferring authority or approval."""

import base64
import hashlib
import json
import re
from dataclasses import dataclass

from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.contracts import InputTooLarge, RunConflict, text
from backend.runtime.task_profiles import DEVELOPMENT_TASK_TYPES


def _encoded(value):
    """Render exact complete input deterministically so owner observations and retries identify the same material."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class PriorCodeTarget:
    """Owner-observed original candidate and complete input fingerprint, never a moving path or branch."""

    attempt_id: str
    snapshot_sha256: str

    def __post_init__(self):
        """Reject ambiguous identities before admission or receipt lookup."""
        text(self.attempt_id, "Prior code attempt", 128)
        if not isinstance(self.snapshot_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.snapshot_sha256
        ):
            raise ValueError("Prior code requires an observed SHA-256 fingerprint")


class CodeCarryovers:
    """Read retained native material or selected older files and freeze owner-chosen data using the existing admission receipt transaction."""

    def __init__(self, runs):
        """Reuse the run store; construction starts no process or additional controller."""
        self.runs = runs

    def _packet(self, conn, project_id, task_id, attempt_id):
        """Require an actual closed native author and its saved complete input; do not reconstruct unknown history."""
        candidate = CodeCandidates._row(conn, project_id, attempt_id)
        if candidate["task_id"] != task_id or candidate["state"] != "ready":
            raise RunConflict("Prior candidate is not ready in this task")
        author = conn.execute(
            """SELECT a.thread_id,a.turn_id,a.status AS attempt_status,r.actor_id,r.execution_kind,
            r.status AS run_status FROM runtime_attempts a JOIN runtime_runs r ON r.id=a.run_id
            WHERE a.id=? AND a.run_id=? AND r.project_id=? AND r.task_id=?""",
            (attempt_id, candidate["run_id"], project_id, task_id),
        ).fetchone()
        if (
            author is None
            or author["execution_kind"] != "development"
            or author["attempt_status"] in ("running", "reconciling")
            or not author["thread_id"]
            or not author["turn_id"]
        ):
            raise RunConflict("Prior code requires a closed original native author")
        self.runs._closed_peer_proof(conn, attempt_id)
        if (
            not conn.execute(
                "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=? AND protocol_version=1",
                (attempt_id,),
            ).fetchone()
            or not conn.execute(
                "SELECT 1 FROM runtime_peers WHERE attempt_id=? AND kind='native' AND state='closed' AND bound_at IS NOT NULL",
                (attempt_id,),
            ).fetchone()
        ):
            raise RunConflict("Prior code requires a witnessed closed native peer")
        original = conn.execute(
            "SELECT input_text,input_sha256,instructions_sha256 FROM runtime_input_snapshots WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        if (
            original is None
            or hashlib.sha256(original["input_text"].encode()).hexdigest()
            != original["input_sha256"]
        ):
            raise RunConflict(
                "Prior code original input is unavailable or inconsistent"
            )
        diff = bytes(candidate["diff"])
        if hashlib.sha256(diff).hexdigest() != candidate["diff_sha256"]:
            raise RunConflict("Prior candidate diff differs from its captured bytes")
        snapshot = {
            "schema_version": 1,
            "origin": {
                "kind": "retained_native_candidate",
                "project_id": project_id,
                "task_id": task_id,
                "run_id": candidate["run_id"],
                "attempt_id": attempt_id,
                "actor_id": author["actor_id"],
                "thread_id": author["thread_id"],
                "turn_id": author["turn_id"],
                "context_version": candidate["context_version"],
                "repository_id": candidate["repository_id"],
            },
            "candidate": {
                key: candidate[key]
                for key in ("base_sha", "head_sha", "tree_sha", "diff_sha256")
            },
            "source": json.loads(candidate["source_json"]),
            "original_input": json.loads(original["input_text"]),
            "original_input_sha256": original["input_sha256"],
            "original_instructions_sha256": original["instructions_sha256"],
            "diff_base64": base64.b64encode(diff).decode("ascii"),
            "diff_bytes": len(diff),
        }
        encoded = _encoded(snapshot)
        if len(encoded.encode()) > 600000:
            raise InputTooLarge(
                "Complete prior-code packet exceeds its 600000-byte input budget; no changes were omitted"
            )
        return {
            "snapshot_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
            "snapshot": snapshot,
            "authority": "data_only",
            "acceptance": "not_granted",
            "publication": "not_granted",
            "explanation": "These are earlier changes and the exact input their author saw. They may use obsolete requirements or another Git base. A fresh author must inspect and adapt them; checks, independent review and owner acceptance must be performed again.",
        }

    def preview(self, project_id, task_id, attempt_id):
        """Expose the exact retained candidate data without resuming it, editing files or accepting work."""
        with self.runs._transaction() as conn:
            self.runs._existing_task(conn, project_id, task_id)
            return self._packet(conn, project_id, task_id, attempt_id)

    def capture(self, conn, spec, binding, target):
        """Bind an exact earlier-code or selected-file observation and the same registered source to fresh development."""
        from backend.runtime.file_imports import FileImports, PriorFilesTarget

        if (
            not isinstance(target, (PriorCodeTarget, PriorFilesTarget))
            or binding is None
        ):
            raise RunConflict(
                "Prior code requires a typed owner observation and registered repository"
            )
        task = conn.execute(
            "SELECT type FROM tasks WHERE project_id=? AND id=?",
            (spec.project_id, spec.task_id),
        ).fetchone()
        if task is None or task["type"] not in DEVELOPMENT_TASK_TYPES:
            raise RunConflict("Prior code is input only for a fresh development task")
        packet = (
            FileImports(self.runs).packet(
                conn,
                spec.project_id,
                spec.task_id,
                binding,
                target.source_kind,
                target.source_id,
                target.paths,
            )
            if isinstance(target, PriorFilesTarget)
            else self._packet(conn, spec.project_id, spec.task_id, target.attempt_id)
        )
        if packet["snapshot_sha256"] != target.snapshot_sha256:
            raise RunConflict(
                "Prior-code snapshot changed; inspect the original material again"
            )
        source = packet["snapshot"]["source"]
        if any(
            source[key] != getattr(binding, key)
            for key in (
                "repository_id",
                "registration_path",
                "workspace",
                "device",
                "inode",
            )
        ):
            raise RunConflict(
                "Prior code belongs to another registered repository or workspace"
            )
        return packet

    @staticmethod
    def input(conn, row):
        """Read the original atomic admission receipt, independent of later source state and candidate files."""
        receipt = conn.execute(
            "SELECT result_json FROM runtime_commands WHERE project_id=? AND task_id=? AND operation_key=?",
            (row["project_id"], row["task_id"], row["operation_key"]),
        ).fetchone()
        if receipt is None:
            return None
        result = json.loads(receipt["result_json"])
        packet = result.get("prior_code")
        if packet is not None and (
            result.get("run_id") != row["id"]
            or hashlib.sha256(_encoded(packet["snapshot"]).encode()).hexdigest()
            != packet["snapshot_sha256"]
        ):
            raise RunConflict("Saved prior-code receipt is inconsistent")
        return packet
