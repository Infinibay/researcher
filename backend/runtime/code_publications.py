"""Durable owner publication requests and fresh host authority over an exact accepted candidate.

Admission is not a Git effect: the controller must still prepare its own broker,
validate actual Git bytes and retain physical closure/transaction receipts.
"""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from backend.knowledge.reviews import canonical
from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.code_acceptances import CodeAcceptances
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    WorkspaceBinding,
    command_key,
    identity,
    text,
)
from backend.runtime.development_workspace import _source_identity
from backend.runtime.publication_git import (
    PublicationDirectory,
    PublicationRefIntent,
    PublicationView,
)


@dataclass(frozen=True)
class CodePublicationIntent:
    """Original owner observation, including the acceptance decision and the exact destination seen before sending."""

    operation_key: str
    acceptance_operation_key: str
    author_attempt_id: str
    context_version: int
    subject_sha256: str
    review_sha256: str
    target_ref: str
    expected_target_sha: str | None

    def __post_init__(self):
        """Require a complete immutable acceptance/destination observation; no actor, path or model identity is client-selected."""
        command_key(self.operation_key)
        command_key(self.acceptance_operation_key)
        text(self.author_attempt_id, "Author attempt", 128)
        identity(self.context_version)
        if any(
            not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
            for value in (self.subject_sha256, self.review_sha256)
        ):
            raise ValueError("Publication requires exact subject/review fingerprints")
        PublicationRefIntent(
            self.operation_key, self.target_ref, self.expected_target_sha
        )


