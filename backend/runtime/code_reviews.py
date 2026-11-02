"""Freeze independent code-review subjects without treating a role, turn completion or receipt as approval.

This store admits one separate review of an observed exact candidate and exposes
its readonly filesystem identity. Native review tools, decisions, acceptance and
publication remain separate responsibilities; no process is launched here.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.check_contracts import CandidateSubject
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    RunSpec,
    WorkspaceBinding,
    text,
)
from backend.runtime.development_workspace import _source_identity


@dataclass(frozen=True)
class CodeReviewTarget:
    """Owner-observed author candidate and complete review packet fingerprint, not a moving branch or role name."""

    attempt_id: str
    subject_sha256: str

    def __post_init__(self):
        """Require a complete candidate identifier and explicit SHA-256 observation before admission."""
        text(self.attempt_id, "Author attempt", 128)
        if not isinstance(self.subject_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.subject_sha256
        ):
            raise ValueError("Code review requires an observed subject fingerprint")


@dataclass(frozen=True)
class CodeReviewView:
    """Readonly exact captured candidate and distinct original registration; never permission to edit either view."""

    source: WorkspaceBinding
    workspace: str
    device: int
    inode: int
    head_sha: str
    tree_sha: str
    subject_sha256: str


class CodeReviews:
    """Own immutable review admission and provenance using the existing transaction, receipt and event boundary."""

    def __init__(self, runs):
        """Retain the actual run store without creating another scheduler or inference loop."""
        self.runs = runs

    def _subject(self, conn, project_id, attempt_id):
        """Snapshot current requirements, exact candidate, original closed author and every retained check within a finite budget."""
        candidate = CodeCandidates._row(conn, project_id, attempt_id)
        subject = CandidateSubject.from_row(candidate)
        author = conn.execute(
            """SELECT a.id AS attempt_id,a.run_id,a.fence,a.thread_id,a.turn_id,a.status AS attempt_status,
            r.actor_id,r.context_version,r.current_attempt_id,r.status AS run_status,r.execution_kind
            FROM runtime_attempts a JOIN runtime_runs r ON r.id=a.run_id
            WHERE a.id=? AND r.project_id=? AND r.task_id=?""",
            (attempt_id, project_id, subject.task_id),
        ).fetchone()
        if author is None or (
            author["run_id"],
            author["current_attempt_id"],
            author["fence"],
            author["context_version"],
            author["attempt_status"],
            author["run_status"],
            author["execution_kind"],
        ) != (
            subject.run_id,
            attempt_id,
            subject.fence,
            subject.context_version,
            "finished",
            "needs_review",
            "development",
        ):
            raise RunConflict(
                "Code review requires its closed original author candidate"
            )
        if author["thread_id"] is None or author["turn_id"] is None:
            raise RunConflict("Code review requires actual original native context")
        self.runs._closed_peer_proof(conn, attempt_id)
        if (
            conn.execute(
                "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=? AND protocol_version=1",
                (attempt_id,),
            ).fetchone()
            is None
            or conn.execute(
                "SELECT 1 FROM runtime_peers WHERE attempt_id=? AND kind='native' AND state='closed' AND bound_at IS NOT NULL",
                (attempt_id,),
            ).fetchone()
            is None
        ):
            raise RunConflict(
                "Code review requires a closed originally dispatched native peer"
            )
        requirements = self.runs._context_snapshot(conn, project_id, subject.task_id)
        if requirements["context_version"] != subject.context_version:
            raise RunConflict("Candidate belongs to obsolete requirements")
        # Execution progress is not a requirement change; claim/finish may update it.
        requirements["task"].pop("status")
        rows = conn.execute(
            "SELECT * FROM runtime_code_checks WHERE project_id=? AND attempt_id=? ORDER BY id LIMIT 65",
            (project_id, attempt_id),
        )
        checks = []
        for index, check in enumerate(rows):
            if index >= 64:
                raise RunConflict(
                    "Complete code review subject exceeds its check limit"
                )
            if json.loads(check["subject_json"]) != asdict(subject):
                raise RunConflict("Check evidence belongs to another candidate")
            checks.append(
                {
                    "id": check["id"],
                    "state": check["state"],
                    "spec": json.loads(check["spec_json"]),
                    "spec_sha256": check["spec_sha256"],
                    "operation_id": check["operation_id"],
                    "result": json.loads(check["result_json"])
                    if check["result_json"]
                    else None,
                    "issue": check["issue"],
                    "output": {
                        name: None
                        if check[name] is None
                        else {
                            "bytes": len(check[name]),
                            "sha256": hashlib.sha256(check[name]).hexdigest(),
                        }
                        for name in ("stdout", "stderr", "junit_xml")
                    },
                }
            )
        if hashlib.sha256(candidate["diff"]).hexdigest() != subject.diff_sha256:
            raise RunConflict("Saved candidate diff differs from its fingerprint")
        snapshot = {
            "schema_version": 1,
            "candidate": asdict(subject),
            "requirements": requirements,
            "author": {
                key: author[key]
                for key in (
                    "run_id",
                    "attempt_id",
                    "actor_id",
                    "fence",
                    "thread_id",
                    "turn_id",
                )
            },
            "diff_bytes": len(candidate["diff"]),
            "checks": checks,
        }
        if len(canonical(snapshot).encode()) > 1048576:
            raise RunConflict("Complete code review subject exceeds one MiB")
        return {"subject_sha256": digest(snapshot), "snapshot": snapshot}, candidate

    def subject(self, project_id, attempt_id):
        """Observe an admissible complete packet; this read neither starts a review nor accepts its content."""
        with self.runs._transaction() as conn:
            return self._subject(conn, project_id, attempt_id)[0]

    def admit_once(self, spec, target):
        """Atomically reserve a separate actor/run and its immutable packet; repeated intent returns only its original receipt."""
        if not isinstance(spec, RunSpec) or not isinstance(target, CodeReviewTarget):
            raise TypeError("Typed run specification and code review target required")
        intent = {"kind": "code_review.admit", **asdict(spec), "target": asdict(target)}
        with self.runs._transaction(write=True) as conn:
            prior = self.runs._receipt(
                conn, spec.project_id, spec.task_id, spec.operation_key, intent
            )
            if prior is not None:
                return self.runs._view(
                    self.runs._row(conn, spec.project_id, prior["run_id"])
                ), False
            self.runs._task(conn, spec.project_id, spec.task_id)
            packet, candidate = self._subject(conn, spec.project_id, target.attempt_id)
            author = packet["snapshot"]["author"]
            if (
                candidate["task_id"],
                candidate["context_version"],
                packet["subject_sha256"],
            ) != (spec.task_id, spec.context_version, target.subject_sha256):
                raise RunConflict("Code review target or requirements changed")
            if spec.actor_id == author["actor_id"]:
                raise RunConflict("An independent code review requires another actor")
            active = conn.execute(
                "SELECT id,status FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
                (spec.project_id, spec.task_id),
            ).fetchall()
            if any(
                row["id"] != author["run_id"] or row["status"] != "needs_review"
                for row in active
            ):
                raise RunConflict("Task already has other active or unreconciled work")
            binding = conn.execute(
                "SELECT * FROM runtime_workspace_bindings WHERE run_id=?",
                (author["run_id"],),
            ).fetchone()
            if binding is None:
                raise RunConflict(
                    "Code review requires the original source registration"
                )
            source = self.runs._binding_view(binding)
            if asdict(source) != json.loads(candidate["source_json"]):
                raise RunConflict("Candidate source differs from original admission")
            self.runs._check_registration(conn, spec.project_id, source)
            _source_identity(source)
            _source_identity(self._view(source, candidate, target.subject_sha256))
            run_id, now = str(uuid4()), self.runs.clock()
            conn.execute(
                """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at,execution_kind)
                VALUES(?,?,?,?,?,?,?,?,'queued',?,?,'code_review')""",
                (
                    run_id,
                    spec.project_id,
                    spec.task_id,
                    spec.actor_id,
                    spec.context_version,
                    spec.operation_key,
                    spec.prompt,
                    spec.runtime,
                    now,
                    now,
                ),
            )
            conn.execute(
                """INSERT INTO runtime_code_review_requests(run_id,project_id,task_id,context_version,subject_sha256,snapshot_json,
                author_run_id,author_attempt_id,author_actor_id,author_thread_id,candidate_workspace,candidate_device,candidate_inode,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    spec.project_id,
                    spec.task_id,
                    spec.context_version,
                    target.subject_sha256,
                    canonical(packet["snapshot"]),
                    author["run_id"],
                    target.attempt_id,
                    author["actor_id"],
                    author["thread_id"],
                    candidate["workspace"],
                    candidate["device"],
                    candidate["inode"],
                    now,
                ),
            )
            conn.execute(
                """INSERT INTO runtime_workspace_bindings(run_id,repository_id,repository_name,requested_repository_id,registration_path,workspace,device,inode,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    source.repository_id,
                    source.repository_name,
                    source.requested_repository_id,
                    source.registration_path,
                    source.workspace,
                    source.device,
                    source.inode,
                    now,
                ),
            )
            self.runs._save_receipt(
                conn,
                spec.project_id,
                spec.task_id,
                spec.operation_key,
                intent,
                {"run_id": run_id},
            )
            self.runs._event(
                conn,
                spec.project_id,
                spec.task_id,
                "run.admitted",
                {
                    "run_id": run_id,
                    "execution_kind": "code_review",
                    "actor_id": spec.actor_id,
                    "context_version": spec.context_version,
                    "subject_sha256": target.subject_sha256,
                    "author_attempt_id": target.attempt_id,
                },
            )
            return self.runs._view(self.runs._row(conn, spec.project_id, run_id)), True

    def _request(self, conn, project_id, run_id, *, require_current=False):
        """Read original immutable data; current access additionally verifies requirements, checks and exact source origin."""
        row = conn.execute(
            "SELECT * FROM runtime_code_review_requests WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Code review request not found")
        request = dict(row)
        run = self.runs._row(conn, project_id, run_id)
        if (
            run["execution_kind"] != "code_review"
            or run["actor_id"] == request["author_actor_id"]
            or (run["task_id"], run["context_version"])
            != (request["task_id"], request["context_version"])
        ):
            raise RunConflict("Code review has no independent original scope")
        if require_current:
            packet, candidate = self._subject(
                conn, project_id, request["author_attempt_id"]
            )
            if packet["subject_sha256"] != request["subject_sha256"] or (
                candidate["workspace"],
                candidate["device"],
                candidate["inode"],
            ) != (
                request["candidate_workspace"],
                request["candidate_device"],
                request["candidate_inode"],
            ):
                raise RunConflict("Code review subject changed")
        return request

    def request(self, project_id, run_id, *, require_current=False):
        """Inspect a historical or explicitly current review without issuing process or mutation authority."""
        with self.runs._transaction() as conn:
            return self._request(
                conn, project_id, run_id, require_current=require_current
            )

    @staticmethod
    def _view(source, candidate, subject_sha256):
        """Translate only a captured candidate identity into the readonly guest execution view."""
        return CodeReviewView(
            source,
            candidate["workspace"],
            candidate["device"],
            candidate["inode"],
            candidate["head_sha"],
            candidate["tree_sha"],
            subject_sha256,
        )

    def execution_view(self, conn, run):
        """Require the admitted source and unchanged packet before exposing a candidate to a readonly peer."""
        request = self._request(
            conn, run["project_id"], run["id"], require_current=True
        )
        binding = conn.execute(
            "SELECT * FROM runtime_workspace_bindings WHERE run_id=?", (run["id"],)
        ).fetchone()
        candidate = CodeCandidates._row(
            conn, run["project_id"], request["author_attempt_id"]
        )
        if binding is None:
            raise RunConflict("Code review has no original source admission")
        source = self.runs._binding_view(binding)
        if asdict(source) != json.loads(candidate["source_json"]):
            raise RunConflict("Code review source changed")
        self.runs._check_registration(conn, run["project_id"], source)
        view = self._view(source, candidate, request["subject_sha256"])
        _source_identity(source)
        _source_identity(view)
        return view