class CodePublications:
    """Reuse the original transaction, owner receipt and attempt machinery without reactivating author/reviewer leases."""

    def __init__(self, runs):
        """Retain the original run store; construction does not migrate, launch processes or grant authority."""
        self.runs = runs

    @staticmethod
    def linked_runs(conn, project_id, author_run_id, receipt):
        """Identify only publication activity bound to this exact acceptance; unrelated work retains its blocking meaning."""
        if (
            receipt is None
            or conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_code_publication_requests'"
            ).fetchone()
            is None
        ):
            return set()
        return {
            row[0]
            for row in conn.execute(
                """SELECT p.run_id FROM runtime_code_publication_requests p
            JOIN runtime_code_acceptances a ON a.id=p.acceptance_id
            JOIN runtime_runs r ON r.id=p.run_id
            WHERE p.project_id=? AND p.author_run_id=? AND a.run_id=p.author_run_id
            AND a.project_id=p.project_id AND a.task_id=p.task_id AND a.attempt_id=p.author_attempt_id
            AND a.context_version=p.context_version AND a.subject_sha256=p.subject_sha256 AND a.review_sha256=p.review_sha256
            AND a.operation_key=? AND p.author_attempt_id=? AND p.context_version=? AND p.subject_sha256=? AND p.review_sha256=?
            AND r.execution_kind='code_publication' AND r.project_id=p.project_id AND r.task_id=p.task_id AND r.context_version=p.context_version""",
                (
                    project_id,
                    author_run_id,
                    receipt["operation_key"],
                    receipt["attempt_id"],
                    receipt["context_version"],
                    receipt["subject_sha256"],
                    receipt["review_sha256"],
                ),
            )
        }

    @staticmethod
    def _view(value):
        """Reconstruct only original persisted source/candidate metadata identities, never refreshing them from current paths."""
        value = dict(value)
        value["source"] = WorkspaceBinding(**value["source"])
        for key in ("source_metadata", "candidate_metadata"):
            value[key] = PublicationDirectory(**value[key])
        return PublicationView(**value)

    def _request(self, conn, project_id, run_id):
        """Read one original request in its actual project and typed run scope."""
        run = self.runs._row(conn, project_id, run_id)
        row = conn.execute(
            "SELECT * FROM runtime_code_publication_requests WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        if row is None or run["execution_kind"] != "code_publication":
            raise RunNotFound("Host publication request not found")
        return dict(row)

    def request(self, project_id, run_id):
        """Inspect stored intent and result without starting or resuming an effect."""
        with self.runs._transaction() as conn:
            row = self._request(conn, project_id, run_id)
            return {
                "run_id": run_id,
                "intent": json.loads(row["intent_json"]),
                "view": json.loads(row["view_json"]),
                "receipt_ref": row["receipt_ref"],
                "result": json.loads(row["result_json"])
                if row["result_json"]
                else None,
            }

    def current(self, conn, run):
        """Validate accepted provenance, original source and pinned metadata for this host run without reopening the accepted task."""
        request = self._request(conn, run["project_id"], run["id"])
        state = CodeAcceptances(self.runs)._state(
            conn, run["project_id"], request["author_run_id"]
        )
        intent = CodePublicationIntent(**json.loads(request["intent_json"]))
        if not state["acceptance_current"] or not self._matches(state, intent):
            raise RunConflict(
                "Publication no longer has its exact current owner acceptance"
            )
        view = self._view(json.loads(request["view_json"]))
        self.runs._check_registration(conn, run["project_id"], view.source)
        _source_identity(view.source)
        _source_identity(view)
        if (
            PublicationDirectory.capture(Path(view.source.workspace) / ".git")
            != view.source_metadata
            or PublicationDirectory.capture(Path(view.workspace) / ".git")
            != view.candidate_metadata
        ):
            raise RunConflict("Publication original metadata identity changed")
        return view

    @staticmethod
    def _matches(state, intent):
        """Compare original owner observations without silently substituting a newer acceptance or candidate."""
        receipt = state["acceptance"]
        return bool(
            receipt
            and (
                receipt["operation_key"],
                state["candidate"]["attempt_id"],
                state["candidate"]["context_version"],
                state["subject_sha256"],
                state["review_sha256"],
            )
            == (
                intent.acceptance_operation_key,
                intent.author_attempt_id,
                intent.context_version,
                intent.subject_sha256,
                intent.review_sha256,
            )
        )

    def admit_once(self, project_id, author_run_id, intent):
        """Atomically admit one exact owner request; an original receipt survives corrections and never schedules itself again."""
        if not isinstance(intent, CodePublicationIntent):
            raise TypeError("Typed owner publication intent required")
        with self.runs._transaction(write=True) as conn:
            author = self.runs._row(conn, project_id, author_run_id)
            body = {
                "kind": "code_publication.admit",
                "author_run_id": author_run_id,
                **asdict(intent),
            }
            prior = self.runs._receipt(
                conn, project_id, author["task_id"], intent.operation_key, body
            )
            if prior is not None:
                return self.runs._view(
                    self.runs._row(conn, project_id, prior["run_id"])
                ), False
            state = CodeAcceptances(self.runs)._state(conn, project_id, author_run_id)
            if not state["acceptance_current"] or not self._matches(state, intent):
                raise RunConflict(
                    "Publication requires the exact current owner acceptance"
                )
            if (
                conn.execute(
                    "SELECT 1 FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review') LIMIT 1",
                    (project_id, author["task_id"]),
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id JOIN runtime_runs r ON r.id=a.run_id WHERE r.project_id=? AND r.task_id=? AND p.state!='closed' LIMIT 1",
                    (project_id, author["task_id"]),
                ).fetchone()
            ):
                raise RunConflict(
                    "Other publication or unreconciled work still owns this task"
                )
            candidate = CodeCandidates._row(conn, project_id, intent.author_attempt_id)
            binding = conn.execute(
                "SELECT * FROM runtime_workspace_bindings WHERE run_id=?",
                (author_run_id,),
            ).fetchone()
            if binding is None:
                raise RunConflict("Publication requires its original registered source")
            source = self.runs._binding_view(binding)
            if asdict(source) != json.loads(candidate["source_json"]):
                raise RunConflict(
                    "Publication source differs from its accepted candidate"
                )
            self.runs._check_registration(conn, project_id, source)
            view = PublicationView(
                source,
                candidate["workspace"],
                candidate["device"],
                candidate["inode"],
                candidate["head_sha"],
                candidate["tree_sha"],
                intent.subject_sha256,
                candidate["base_sha"],
                candidate["diff_sha256"],
                PublicationDirectory.capture(Path(source.workspace) / ".git"),
                PublicationDirectory.capture(Path(candidate["workspace"]) / ".git"),
            )
            _source_identity(source)
            _source_identity(view)
            accepted = conn.execute(
                "SELECT id FROM runtime_code_acceptances WHERE run_id=?",
                (author_run_id,),
            ).fetchone()[0]
            run_id, now = str(uuid4()), self.runs.clock()
            ref = PublicationRefIntent(
                run_id, intent.target_ref, intent.expected_target_sha
            )
            conn.execute(
                """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at,execution_kind)
            VALUES(?,?,?,'owner-publication',?,?,?,'codex','queued',?,?,'code_publication')""",
                (
                    run_id,
                    project_id,
                    author["task_id"],
                    intent.context_version,
                    intent.operation_key,
                    "Publish the exact accepted candidate to " + intent.target_ref,
                    now,
                    now,
                ),
            )
            conn.execute(
                """INSERT INTO runtime_code_publication_requests(run_id,project_id,task_id,author_run_id,author_attempt_id,acceptance_id,context_version,subject_sha256,review_sha256,target_ref,expected_target_sha,receipt_ref,intent_json,view_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    project_id,
                    author["task_id"],
                    author_run_id,
                    intent.author_attempt_id,
                    accepted,
                    intent.context_version,
                    intent.subject_sha256,
                    intent.review_sha256,
                    intent.target_ref,
                    intent.expected_target_sha,
                    ref.receipt_ref,
                    canonical(asdict(intent)),
                    canonical(asdict(view)),
                    now,
                ),
            )
            conn.execute(
                """INSERT INTO runtime_workspace_bindings(run_id,repository_id,repository_name,requested_repository_id,registration_path,workspace,device,inode,created_at)
            SELECT ?,repository_id,repository_name,requested_repository_id,registration_path,workspace,device,inode,? FROM runtime_workspace_bindings WHERE run_id=?""",
                (run_id, now, author_run_id),
            )
            self.runs._save_receipt(
                conn,
                project_id,
                author["task_id"],
                intent.operation_key,
                body,
                {"run_id": run_id},
            )
            self.runs._event(
                conn,
                project_id,
                author["task_id"],
                "code.publication_requested",
                {
                    "run_id": run_id,
                    "author_run_id": author_run_id,
                    "subject_sha256": intent.subject_sha256,
                    "target_ref": intent.target_ref,
                },
            )
            return self.runs._view(self.runs._row(conn, project_id, run_id)), True

    def complete(self, lease, observed, proof):
        """Atomically retain a physically closed exact Git result; a withdrawn context keeps history without accepting a new task."""
        from backend.knowledge.reviews import digest
        from backend.runtime.publication_git import PublicationRefObservation

        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            request = self._request(conn, lease.project_id, lease.run_id)
            if request["result_json"] is not None:
                return json.loads(request["result_json"])
            view = self._view(json.loads(request["view_json"]))
            ref = PublicationRefIntent(
                lease.run_id, request["target_ref"], request["expected_target_sha"]
            )
            if (
                not isinstance(observed, PublicationRefObservation)
                or observed.state != "published"
                or (observed.head_sha, observed.receipt_ref)
                != (view.head_sha, ref.receipt_ref)
                or proof.get("domain_closed") is not True
            ):
                raise RunConflict(
                    "Publication requires its exact closed Git observation"
                )
            operations = proof.get("operations", [])
            if (
                not operations
                or any(op.get("execution_closed") is not True for op in operations)
                or not any(
                    op.get("exit_code") == 0
                    and op.get("manifest", {}).get("profile")
                    == "owned-git-publication-v1"
                    and op["manifest"]["launch"].get("input_text")
                    == ref.transaction(view.head_sha)
                    for op in operations
                )
            ):
                raise RunConflict(
                    "Publication has no original successful ref transaction receipt"
                )
            self.runs._closed_peer_proof(conn, lease.attempt_id)
            run = self.runs._row(conn, lease.project_id, lease.run_id)
            current = (
                run["status"] == "running"
                and run["fence"] == lease.fence
                and self.runs._context(conn, lease.task_id) == lease.context_version
            )
            result = {
                "run_id": lease.run_id,
                "author_run_id": request["author_run_id"],
                "operation_key": run["operation_key"],
                "context_version": lease.context_version,
                "publication_performed": True,
                "completed_after_withdrawal": not current,
                "observed": asdict(observed),
                "proof_sha256": digest(proof),
                "grant_id": proof["grant_id"],
                "recorded_at": self.runs.clock(),
            }
            conn.execute(
                "UPDATE runtime_code_publication_requests SET result_json=? WHERE run_id=?",
                (canonical(result), lease.run_id),
            )
            conn.execute(
                "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
                (self.runs.clock(), lease.attempt_id),
            )
            conn.execute(
                "UPDATE runtime_runs SET status=?,updated_at=? WHERE id=?",
                (
                    "accepted"
                    if current
                    else "cancelled"
                    if run["cancel_requested"]
                    else "superseded",
                    self.runs.clock(),
                    lease.run_id,
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code.publication_completed",
                result,
            )
            return result

    def interrupted(self, lease, *, physically_closed, reason):
        """Preserve an uncertain original effect without auto-replay, while recording whether its actual processes closed."""
        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            if physically_closed:
                self.runs._closed_peer_proof(conn, lease.attempt_id)
                conn.execute(
                    "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
                    (self.runs.clock(), lease.attempt_id),
                )
            issue = {
                "code": "code_publication_uncertain",
                "message": "La publicación no dejó un resultado completo comprobado. Conservamos su solicitud y evidencia; no se repetirá automáticamente.",
                "next_action": "inspect_saved_work",
                "inference_started": False,
            }
            conn.execute(
                "UPDATE runtime_runs SET status='reconciling',issue_json=?,updated_at=? WHERE id=?",
                (canonical(issue), self.runs.clock(), lease.run_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code.publication_interrupted",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "execution_closed": physically_closed,
                    "reason": reason,
                },
            )
