"""Host-owned execution identity and transactions; no inference or job replay.

This adapter persists admission, authority and observations. It does not run a
model, mint a business grant, prove remote job termination or publish. Owner
acceptance is a distinct version-checked transaction over explicit delivered results.
"""

import hashlib
import json
import time
from collections.abc import Callable
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.db.connection import connect
from backend.runtime.contracts import (
    AttemptLease,
    CommandJob,
    CommandSpec,
    EventPage,
    JobReservation,
    RunConflict,
    RunEvent,
    RunNotFound,
    RunSpec,
    RunView,
    StaleAttempt,
    WorkspaceBinding,
    WorkspaceChanged,
    cancel_outcome,
    command_key,
    identity,
    invalidated_outcome,
    native_outcome,
    text,
    validate_correction,
)
from backend.runtime.task_profiles import DEVELOPMENT_TASK_TYPES, DOCUMENTARY_TASK_TYPES


def _json(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _duration(seconds):
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not 0 < seconds <= 120
    ):
        raise ValueError("Lease duration must be positive and at most 120 seconds")


class SQLiteRunStore:
    """Own durable admission, fenced attempts and version-bound review requests in SQLite."""

    def __init__(self, database: str | Path, *, clock: Callable[[], float] = time.time):
        """Bind an existing migrated database and the clock used for lease and receipt checks."""
        self.database = str(database)
        self.clock = clock

    @contextmanager
    def _transaction(self, *, write=False):
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn

    @staticmethod
    def _existing_task(conn, project_id, task_id):
        identity(project_id)
        identity(task_id)
        row = conn.execute(
            "SELECT status FROM tasks WHERE project_id=? AND id=?",
            (project_id, task_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Task not found in this project")
        return row

    @staticmethod
    def _task(conn, project_id, task_id):
        """Require open scoped work and current accepted plan/prerequisites before granting any native child execution authority."""
        row = SQLiteRunStore._existing_task(conn, project_id, task_id)
        if row["status"] in ("done", "cancelled", "failed"):
            raise RunConflict("Task no longer admits execution")
        if conn.execute("""SELECT 1 FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id
            JOIN runtime_runs r ON r.id=a.run_id WHERE p.task_id=? AND (r.status!='accepted' OR a.context_version!=coalesce(
            (SELECT version FROM task_contexts WHERE task_id=a.task_id),1))""", (task_id,)).fetchone():
            from backend.planning.execution import PlanExecutions

            if not PlanExecutions.admits_revised_task(conn, project_id, task_id):
                raise RunConflict("The original accepted project plan changed; inspect its history before new child work")
        if conn.execute("SELECT 1 FROM runtime_project_plan_tasks WHERE task_id=?", (task_id,)).fetchone() and conn.execute(
            """SELECT 1 FROM task_dependencies d JOIN tasks p ON p.id=d.depends_on_task_id
            WHERE d.task_id=? AND d.dependency_type='blocks' AND (p.status!='done' OR NOT EXISTS(
                SELECT 1 FROM runtime_runs r WHERE r.project_id=p.project_id AND r.task_id=p.id
                AND r.status='accepted' AND r.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=p.id),1))) LIMIT 1""", (task_id,)
        ).fetchone():
            raise RunConflict("A prerequisite task still lacks a current accepted result")
        return row

    @staticmethod
    def _context(conn, task_id):
        row = conn.execute(
            "SELECT version FROM task_contexts WHERE task_id=?", (task_id,)
        ).fetchone()
        return row[0] if row is not None else 1

    @staticmethod
    def _row(conn, project_id, run_id):
        """Load a run in its actual project, joining its native attempt, repository and review identity."""
        identity(project_id)
        text(run_id, "run_id", 128)
        row = conn.execute(
            """SELECT r.*,a.thread_id,a.turn_id,a.owner_id,a.status AS attempt_status,
            a.lease_expires_at,a.native_result_json,a.fence AS attempt_fence,
            chat.thread_id AS conversation_thread_id,dispatch.model AS dispatch_model,
            binding.repository_id AS bound_repository_id,binding.repository_name AS bound_repository_name,
            review.finding_id AS review_finding_id,review.subject_sha256 AS review_subject_sha256,
            decision.id AS review_decision_id,decision.verdict AS review_verdict
            FROM runtime_runs r LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id
            LEFT JOIN runtime_chat_links chat ON chat.run_id=r.id
            LEFT JOIN runtime_inference_dispatches dispatch ON dispatch.attempt_id=a.id
            LEFT JOIN runtime_workspace_bindings binding ON binding.run_id=r.id
            LEFT JOIN finding_review_requests review ON review.run_id=r.id
            LEFT JOIN finding_review_decisions decision ON decision.run_id=r.id
            WHERE r.project_id=? AND r.id=?""",
            (project_id, run_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Run not found in this project")
        return row

    @staticmethod
    def _view(row):
        """Project stored execution facts without interpreting a review verdict as task acceptance."""
        return RunView(
            run_id=row["id"],
            project_id=row["project_id"],
            task_id=row["task_id"],
            actor_id=row["actor_id"],
            context_version=row["context_version"],
            status=row["status"],
            fence=row["fence"],
            attempt_id=row["current_attempt_id"],
            thread_id=row["thread_id"],
            turn_id=row["turn_id"],
            prompt=row["prompt"],
            runtime=row["runtime"],
            result=json.loads(row["native_result_json"])
            if row["native_result_json"] is not None
            else None,
            cancel_requested=bool(row["cancel_requested"]),
            operation_key=row["operation_key"],
            conversation_thread_id=row["conversation_thread_id"],
            model=row["dispatch_model"],
            repository_id=row["bound_repository_id"],
            repository_name=row["bound_repository_name"],
            issue=json.loads(row["issue_json"]) if row["issue_json"] else None,
            execution_kind=row["execution_kind"],
            review={
                "finding_id": row["review_finding_id"],
                "subject_sha256": row["review_subject_sha256"],
                "decision_id": row["review_decision_id"],
                "verdict": row["review_verdict"],
            }
            if row["review_finding_id"] is not None
            else None,
        )

    @staticmethod
    def _event(conn, project_id, task_id, event_type, data):
        cursor = conn.execute(
            """INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json)
            VALUES(?,?,'runtime','task',?,?)""",
            (project_id, event_type, task_id, _json({"schema_version": 1, **data})),
        )
        return cursor.lastrowid

    @staticmethod
    def _receipt(conn, project, task, key, intent):
        row = conn.execute(
            "SELECT request_hash,result_json FROM runtime_commands WHERE project_id=? AND task_id=? AND operation_key=?",
            (project, task, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != _digest(intent):
            raise RunConflict("Operation key already identifies another intent")
        return json.loads(row["result_json"])

    def _save_receipt(self, conn, project, task, key, intent, result):
        conn.execute(
            "INSERT INTO runtime_commands(project_id,task_id,operation_key,request_hash,result_json,created_at) VALUES(?,?,?,?,?,?)",
            (project, task, key, _digest(intent), _json(result), self.clock()),
        )

    def get(self, project_id: int, run_id: str) -> RunView:
        with self._transaction() as conn:
            return self._view(self._row(conn, project_id, run_id))

    def context_snapshot(self, project_id, task_id):
        with self._transaction() as conn:
            return self._context_snapshot(conn, project_id, task_id)

    def _review_request(self, conn, project_id, run_id, *, require_current=False):
        """Read an admitted finding/code review descriptor; productive roots have none and native code dispatch also needs preflight."""
        from backend.knowledge.reviews import verify_current

        run = SQLiteRunStore._row(conn, project_id, run_id)
        if run["execution_kind"] == "code_review":
            from backend.runtime.code_reviews import CodeReviews

            code = CodeReviews(self)._request(conn, project_id, run_id, require_current=require_current)
            return {"kind": "code_review", **{key:code[key] for key in ("run_id", "subject_sha256", "author_run_id", "author_attempt_id", "author_actor_id", "context_version")}}
        request = conn.execute(
            "SELECT * FROM finding_review_requests WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        if request is None:
            if run["execution_kind"] not in ("research", "development"):
                raise RunConflict("Review execution has no original admitted subject")
            return None
        if (
            run["execution_kind"] != "finding_review"
            or run["actor_id"] == request["author_actor_id"]
        ):
            raise RunConflict("Review execution does not identify an independent actor")
        if require_current:
            verify_current(conn, dict(request))
        return {
            key: request[key]
            for key in (
                "run_id",
                "finding_id",
                "subject_sha256",
                "author_run_id",
                "author_attempt_id",
                "author_actor_id",
                "context_version",
            )
        }

    def review_request(self, project_id, run_id, *, require_current=False):
        """Expose the durable mode without inferring it from a prompt or role name."""
        with self._transaction() as conn:
            return self._review_request(
                conn, project_id, run_id, require_current=require_current
            )

    def accept_result(self, project_id, run_id, **command):
        """Record one owner decision over exact delivered content; no native tool can enter this use case."""
        from backend.knowledge.results import accept_result

        with self._transaction(write=True) as conn:
            row = self._row(conn, project_id, run_id)
            self._closed_peer_proof(conn, row["current_attempt_id"])
            receipt, recorded = accept_result(
                conn, project_id, run_id, now=self.clock(), **command
            )
            if recorded:
                self._event(
                    conn, project_id, row["task_id"], "result.accepted", receipt
                )
            return receipt

    def result_state(self, project_id, run_id):
        """Inspect a scoped delivered result without accepting it or starting inference."""
        from backend.knowledge.results import result_state

        with self._transaction() as conn:
            return result_state(conn, project_id, run_id)

    def code_result_state(self, project_id, run_id):
        """Expose exact code/check/review observations to the owner without native dispatch."""
        from backend.runtime.code_acceptances import CodeAcceptances

        return CodeAcceptances(self).state(project_id, run_id)

    def accept_code(self, project_id, run_id, **command):
        """Translate a paired-owner command into a neutral immutable intent; no native tool exposes this method."""
        from backend.runtime.code_acceptance_policy import CodeAcceptanceIntent
        from backend.runtime.code_acceptances import CodeAcceptances

        return CodeAcceptances(self).accept(project_id, run_id, CodeAcceptanceIntent(**command))

    def code_result_diff(self, project_id, run_id, **window):
        """Read the captured historical diff with complete-byte identity and explicit text coverage."""
        from backend.runtime.code_acceptances import CodeAcceptances

        return CodeAcceptances(self).diff(project_id, run_id, **window)

    def result_report(self, project_id, run_id, candidate_id, report_id, **window):
        """Read one explicitly selected immutable report in an owner-scoped bounded window."""
        from backend.knowledge.results import report_window

        with self._transaction() as conn:
            return report_window(
                conn, project_id, run_id, candidate_id, report_id, **window
            )

    def finding_review_state(self, project_id, finding_id, *, after_id=0, limit=20):
        """Inspect an observed subject and page actual review attempts without auto-validation."""
        from backend.knowledge.reviews import finding_review_state

        with self._transaction() as conn:
            return finding_review_state(
                conn, project_id, finding_id, after_id=after_id, limit=limit
            )

    def finding_review_detail(self, project_id, request_id):
        """Read an attributed bounded decision, preserving stale and partial assessments."""
        from backend.knowledge.reviews import finding_review_detail

        with self._transaction() as conn:
            return finding_review_detail(conn, project_id, request_id)

    def _context_snapshot(self, conn, project_id, task_id):
        self._existing_task(conn, project_id, task_id)
        task = conn.execute(
            """SELECT title,description,type,status,acceptance_criteria,context_json,
            priority,estimated_complexity,branch_name,assigned_to,reviewer,
            epic_id,milestone_id,parent_task_id FROM tasks WHERE project_id=? AND id=?""",
            (project_id, task_id),
        ).fetchone()
        revisions = conn.execute(
            "SELECT version,statement,source_kind,source_reference FROM runtime_context_revisions WHERE project_id=? AND task_id=? ORDER BY version",
            (project_id, task_id),
        ).fetchall()
        return {
            "task": dict(task),
            "context_version": self._context(conn, task_id),
            "corrections": [dict(row) for row in revisions],
            "task_changes": [
                {
                    "version": change["version"],
                    "source_kind": "task_metadata",
                    "actor": None,
                    "recorded_at": change["recorded_at"],
                    "changes": {
                        field: {"before": before[field], "after": value}
                        for field, value in after.items()
                        if before[field] != value
                    },
                }
                for change in conn.execute(
                    "SELECT * FROM runtime_task_input_changes WHERE project_id=? AND task_id=? ORDER BY version",
                    (project_id, task_id),
                )
                for before, after in [
                    (
                        json.loads(change["before_json"]),
                        json.loads(change["after_json"]),
                    )
                ]
            ],
            "user_answers": [
                {
                    "request_id": q["request_id"],
                    "asked_under_context": q["context_version"],
                    "answer_context_version": q["answer_context_version"],
                    "questions": json.loads(q["question_set_json"]),
                    "answers": json.loads(q["response"]),
                }
                for q in conn.execute(
                    """SELECT q.*,u.response FROM runtime_question_links q JOIN user_requests u ON u.id=q.request_id
                    JOIN runtime_runs r ON r.id=q.run_id WHERE q.project_id=? AND r.task_id=? AND u.status='responded'
                    AND q.answer_context_version IS NOT NULL ORDER BY q.answer_context_version,q.request_id""",
                    (project_id, task_id),
                )
            ],
        }

    def task_runs(self, project_id, task_id, *, limit=30):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid task execution history limit")
        with self._transaction() as conn:
            self._existing_task(conn, project_id, task_id)
            rows = conn.execute(
                "SELECT id FROM runtime_runs WHERE project_id=? AND task_id=? ORDER BY rowid DESC LIMIT ?",
                (project_id, task_id, limit),
            ).fetchall()
            return tuple(
                self._view(self._row(conn, project_id, row["id"])) for row in rows
            )

    def reserve_inference(
        self,
        lease,
        *,
        workspace,
        catalog_hash,
        limits,
        model=None,
        project_turn_limit=20,
        project_token_limit=4000000,
    ):
        """Reserve before turn/start. False means NEVER dispatch this intent again.

        These are observed-work fuses, not a physical billing cap. Unknown usage
        keeps the full token reservation. Project budgets are durable lifetime
        limits; changing policy requires a separate trusted migration/decision.
        """
        with self._transaction(write=True) as conn:
            return self._reserve_inference(
                conn,
                lease,
                workspace=workspace,
                catalog_hash=catalog_hash,
                limits=limits,
                model=model,
                project_turn_limit=project_turn_limit,
                project_token_limit=project_token_limit,
            )

    def reserve_input(
        self,
        lease,
        *,
        workspace,
        catalog_hash,
        model,
        limits,
        developer_instructions,
        catalog,
        project_turn_limit=20,
        project_token_limit=4000000,
    ):
        """Atomically freeze host input and reserve its one non-replayable turn."""
        from backend.runtime.contracts import InputTooLarge
        from backend.runtime.run_inputs import MAX_INPUT_BYTES, freeze_input

        text(developer_instructions, "developer instructions", MAX_INPUT_BYTES)
        catalog_json = _json(catalog)
        if hashlib.sha256(catalog_json.encode()).hexdigest() != catalog_hash:
            raise RunConflict("Native tool catalog differs from its recorded hash")
        with self._transaction(write=True) as conn:
            if not self._reserve_inference(
                conn,
                lease,
                workspace=workspace,
                catalog_hash=catalog_hash,
                model=model,
                limits=limits,
                project_turn_limit=project_turn_limit,
                project_token_limit=project_token_limit,
            ):
                previous = conn.execute(
                    "SELECT developer_instructions,business_catalog_json FROM runtime_input_snapshots WHERE attempt_id=?",
                    (lease.attempt_id,),
                ).fetchone()
                if previous is not None and tuple(previous) != (
                    developer_instructions,
                    catalog_json,
                ):
                    raise RunConflict(
                        "Attempt already reserved other host instructions"
                    )
                return (
                    None  # Includes historical dispatches: no invented input or replay.
                )
            row = self._row(conn, lease.project_id, lease.run_id)
            context = self._context_snapshot(conn, lease.project_id, lease.task_id)
            review = self._review_request(
                conn, lease.project_id, lease.run_id, require_current=True
            )
            if review is not None:
                context["review"] = review
            development = row["execution_kind"] == "development"
            code_review = row["execution_kind"] == "code_review"
            expected_types = DEVELOPMENT_TASK_TYPES if development or code_review else DOCUMENTARY_TASK_TYPES if row["execution_kind"] == "finding_review" else (*DOCUMENTARY_TASK_TYPES, "plan")
            if context["task"]["type"] not in expected_types:
                raise RunConflict("Task type changed before input reservation")
            if development:
                from backend.runtime.development_state import DevelopmentWorkspaces

                view = DevelopmentWorkspaces.read_view(conn, lease.project_id, lease.attempt_id)
                context["execution"] = {
                    "kind": "development", "repository_id": view.source.repository_id,
                    "base_sha": view.base_sha, "base_tree_sha": view.base_tree_sha,
                    "workspace": "/run/researcher-source", "workspace_access": "private-write",
                    "acceptance": "not_granted", "publication": "not_granted",
                }
            elif code_review:
                from backend.runtime.code_reviews import CodeReviews

                view = CodeReviews(self).execution_view(conn,row)
                context["execution"] = {"kind":"code_review", "repository_id":view.source.repository_id, "head_sha":view.head_sha, "tree_sha":view.tree_sha, "subject_sha256":view.subject_sha256, "workspace":"/run/researcher-source", "workspace_access":"readonly", "acceptance":"not_granted", "publication":"not_granted"}
            if context["task"]["type"] == "investigation" and row["execution_kind"] == "research":
                context["execution"] = {"kind": "investigation", "methodology": "scope_gather_organize_summarize", "workspace_access": "readonly", "acceptance": "not_granted", "publication": "not_granted"}
            if context["task"]["type"] == "research" and row["execution_kind"] == "research":
                context["execution"] = {"kind": "scientific_research", "methodology": "question_evidence_hypotheses_synthesis", "workspace_access": "readonly", "acceptance": "not_granted", "publication": "not_granted"}
            frozen = freeze_input(conn, row, context)
            if (
                len(frozen.input_text.encode())
                + len(developer_instructions.encode())
                + len(catalog_json.encode())
                > MAX_INPUT_BYTES
            ):
                raise InputTooLarge("Complete host input exceeds its byte limit")
            instructions_sha = hashlib.sha256(
                developer_instructions.encode()
            ).hexdigest()
            conn.execute(
                "INSERT INTO runtime_input_snapshots VALUES(?,1,?,?,?,?,?,?)",
                (
                    lease.attempt_id,
                    frozen.input_text,
                    frozen.input_sha256,
                    developer_instructions,
                    instructions_sha,
                    catalog_json,
                    self.clock(),
                ),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.input_frozen",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "input_sha256": frozen.input_sha256,
                    "instructions_sha256": instructions_sha,
                    "context_version": lease.context_version,
                    "native_start_observed": False,
                },
            )
            return frozen

    def input_record(self, project_id, run_id):
        """Read exact host-owned initial input; no reconstruction for old runs."""
        with self._transaction() as conn:
            run = self._row(conn, project_id, run_id)
            row = conn.execute(
                "SELECT * FROM runtime_input_snapshots WHERE attempt_id=?",
                (run["current_attempt_id"],),
            ).fetchone()
            if row is None:
                return {
                    "available": False,
                    "attempt_id": run["current_attempt_id"],
                    "reason": "no_record",
                }
            return {
                "available": True,
                "attempt_id": row["attempt_id"],
                "schema_version": row["schema_version"],
                "input_text": row["input_text"],
                "input_sha256": row["input_sha256"],
                "developer_instructions": row["developer_instructions"],
                "instructions_sha256": row["instructions_sha256"],
                "business_catalog": json.loads(row["business_catalog_json"]),
                "model": run["dispatch_model"],
                "created_at": row["created_at"],
                "native_start_observed": run["turn_id"] is not None,
                "coverage": {
                    "researcher_input": "exact",
                    "native_system_instructions": "not_exposed",
                    "subsequent_tool_results": "not_in_initial_snapshot",
                    "understanding": "not_proven",
                },
            }

    def _reserve_inference(
        self,
        conn,
        lease,
        *,
        workspace,
        catalog_hash,
        limits,
        model=None,
        project_turn_limit=20,
        project_token_limit=4000000,
    ):
        """Reserve inference under current authority, requiring validated code review preflight."""
        import re

        from backend.runtime.native_commands import VERSION

        text(workspace, "workspace", 4096)
        if model is not None:
            text(model, "model", 256)
        if not re.fullmatch(r"[a-f0-9]{64}", catalog_hash):
            raise ValueError("Expected a tool catalog SHA256")
        if limits.max_turns != 1:
            raise ValueError("Each dispatch reserves exactly one native turn")
        identity(project_turn_limit)
        identity(project_token_limit)
        intent = (workspace, catalog_hash, VERSION, _json(asdict(limits)), model)
        row = self._authority(conn, lease)
        if row["execution_kind"] in ("code_publication", "remote_publication"):
            raise RunConflict("host-only publication cannot reserve model inference")
        self._bound_workspace(conn, row, workspace)
        if row["execution_kind"] == "code_review":
            from backend.runtime.code_review_records import CodeReviewRecords

            CodeReviewRecords(self).require_preflight(conn,row)
        if row["thread_id"] is None:
            raise RunConflict("Bind native thread before reserving dispatch")
        previous = conn.execute(
            "SELECT * FROM runtime_inference_dispatches WHERE attempt_id=?",
            (lease.attempt_id,),
        ).fetchone()
        if previous is not None:
            if (
                tuple(
                    previous[k]
                    for k in (
                        "workspace",
                        "catalog_hash",
                        "runtime_version",
                        "limits_json",
                        "model",
                    )
                )
                != intent
            ):
                raise RunConflict("Attempt already reserved another inference intent")
            return False
        conn.execute(
            "INSERT OR IGNORE INTO runtime_project_budgets VALUES(?,?,?)",
            (lease.project_id, project_turn_limit, project_token_limit),
        )
        policy = conn.execute(
            "SELECT * FROM runtime_project_budgets WHERE project_id=?",
            (lease.project_id,),
        ).fetchone()
        if (policy["turn_limit"], policy["token_limit"]) != (
            project_turn_limit,
            project_token_limit,
        ):
            raise RunConflict(
                "Project budget policy changed; explicit reconciliation required"
            )
        used = conn.execute(
            """SELECT COUNT(*), COALESCE(SUM(CASE WHEN status='settled' AND observed_tokens IS NOT NULL
            THEN observed_tokens ELSE MAX(token_ceiling,COALESCE(observed_tokens,0)) END),0) FROM runtime_inference_dispatches WHERE project_id=?""",
            (lease.project_id,),
        ).fetchone()
        if (
            used[0] >= project_turn_limit
            or used[1] + limits.max_observed_tokens > project_token_limit
        ):
            raise RunConflict("Project work budget exhausted; no native turn was sent")
        conn.execute(
            """INSERT INTO runtime_inference_dispatches(attempt_id,project_id,workspace,catalog_hash,
            runtime_version,limits_json,model,token_ceiling,status,created_at) VALUES(?,?,?,?,?,?,?,?,'reserved',?)""",
            (
                lease.attempt_id,
                lease.project_id,
                *intent,
                limits.max_observed_tokens,
                self.clock(),
            ),
        )
        self._event(
            conn,
            lease.project_id,
            lease.task_id,
            "run.dispatch_reserved",
            {
                "run_id": lease.run_id,
                "attempt_id": lease.attempt_id,
                "catalog_hash": catalog_hash,
                "limits": asdict(limits),
                "runtime_version": VERSION,
                "model": model,
            },
        )
        return True

    def note_inference_usage(self, lease, cumulative):
        """Preserve reported high water even if the turn later loses its receipt."""
        if type(cumulative) is not int or not 0 <= cumulative <= 9223372036854775807:
            raise ValueError("Invalid native cumulative token observation")
        with self._transaction(write=True) as conn:
            self._original_attempt(conn, lease)
            row = conn.execute(
                "SELECT observed_tokens FROM runtime_inference_dispatches WHERE attempt_id=?",
                (lease.attempt_id,),
            ).fetchone()
            if row is None:
                raise RunConflict("No reserved native dispatch")
            if row[0] is not None and row[0] >= cumulative:
                return
            conn.execute(
                "UPDATE runtime_inference_dispatches SET observed_tokens=? WHERE attempt_id=?",
                (cumulative, lease.attempt_id),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.usage_high_water",
                {
                    "run_id": lease.run_id,
                    "observed_tokens": cumulative,
                    "billing_quota_known": False,
                },
            )

    def settle_inference(self, lease, *, observed_tokens, native_status):
        native_outcome(native_status)
        if observed_tokens is not None and (
            type(observed_tokens) is not int or observed_tokens < 0
        ):
            raise ValueError("Observed tokens must be a nonnegative integer or unknown")
        with self._transaction(write=True) as conn:
            self._original_attempt(conn, lease)
            row = conn.execute(
                "SELECT * FROM runtime_inference_dispatches WHERE attempt_id=?",
                (lease.attempt_id,),
            ).fetchone()
            if row is None:
                raise RunConflict("No reserved native dispatch")
            if row["observed_tokens"] is not None:
                observed_tokens = max(row["observed_tokens"], observed_tokens or 0)
            if row["status"] == "settled":
                if (row["observed_tokens"], row["native_status"]) != (
                    observed_tokens,
                    native_status,
                ):
                    raise RunConflict("Conflicting terminal usage receipt")
                return
            conn.execute(
                """UPDATE runtime_inference_dispatches SET status='settled',observed_tokens=?,
                         native_status=?,settled_at=? WHERE attempt_id=?""",
                (observed_tokens, native_status, self.clock(), lease.attempt_id),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.usage_observed",
                {
                    "run_id": lease.run_id,
                    "observed_tokens": observed_tokens,
                    "native_status": native_status,
                    "usage_unknown": observed_tokens is None,
                },
            )

    def recover_owners(self, owner_id):
        """Call ONLY after acquiring the exclusive database owner OS lock.

        No native prompt replay and no assertion that old jobs are terminal.
        """
        text(owner_id, "owner_id", 128)
        with self._transaction(write=True) as conn:
            rows = conn.execute(
                """SELECT r.project_id,r.id FROM runtime_runs r JOIN runtime_attempts a
                ON a.id=r.current_attempt_id WHERE a.owner_id<>? AND a.status IN ('running','reconciling')
                AND r.status IN ('running','cancelling')""",
                (owner_id,),
            ).fetchall()
            for item in rows:
                row = self._row(conn, item["project_id"], item["id"])
                self._withdraw(conn, row, "reconciling")
                conn.execute(
                    "UPDATE runtime_inference_dispatches SET status='unknown' WHERE attempt_id=? AND status='reserved'",
                    (row["current_attempt_id"],),
                )
                self._event(
                    conn,
                    row["project_id"],
                    row["task_id"],
                    "run.owner_lost",
                    {
                        "run_id": row["id"],
                        "attempt_id": row["current_attempt_id"],
                        "replay": False,
                    },
                )
            return len(rows)

    def uncertain_inference(self, lease, *, reason, native_result=None):
        """Retain uncertainty when a worker cannot prove its peer teardown."""
        text(reason, "uncertainty reason", 128)
        if native_result is not None:
            native_outcome(native_result["native_status"])
            text(native_result["summary"], "summary", 200000)
        with self._transaction(write=True) as conn:
            self._original_attempt(conn, lease)
            row = self._row(conn, lease.project_id, lease.run_id)
            if row["current_attempt_id"] != lease.attempt_id or row["status"] not in (
                "running",
                "cancelling",
                "reconciling",
            ):
                raise StaleAttempt("Uncertainty cannot replace another result or owner")
            self._withdraw(conn, row, "reconciling")
            if native_result is not None:
                conn.execute(
                    "UPDATE runtime_attempts SET native_result_json=? WHERE id=?",
                    (_json(native_result), lease.attempt_id),
                )
            conn.execute(
                "UPDATE runtime_inference_dispatches SET status='unknown' WHERE attempt_id=?",
                (lease.attempt_id,),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.peer_state_unknown",
                {"run_id": lease.run_id, "reason": reason, "replay": False},
            )

    def retire_withdrawn(self, lease):
        """Host-only after physical closure: derive Stop/context from durable state.

        A metadata writer need not share the coordinator's callback or heartbeat.
        This records retirement, never acceptance, replay or a physical kill.
        """
        with self._transaction(write=True) as conn:
            self._original_attempt(conn, lease)
            row = self._row(conn, lease.project_id, lease.run_id)
            if row["current_attempt_id"] != lease.attempt_id:
                raise StaleAttempt("Another attempt owns this run")
            if row["cancel_requested"]:
                outcome = "cancelled"
            elif self._context(conn, lease.task_id) != lease.context_version:
                outcome = "superseded"
            else:
                return None
            if row["status"] in ("cancelled", "superseded", "failed", "accepted"):
                return self._view(row)
            return self._retire_closed(conn, row, outcome)

    def retire_inference(self, lease, *, outcome):
        """Host-only: caller has closed its native AND business peers in one worker.

        Cannot certify an owned command whose terminal receipt is missing. Native
        completion/unknown usage remain independent of product task acceptance.
        """
        if outcome not in ("cancelled", "superseded", "failed"):
            raise ValueError("Invalid retired inference outcome")
        with self._transaction(write=True) as conn:
            self._original_attempt(conn, lease)
            row = self._row(conn, lease.project_id, lease.run_id)
            if row["current_attempt_id"] != lease.attempt_id:
                raise StaleAttempt("Another attempt owns this run")
            if row["status"] in (
                "accepted",
                "needs_review",
                "cancelled",
                "superseded",
                "failed",
            ):
                return self._view(row)
            if outcome == "cancelled" and not row["cancel_requested"]:
                raise RunConflict("No durable cancellation intent")
            if (
                outcome == "superseded"
                and self._context(conn, lease.task_id) == lease.context_version
            ):
                raise RunConflict("No durable context correction")
            return self._retire_closed(conn, row, outcome)

    @staticmethod
    def _closed_peer_proof(conn, attempt_id):
        """Require original peer closure by execution kind; an HTTP-only remote stage has no fictitious model or command process peers."""
        scope = conn.execute(
            "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if scope is not None:
            peers = conn.execute(
                "SELECT kind,state FROM runtime_peers WHERE attempt_id=?", (attempt_id,)
            ).fetchall()
            run = conn.execute("SELECT r.execution_kind FROM runtime_runs r JOIN runtime_attempts a ON a.run_id=r.id WHERE a.id=?", (attempt_id,)).fetchone()
            required = {"command"} if run and run[0] in ("code_publication", "remote_publication") else {"native", "business"}
            if run and run[0] == "remote_publication":
                remote = conn.execute("SELECT p.stage FROM runtime_remote_publications p JOIN runtime_attempts a ON a.run_id=p.run_id WHERE a.id=?", (attempt_id,)).fetchone()
                if (remote and remote[0] == "pull") or not peers:
                    required = set()
            if not required <= {peer["kind"] for peer in peers} or any(
                peer["state"] != "closed" for peer in peers
            ):
                raise RunConflict("Owned peer closure has not been proven")

    def _retire_closed(self, conn, row, outcome):
        attempt_id = row["current_attempt_id"]
        self._closed_peer_proof(conn, attempt_id)
        if conn.execute(
            """SELECT 1 FROM runtime_jobs j WHERE attempt_id=? AND status<>'exited'
            AND NOT EXISTS(SELECT 1 FROM runtime_peers p WHERE p.id=j.peer_id
                AND p.attempt_id=j.attempt_id AND p.kind='command' AND p.state='closed'
                AND p.database_identity IS NOT NULL)""",
            (attempt_id,),
        ).fetchone():
            raise RunConflict("Owned jobs require terminal reconciliation")
        # A closed actor cannot keep acting, but no terminal result is invented.
        for job in conn.execute(
            "SELECT id FROM runtime_jobs WHERE attempt_id=? AND status IN ('dispatching','cancelling')",
            (attempt_id,),
        ).fetchall():
            conn.execute(
                "UPDATE runtime_jobs SET status='unknown',error=COALESCE(error,'PeerClosedWithoutTerminalReceipt') WHERE id=?",
                (job["id"],),
            )
            self._event(
                conn,
                row["project_id"],
                row["task_id"],
                "job.quiescent",
                {
                    "job_id": job["id"],
                    "attempt_id": attempt_id,
                    "local_execution_closed": True,
                    "exit_code": None,
                },
            )
        self._withdraw(conn, row, outcome)
        conn.execute(
            "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
            (self.clock(), attempt_id),
        )
        conn.execute(
            "UPDATE runtime_inference_dispatches SET status='unknown' WHERE attempt_id=? AND status='reserved'",
            (attempt_id,),
        )
        self._event(
            conn,
            row["project_id"],
            row["task_id"],
            "run.peers_retired",
            {
                "run_id": row["id"],
                "attempt_id": attempt_id,
                "status": outcome,
                "native_and_business_closed": True,
            },
        )
        return self._view(self._row(conn, row["project_id"], row["id"]))

    @staticmethod
    def _admission_intent(spec, conversation_thread, repository_id=None, review=None, prior_code=None):
        """Keep historical ordinary intents stable and bind exact review or earlier-code input selections."""
        intent = {"kind": "admit", **asdict(spec)}
        if conversation_thread is not None:
            command_key(conversation_thread)
            intent["conversation_thread"] = conversation_thread
        if repository_id is not None:
            identity(repository_id)
            intent["repository_id"] = repository_id
        if review is not None:
            from backend.research.models import ReviewTarget

            if not isinstance(review, ReviewTarget):
                raise ValueError("A typed owner-observed review target is required")
            intent["review"] = asdict(review)
        if prior_code is not None:
            from backend.runtime.code_carryover import PriorCodeTarget
            from backend.runtime.file_imports import PriorFilesTarget
            from backend.runtime.branch_inputs import PriorBranchTarget

            if review is not None or not isinstance(prior_code, (PriorCodeTarget, PriorFilesTarget, PriorBranchTarget)):
                raise ValueError("Prior code requires a typed author input selection")
            intent["prior_code"] = asdict(prior_code)
        return intent

    def _admission_receipt(
        self, conn, spec, conversation_thread, repository_id, review=None, prior_code=None
    ):
        """Recover original admission receipts without rechecking or replaying effects."""
        intent = self._admission_intent(
            spec, conversation_thread, repository_id, review, prior_code
        )
        try:
            return self._receipt(
                conn, spec.project_id, spec.task_id, spec.operation_key, intent
            )
        except RunConflict:
            if repository_id is None or review is not None or prior_code is not None:
                raise
            # Historical receipts did not record selection. They may be read,
            # never used to infer a workspace or restart a queued request.
            old = self._receipt(
                conn,
                spec.project_id,
                spec.task_id,
                spec.operation_key,
                self._admission_intent(spec, conversation_thread),
            )
            if (
                old is None
                or self._row(conn, spec.project_id, old["run_id"])[
                    "bound_repository_id"
                ]
                is not None
            ):
                raise RunConflict("Operation key already identifies another intent")
            return old

    def admission_receipt(
        self, spec, *, conversation_thread=None, repository_id=None, review=None, prior_code=None
    ):
        """Read an exact ordinary or review request receipt without scheduling work."""
        with self._transaction() as conn:
            receipt = self._admission_receipt(
                conn, spec, conversation_thread, repository_id, review, prior_code
            )
            return (
                self._view(self._row(conn, spec.project_id, receipt["run_id"]))
                if receipt
                else None
            )

    @staticmethod
    def _correction_intent(command):
        validate_correction(**command)
        return {
            "kind": "correct_context",
            **{key: value for key, value in command.items() if key != "operation_key"},
        }

    def correction_receipt(self, **command):
        intent = self._correction_intent(command)
        with self._transaction() as conn:
            receipt = self._receipt(
                conn,
                command["project_id"],
                command["task_id"],
                command["operation_key"],
                intent,
            )
            return receipt["version"] if receipt else None

    @staticmethod
    def _review_subject(conn, spec, target):
        """Require the observed complete subject and an actual different original author."""
        from backend.knowledge.reviews import finding_subject

        subject = finding_subject(conn, spec.project_id, target.finding_id)
        if subject["snapshot"]["finding"]["task_id"] != spec.task_id:
            raise RunConflict("Review finding belongs to another task")
        if subject["subject_sha256"] != target.subject_sha256:
            raise RunConflict("Review subject changed; inspect the current version")
        if not subject["reviewable"]:
            raise RunConflict("Independent review requires known closed author origin")
        if subject["snapshot"]["author"]["actor_id"] == spec.actor_id:
            raise RunConflict("Independent review requires a different admitted actor")
        return subject

    def admit(
        self, spec: RunSpec, *, conversation_thread=None, binding=None, review=None, prior_code=None
    ) -> RunView:
        """Return the durable receipt for one scoped admission, freezing a review target when supplied."""
        return self.admit_once(
            spec,
            conversation_thread=conversation_thread,
            binding=binding,
            review=review,
            prior_code=prior_code,
        )[0]

    def admit_once(
        self, spec: RunSpec, *, conversation_thread=None, binding=None, review=None, prior_code=None
    ):
        """Admit a typed author or bound independent finding review without reinterpreting historical receipts."""
        repository_id = binding.requested_repository_id if binding else None
        intent = self._admission_intent(
            spec, conversation_thread, repository_id, review, prior_code
        )
        with self._transaction(write=True) as conn:
            receipt = self._admission_receipt(
                conn, spec, conversation_thread, repository_id, review, prior_code
            )
            if receipt is not None:
                return self._view(
                    self._row(conn, spec.project_id, receipt["run_id"])
                ), False
            self._task(conn, spec.project_id, spec.task_id)
            from backend.runtime.code_carryover import CodeCarryovers

            prior_packet = CodeCarryovers(self).capture(conn, spec, binding, prior_code) if prior_code is not None else None
            if self._context(conn, spec.task_id) != spec.context_version:
                raise RunConflict("Run context is already obsolete")
            subject = (
                self._review_subject(conn, spec, review) if review is not None else None
            )
            active = conn.execute(
                "SELECT id,status FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
                (spec.project_id, spec.task_id),
            ).fetchall()
            author_run = subject["snapshot"]["author"]["run_id"] if subject else None
            if any(
                row["id"] != author_run or row["status"] != "needs_review"
                for row in active
            ):
                raise RunConflict("Task already has active or unreconciled work")
            conn.execute(
                "INSERT OR IGNORE INTO task_contexts(task_id,version) VALUES(?,1)",
                (spec.task_id,),
            )
            run_id = str(uuid4())
            now = self.clock()
            task_type = conn.execute("SELECT type FROM tasks WHERE project_id=? AND id=?", (spec.project_id, spec.task_id)).fetchone()[0]
            execution_kind = "finding_review" if review is not None else ("development" if task_type in DEVELOPMENT_TASK_TYPES else "research")
            conn.execute(
                """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at,execution_kind)
                VALUES(?,?,?,?,?,?,?,?,'queued',?,?,?)""",
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
                    execution_kind,
                ),
            )
            if task_type == "plan" and review is None:
                from backend.planning.store import ProjectPlans

                ProjectPlans.capture(conn, self, spec, run_id)
            if subject is not None:
                author = subject["snapshot"]["author"]
                conn.execute(
                    """INSERT INTO finding_review_requests(run_id,project_id,task_id,finding_id,context_version,
                    subject_sha256,snapshot_json,author_run_id,author_attempt_id,author_actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        run_id,
                        spec.project_id,
                        spec.task_id,
                        review.finding_id,
                        spec.context_version,
                        review.subject_sha256,
                        _json(subject["snapshot"]),
                        author["run_id"],
                        author["attempt_id"],
                        author["actor_id"],
                        now,
                    ),
                )
            if conversation_thread is not None:
                self._attach_conversation(conn, spec, run_id, conversation_thread)
            if binding is not None:
                self._check_registration(conn, spec.project_id, binding)
                conn.execute(
                    """INSERT INTO runtime_workspace_bindings(run_id,repository_id,repository_name,
                    requested_repository_id,registration_path,workspace,device,inode,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        run_id,
                        binding.repository_id,
                        binding.repository_name,
                        binding.requested_repository_id,
                        binding.registration_path,
                        binding.workspace,
                        binding.device,
                        binding.inode,
                        now,
                    ),
                )
            self._save_receipt(
                conn,
                spec.project_id,
                spec.task_id,
                spec.operation_key,
                intent,
                {"run_id": run_id, **({"prior_code": prior_packet} if prior_packet is not None else {})},
            )
            from backend.planning.execution import PlanExecutions

            PlanExecutions(self).attach(conn, spec, run_id)
            self._event(
                conn,
                spec.project_id,
                spec.task_id,
                "run.admitted",
                {
                    "run_id": run_id,
                    "actor_id": spec.actor_id,
                    "context_version": spec.context_version,
                },
            )
            return self._view(self._row(conn, spec.project_id, run_id)), True

    @staticmethod
    def _check_registration(conn, project_id, binding):
        repository = conn.execute(
            "SELECT local_path FROM repositories WHERE id=? AND project_id=? AND status='active'",
            (binding.repository_id, project_id),
        ).fetchone()
        if repository is None or repository["local_path"] != binding.registration_path:
            raise WorkspaceChanged("Admitted repository registration changed")

    def workspace_binding(self, project_id, run_id):
        with self._transaction() as conn:
            self._row(conn, project_id, run_id)
            row = conn.execute(
                "SELECT * FROM runtime_workspace_bindings WHERE run_id=?", (run_id,)
            ).fetchone()
            return self._binding_view(row) if row is not None else None

    @staticmethod
    def _binding_view(row):
        return WorkspaceBinding(
            **{
                name: row[name]
                for name in (
                    "repository_id",
                    "repository_name",
                    "registration_path",
                    "workspace",
                    "device",
                    "inode",
                    "requested_repository_id",
                )
            }
        )

    def _bound_workspace(self, conn, row, workspace=None):
        """Validate dispatch against its actual ready view while retaining the original source registration."""
        binding = conn.execute(
            "SELECT * FROM runtime_workspace_bindings WHERE run_id=?", (row["id"],)
        ).fetchone()
        if binding is not None:
            source = self._binding_view(binding)
            self._check_registration(conn, row["project_id"], source)
            expected = source.workspace
            if workspace is not None and row["execution_kind"] == "development":
                from backend.runtime.development_state import DevelopmentWorkspaces
                from backend.runtime.development_workspace import _source_identity

                view = DevelopmentWorkspaces.read_view(conn, row["project_id"], row["current_attempt_id"])
                if view.source != source:
                    raise WorkspaceChanged("Private execution view differs from the admitted source")
                _source_identity(source)
                _source_identity(view)
                expected = view.workspace
            if workspace is not None and row["execution_kind"] == "code_review":
                from backend.runtime.code_reviews import CodeReviews

                try:
                    expected = CodeReviews(self).execution_view(conn, row).workspace
                except RunNotFound as exc:
                    raise WorkspaceChanged(
                        "Code review requires an exact candidate snapshot"
                    ) from exc
            if workspace is not None and workspace != expected:
                raise WorkspaceChanged("Dispatch differs from the admitted workspace")
        elif workspace is not None and row["execution_kind"] in ("development", "code_review"):
            raise WorkspaceChanged("Development dispatch requires an admitted source and private view")

    def request_start(
        self, *, project_id, run_id, expected_fence, context_version, operation_key
    ):
        identity(context_version)
        command_key(operation_key)
        if type(expected_fence) is not int or expected_fence < 0:
            raise ValueError("Invalid expected fence")
        intent = {
            "kind": "retry_start",
            "run_id": run_id,
            "expected_fence": expected_fence,
            "context_version": context_version,
        }
        with self._transaction(write=True) as conn:
            row = self._row(conn, project_id, run_id)
            previous = self._receipt(
                conn, project_id, row["task_id"], operation_key, intent
            )
            if previous is not None:
                return self._view(row), False
            if (
                row["status"] != "queued"
                or row["current_attempt_id"] is not None
                or row["fence"] != expected_fence
                or row["context_version"] != context_version
                or self._context(conn, row["task_id"]) != context_version
            ):
                raise RunConflict(
                    "Refresh the queued request before retrying its start"
                )
            self._task(conn, project_id, row["task_id"])
            self._save_receipt(
                conn,
                project_id,
                row["task_id"],
                operation_key,
                intent,
                {"run_id": run_id},
            )
            self._event(
                conn,
                project_id,
                row["task_id"],
                "run.start_requested",
                {
                    "run_id": run_id,
                    "operation_key": operation_key,
                    "original_request": True,
                },
            )
            return self._view(row), True

    def record_issue(self, project_id, run_id, issue, *, attempt_id=None):
        command_key(issue["code"])
        text(issue["message"], "issue message", 4096)
        if (
            issue["inference_started"] is not None
            and type(issue["inference_started"]) is not bool
        ):
            raise ValueError("Inference observation must be true, false or unknown")
        with self._transaction(write=True) as conn:
            row = self._row(conn, project_id, run_id)
            if attempt_id is None:
                if row["status"] != "queued" or row["current_attempt_id"] is not None:
                    return self._view(row)
            elif row["current_attempt_id"] != attempt_id or row["status"] not in (
                "failed",
                "reconciling",
            ):
                return self._view(row)
            if row["issue_json"] != _json(issue):
                conn.execute(
                    "UPDATE runtime_runs SET issue_json=?,updated_at=? WHERE id=?",
                    (_json(issue), self.clock(), run_id),
                )
                self._event(
                    conn,
                    project_id,
                    row["task_id"],
                    "run.issue",
                    {"run_id": run_id, **issue},
                )
            return self._view(self._row(conn, project_id, run_id))

    @staticmethod
    def _attach_conversation(conn, spec, run_id, thread_id):
        thread = conn.execute(
            "SELECT * FROM conversation_threads WHERE thread_id=?", (thread_id,)
        ).fetchone()
        if thread is not None:
            if thread["project_id"] != spec.project_id:
                raise RunNotFound("Conversation not found in this project")
            if (
                thread["task_id"] not in (None, spec.task_id)
                or thread["thread_type"] != "user_chat"
                or thread["status"] != "active"
            ):
                raise RunConflict("Conversation belongs to another task or is closed")
            conn.execute(
                "UPDATE conversation_threads SET task_id=? WHERE thread_id=?",
                (spec.task_id, thread_id),
            )
        else:
            conn.execute(
                "INSERT INTO conversation_threads(thread_id,project_id,task_id,thread_type) VALUES(?,?,?,'user_chat')",
                (thread_id, spec.project_id, spec.task_id),
            )
        user_message = conn.execute(
            """INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,
            conversation_type,message,metadata_json) VALUES(?,?,'user','researcher','user_to_agent',?,?)""",
            (
                spec.project_id,
                thread_id,
                spec.prompt,
                _json(
                    {
                        "schema_version": 1,
                        "runtime_run_id": run_id,
                        "context_version": spec.context_version,
                        "kind": "instruction",
                    }
                ),
            ),
        ).lastrowid
        conn.execute(
            "INSERT INTO runtime_chat_links(run_id,project_id,thread_id,user_message_id) VALUES(?,?,?,?)",
            (run_id, spec.project_id, thread_id, user_message),
        )
        conn.execute(
            "UPDATE conversation_threads SET last_message_at=CURRENT_TIMESTAMP WHERE thread_id=?",
            (thread_id,),
        )

    @staticmethod
    def _deliver_proposal(conn, lease, summary):
        link = conn.execute(
            "SELECT * FROM runtime_chat_links WHERE run_id=?", (lease.run_id,)
        ).fetchone()
        if link is None or link["proposal_message_id"] is not None:
            return
        message_id = conn.execute(
            """INSERT INTO chat_messages(project_id,thread_id,parent_message_id,from_agent,to_agent,
            conversation_type,message,metadata_json) VALUES(?,?,?,'researcher','user','agent_to_user',?,?)""",
            (
                lease.project_id,
                link["thread_id"],
                link["user_message_id"],
                summary,
                _json(
                    {
                        "schema_version": 1,
                        "runtime_run_id": lease.run_id,
                        "context_version": lease.context_version,
                        "kind": "proposal",
                        "accepted": False,
                    }
                ),
            ),
        ).lastrowid
        conn.execute(
            "UPDATE runtime_chat_links SET proposal_message_id=? WHERE run_id=?",
            (message_id, lease.run_id),
        )
        conn.execute(
            "UPDATE conversation_threads SET last_message_at=CURRENT_TIMESTAMP WHERE thread_id=?",
            (link["thread_id"],),
        )

    def claim(self, project_id, run_id, owner_id, *, lease_seconds=30) -> AttemptLease:
        with self._transaction(write=True) as conn:
            return self._claim(
                conn, project_id, run_id, owner_id, lease_seconds=lease_seconds
            )

    def _execution_subject(self, conn, row):
        """Validate a host publication's exact acceptance without reopening done; all native inference kinds retain the ordinary task gate."""
        if row["execution_kind"] == "remote_publication":
            from backend.runtime.remote_recovery import RemoteRecovery
            from backend.runtime.remote_runtime import RemotePublications

            recovery = RemoteRecovery(self)
            if recovery.observation(conn, row) is not None:
                recovery.subject(conn, row)
            else:
                RemotePublications(self).current(conn, row)
        elif row["execution_kind"] == "code_publication":
            from backend.runtime.code_publications import CodePublications
            from backend.runtime.publication_recovery import PublicationRecovery

            recovery = PublicationRecovery(self)
            if recovery.observation(conn, row) is not None:
                recovery.subject(conn, row)
            else:
                CodePublications(self).current(conn, row)
        else:
            self._task(conn, row["project_id"], row["task_id"])
            from backend.planning.execution import PlanExecutions

            PlanExecutions(self).input(conn, row)
            if conn.execute("SELECT 1 FROM runtime_project_plan_requests WHERE run_id=?", (row["id"],)).fetchone():
                from backend.planning.store import ProjectPlans

                ProjectPlans(self).current(conn, row)

    def _claim(self, conn, project_id, run_id, owner_id, *, lease_seconds=30):
        """Claim a new fenced attempt under its typed subject; publication preserves the already accepted task state."""
        text(owner_id, "owner_id", 128)
        _duration(lease_seconds)
        row = self._row(conn, project_id, run_id)
        self._execution_subject(conn, row)
        if row["status"] != "queued" or row["context_version"] != self._context(
            conn, row["task_id"]
        ):
            raise RunConflict("Run is not claimable; reconcile existing work first")
        self._bound_workspace(conn, row)
        attempt_id, fence = str(uuid4()), row["fence"] + 1
        now = self.clock()
        expires = now + lease_seconds
        conn.execute(
            "INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES(?,?,?,?,'running',?,?)",
            (attempt_id, run_id, owner_id, fence, expires, now),
        )
        conn.execute(
            "UPDATE runtime_runs SET status='running',fence=?,current_attempt_id=?,updated_at=?,issue_json=NULL WHERE id=?",
            (fence, attempt_id, now, run_id),
        )
        if row["execution_kind"] not in ("code_publication", "remote_publication"):
            conn.execute(
                "UPDATE tasks SET status='in_progress' WHERE project_id=? AND id=?",
                (project_id, row["task_id"]),
            )
        self._event(
            conn,
            project_id,
            row["task_id"],
            "run.claimed",
            {
                "run_id": run_id,
                "attempt_id": attempt_id,
                "fence": fence,
                "context_version": row["context_version"],
            },
        )
        return AttemptLease(
            run_id,
            attempt_id,
            project_id,
            row["task_id"],
            row["actor_id"],
            row["context_version"],
            owner_id,
            fence,
            expires,
        )

    def _authority(self, conn, lease, *, allow_finished=False, now=None):
        """Check original owner/fence/context and the current execution subject before granting live effect authority."""
        row = self._row(conn, lease.project_id, lease.run_id)
        actual = (
            row["current_attempt_id"],
            row["task_id"],
            row["actor_id"],
            row["context_version"],
            row["owner_id"],
            row["fence"],
            row["attempt_fence"],
        )
        expected = (
            lease.attempt_id,
            lease.task_id,
            lease.actor_id,
            lease.context_version,
            lease.owner_id,
            lease.fence,
            lease.fence,
        )
        from backend.runtime.publication_recovery import PublicationRecovery
        from backend.runtime.remote_recovery import RemoteRecovery

        readonly_observation = (PublicationRecovery.observation(conn, row) is not None
            or RemoteRecovery.observation(conn, row) is not None)
        if actual != expected or (not readonly_observation and row["context_version"] != self._context(
            conn, row["task_id"]
        )):
            raise StaleAttempt(
                "Attempt identity, fence or context is no longer current"
            )
        if allow_finished and row["attempt_status"] == "finished":
            return row
        if (
            row["status"] != "running"
            or row["attempt_status"] != "running"
            or row["lease_expires_at"] <= (self.clock() if now is None else now)
        ):
            raise StaleAttempt("Attempt authority expired or was withdrawn")
        self._execution_subject(conn, row)
        return row

    def heartbeat(self, lease: AttemptLease, *, lease_seconds=30) -> AttemptLease:
        _duration(lease_seconds)
        with self._transaction(write=True) as conn:
            self._authority(conn, lease)
            expires = self.clock() + lease_seconds
            conn.execute(
                "UPDATE runtime_attempts SET lease_expires_at=? WHERE id=?",
                (expires, lease.attempt_id),
            )
            return AttemptLease(
                lease.run_id,
                lease.attempt_id,
                lease.project_id,
                lease.task_id,
                lease.actor_id,
                lease.context_version,
                lease.owner_id,
                lease.fence,
                expires,
            )

    @staticmethod
    def _independent_review_thread(conn, lease, thread_id):
        """Reject reuse of the author's native context even under a different role/attempt."""
        row = conn.execute(
            "SELECT json_extract(snapshot_json,'$.author.thread_id') FROM finding_review_requests WHERE project_id=? AND run_id=?",
            (lease.project_id, lease.run_id),
        ).fetchone()
        if row is not None and row[0] == thread_id:
            raise RunConflict("An independent reviewer requires a new native thread")
        kind = conn.execute(
            "SELECT execution_kind FROM runtime_runs WHERE id=?", (lease.run_id,)
        ).fetchone()
        if kind is not None and kind[0] == "code_review":
            code = conn.execute(
                "SELECT author_thread_id FROM runtime_code_review_requests WHERE project_id=? AND run_id=?",
                (lease.project_id, lease.run_id),
            ).fetchone()
            if code is None or code[0] == thread_id:
                raise RunConflict(
                    "An independent code reviewer requires an admitted subject and a new native thread"
                )

    def bind_thread(self, lease, *, thread_id):
        """Persist the known thread before sending a possibly uncertain turn."""
        text(thread_id, "thread_id", 256)
        with self._transaction(write=True) as conn:
            row = self._authority(conn, lease)
            self._independent_review_thread(conn, lease, thread_id)
            if row["thread_id"] is not None:
                if row["thread_id"] != thread_id:
                    raise RunConflict(
                        "Attempt already identifies another native thread"
                    )
                return
            conn.execute(
                "UPDATE runtime_attempts SET thread_id=? WHERE id=?",
                (thread_id, lease.attempt_id),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.thread_bound",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "thread_id": thread_id,
                },
            )

    def bind_native(self, lease, *, thread_id, turn_id):
        """Bind an original turn while preserving review context independence."""
        text(thread_id, "thread_id", 256)
        text(turn_id, "turn_id", 256)
        with self._transaction(write=True) as conn:
            row = self._authority(conn, lease)
            self._independent_review_thread(conn, lease, thread_id)
            if (row["thread_id"] is not None and row["thread_id"] != thread_id) or (
                row["turn_id"] is not None and row["turn_id"] != turn_id
            ):
                raise RunConflict("Attempt already identifies another native turn")
            if (row["thread_id"], row["turn_id"]) == (thread_id, turn_id):
                return
            conn.execute(
                "UPDATE runtime_attempts SET thread_id=?,turn_id=? WHERE id=?",
                (thread_id, turn_id, lease.attempt_id),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.native_bound",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                },
            )

    def bind_grant(self, lease, grant_id):
        text(grant_id, "grant_id", 128)
        with self._transaction(write=True) as conn:
            self._authority(conn, lease)
            grant = conn.execute(
                "SELECT * FROM tool_grants WHERE id=?", (grant_id,)
            ).fetchone()
            if (
                grant is None
                or (
                    grant["project_id"],
                    grant["task_id"],
                    grant["agent_id"],
                    grant["context_version"],
                )
                != (
                    lease.project_id,
                    lease.task_id,
                    lease.actor_id,
                    lease.context_version,
                )
                or grant["revoked_at"] is not None
                or grant["expires_at"] <= self.clock()
            ):
                raise RunConflict("Grant does not match this live attempt")
            if grant["runtime_bound"]:
                if grant["runtime_attempt_id"] != lease.attempt_id:
                    raise RunConflict("Grant already belongs to another attempt")
                return
            conn.execute(
                "UPDATE tool_grants SET runtime_attempt_id=?,runtime_bound=1 WHERE id=?",
                (lease.attempt_id, grant_id),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.grant_bound",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "grant_id": grant_id,
                },
            )

    def finish(self, lease, *, native_status, summary):
        status = native_outcome(native_status)
        text(summary, "summary", 200000)
        result = {"native_status": native_status, "summary": summary}
        with self._transaction(write=True) as conn:
            row = self._authority(conn, lease, allow_finished=True)
            self._closed_peer_proof(conn, lease.attempt_id)
            if row["native_result_json"] is not None:
                if json.loads(row["native_result_json"]) != result:
                    raise RunConflict(
                        "Attempt already has a different terminal observation"
                    )
                return self._view(row)
            now = self.clock()
            conn.execute(
                "UPDATE runtime_attempts SET status='finished',native_result_json=?,ended_at=? WHERE id=?",
                (_json(result), now, lease.attempt_id),
            )
            conn.execute(
                "UPDATE runtime_runs SET status=?,updated_at=? WHERE id=?",
                (status, now, lease.run_id),
            )
            conn.execute(
                "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE runtime_attempt_id=?",
                (now, lease.attempt_id),
            )
            if native_status == "completed":
                self._deliver_proposal(conn, lease, summary)
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.finished",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "native_status": native_status,
                    "status": status,
                    "context_version": lease.context_version,
                },
            )
            return self._view(self._row(conn, lease.project_id, lease.run_id))

    @staticmethod
    def _original_attempt(conn, lease):
        attempt = conn.execute(
            """SELECT a.*,r.project_id,r.task_id,r.actor_id,r.context_version
                FROM runtime_attempts a JOIN runtime_runs r ON r.id=a.run_id
                WHERE a.id=? AND r.project_id=?""",
            (lease.attempt_id, lease.project_id),
        ).fetchone()
        if attempt is None or (
            attempt["run_id"],
            attempt["task_id"],
            attempt["actor_id"],
            attempt["context_version"],
            attempt["owner_id"],
            attempt["fence"],
        ) != (
            lease.run_id,
            lease.task_id,
            lease.actor_id,
            lease.context_version,
            lease.owner_id,
            lease.fence,
        ):
            raise StaleAttempt(
                "Observation does not identify this attempt's original owner"
            )
        return attempt

    def observe_native(self, lease, *, observation_key, native_kind, payload):
        """Retain even stale facts, without granting authority or accepting work."""
        command_key(observation_key)
        if native_kind not in (
            "turn.completed",
            "turn.failed",
            "turn.interrupted",
            "tool.started",
            "tool.completed",
            "tool.failed",
            "approval.requested",
        ) or not isinstance(payload, dict):
            raise ValueError("Unsupported native observation")
        text(_json(payload), "native payload", 32000)
        fingerprint = _digest({"native_kind": native_kind, "payload": payload})
        with self._transaction(write=True) as conn:
            attempt = self._original_attempt(conn, lease)
            for field in ("thread_id", "turn_id"):
                if (
                    attempt[field] is not None
                    and field in payload
                    and payload[field] != attempt[field]
                ):
                    raise RunConflict("Observation identifies another native turn")
            receipt = conn.execute(
                "SELECT request_hash,event_id FROM runtime_observation_receipts WHERE attempt_id=? AND observation_key=?",
                (lease.attempt_id, observation_key),
            ).fetchone()
            if receipt is not None:
                if receipt["request_hash"] != fingerprint:
                    raise RunConflict(
                        "Native observation key already identifies another fact"
                    )
                return receipt["event_id"]
            event_id = self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "native.observed",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "fence": lease.fence,
                    "context_version": lease.context_version,
                    "native_kind": native_kind,
                    "payload": payload,
                },
            )
            conn.execute(
                "INSERT INTO runtime_observation_receipts(attempt_id,observation_key,request_hash,event_id,created_at) VALUES(?,?,?,?,?)",
                (
                    lease.attempt_id,
                    observation_key,
                    fingerprint,
                    event_id,
                    self.clock(),
                ),
            )
            return event_id

    def attempt_active(self, lease) -> bool:
        with self._transaction() as conn:
            try:
                self._authority(conn, lease)
                return True
            except (StaleAttempt, RunNotFound):
                return False

    def supervise_attempt(self, lease) -> bool:
        """Fence an observed expiry atomically, so a clock correction cannot revive it."""
        with self._transaction(write=True) as conn:
            now = self.clock()
            row = self._row(conn, lease.project_id, lease.run_id)
            self._expire_current(conn, row, now)
            try:
                self._authority(conn, lease, now=now)
                return True
            except (RunConflict, RunNotFound):
                return False

    @staticmethod
    def _job_view(row):
        return CommandJob(
            job_id=row["id"],
            run_id=row["run_id"],
            attempt_id=row["attempt_id"],
            executor_id=row["executor_id"],
            operation_key=row["operation_key"],
            status=row["status"],
            workspace=row["workspace"],
            spec=CommandSpec(
                tuple(json.loads(row["argv_json"])),
                row["cwd"],
                row["timeout_seconds"],
                row["output_bytes"],
            ),
            exit_code=row["exit_code"],
            stdout=bytes(row["stdout"]),
            stderr=bytes(row["stderr"]),
            output_limited=bool(row["output_limited"]),
            cancel_requested=bool(row["cancel_requested"]),
            error=row["error"],
            peer_id=row["peer_id"],
            local_execution_closed=bool(row["local_execution_closed"]),
        )

    @staticmethod
    def _job_row(conn, project_id, job_id):
        row = conn.execute(
            """SELECT j.*,EXISTS(SELECT 1 FROM runtime_peers p WHERE p.id=j.peer_id
            AND p.attempt_id=j.attempt_id AND p.kind='command' AND p.state='closed'
            AND p.database_identity IS NOT NULL) AS local_execution_closed
            FROM runtime_jobs j JOIN runtime_runs r ON r.id=j.run_id WHERE j.id=? AND r.project_id=?""",
            (job_id, project_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Job not found in this project")
        return row

    def get_job(self, project_id, job_id) -> CommandJob:
        identity(project_id)
        text(job_id, "job_id", 128)
        with self._transaction() as conn:
            return self._job_view(self._job_row(conn, project_id, job_id))

    def command_receipt(self, lease, *, operation_key, spec: CommandSpec, workspace):
        """Read an identical intent before opening a peer; never grant stale readers.

        Owner recovery deliberately uses get_job instead. A missing receipt is
        not a reservation: reserve_job must still enforce authority atomically.
        """
        command_key(operation_key)
        fingerprint = _digest({"workspace": workspace, "spec": asdict(spec)})
        with self._transaction() as conn:
            self._authority(conn, lease)
            row = conn.execute(
                "SELECT id,request_hash FROM runtime_jobs WHERE run_id=? AND operation_key=?",
                (lease.run_id, operation_key),
            ).fetchone()
            if row is None:
                return None
            if row["request_hash"] != fingerprint:
                raise RunConflict(
                    "Command operation key already identifies another intent"
                )
            job = self._job_view(self._job_row(conn, lease.project_id, row["id"]))
            if job.attempt_id != lease.attempt_id:
                raise RunConflict("Command receipt belongs to an earlier attempt")
            return job

    def reserve_job(
        self,
        lease,
        *,
        operation_key,
        spec: CommandSpec,
        workspace,
        executor_id,
        peer_id=None,
    ) -> JobReservation:
        command_key(operation_key)
        command_key(executor_id)
        text(workspace, "workspace", 4096)
        fingerprint = _digest({"workspace": workspace, "spec": asdict(spec)})
        with self._transaction(write=True) as conn:
            self._original_attempt(conn, lease)
            existing = conn.execute(
                "SELECT * FROM runtime_jobs WHERE run_id=? AND operation_key=?",
                (lease.run_id, operation_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != fingerprint:
                    raise RunConflict(
                        "Command operation key already identifies another intent"
                    )
                return JobReservation(
                    self._job_view(
                        self._job_row(conn, lease.project_id, existing["id"])
                    ),
                    False,
                )
            active_run = self._authority(conn, lease)
            self._bound_workspace(conn, active_run, workspace)
            scope = conn.execute(
                "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=?",
                (lease.attempt_id,),
            ).fetchone()
            if peer_id is None and scope is not None:
                raise RunConflict("Command requires a registered peer")
            if peer_id is not None:
                from backend.runtime.peer_registry import PeerRegistry

                peer = conn.execute(
                    "SELECT * FROM runtime_peers WHERE id=?", (peer_id,)
                ).fetchone()
                if (
                    peer is None
                    or peer["kind"] != "command"
                    or peer["state"] != "bound"
                    or peer["attempt_id"] != lease.attempt_id
                    or peer["fence"] != lease.fence
                ):
                    raise RunConflict("Command requires its own bound peer")
                PeerRegistry(self)._check_origin(peer)
            if (
                conn.execute(
                    "SELECT id FROM runtime_jobs WHERE run_id=? AND status IN ('dispatching','cancelling','unknown')",
                    (lease.run_id,),
                ).fetchone()
                is not None
            ):
                raise RunConflict(
                    "An existing command must terminate or be reconciled first"
                )
            job_id = str(uuid4())
            conn.execute(
                """INSERT INTO runtime_jobs(id,run_id,attempt_id,executor_id,operation_key,request_hash,argv_json,cwd,workspace,timeout_seconds,output_bytes,status,created_at,peer_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,'dispatching',?,?)""",
                (
                    job_id,
                    lease.run_id,
                    lease.attempt_id,
                    executor_id,
                    operation_key,
                    fingerprint,
                    _json(spec.argv),
                    spec.cwd,
                    workspace,
                    spec.timeout_seconds,
                    spec.output_bytes,
                    self.clock(),
                    peer_id,
                ),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "job.dispatching",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "job_id": job_id,
                    "executor_id": executor_id,
                },
            )
            return JobReservation(
                self._job_view(self._job_row(conn, lease.project_id, job_id)), True
            )

    def _owned_job(self, conn, lease, job_id):
        self._original_attempt(conn, lease)
        row = self._job_row(conn, lease.project_id, job_id)
        if row["run_id"] != lease.run_id or row["attempt_id"] != lease.attempt_id:
            raise RunNotFound("Job does not belong to this attempt")
        return row

    def cancel_job(self, lease, job_id) -> CommandJob:
        with self._transaction(write=True) as conn:
            row = self._owned_job(conn, lease, job_id)
            if row["status"] == "exited" or row["cancel_requested"]:
                return self._job_view(row)
            status = "unknown" if row["status"] == "unknown" else "cancelling"
            conn.execute(
                "UPDATE runtime_jobs SET cancel_requested=1,status=? WHERE id=?",
                (status, job_id),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "job.cancel_requested",
                {
                    "job_id": job_id,
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                },
            )
            return self._job_view(self._job_row(conn, lease.project_id, job_id))

    def finish_job(
        self,
        lease,
        job_id,
        *,
        executor_id,
        exit_code,
        stdout,
        stderr,
        output_limited,
        error=None,
    ) -> CommandJob:
        if exit_code is not None and type(exit_code) is not int:
            raise ValueError("Command exit code must be an integer or unknown")
        if (
            not isinstance(stdout, bytes)
            or not isinstance(stderr, bytes)
            or type(output_limited) is not bool
        ):
            raise ValueError("Expected bounded binary command output")
        if error is not None:
            text(error, "command error", 1000)
        if exit_code is None and error is None:
            raise ValueError("An uncertain command requires an explicit error")
        with self._transaction(write=True) as conn:
            row = self._owned_job(conn, lease, job_id)
            if row["executor_id"] != executor_id:
                raise RunConflict("Job belongs to another native connection")
            if max(len(stdout), len(stderr)) > row["output_bytes"]:
                raise ValueError("Command output exceeds its declared stream budget")
            if row["status"] == "exited":
                if (
                    row["exit_code"],
                    bytes(row["stdout"]),
                    bytes(row["stderr"]),
                    bool(row["output_limited"]),
                    row["error"],
                ) != (exit_code, stdout, stderr, output_limited, error):
                    raise RunConflict("Job already has another terminal receipt")
                return self._job_view(row)
            if not stdout.startswith(bytes(row["stdout"])) or not stderr.startswith(
                bytes(row["stderr"])
            ):
                raise RunConflict("Observed output cannot replace an earlier prefix")
            status = "unknown" if exit_code is None else "exited"
            conn.execute(
                "UPDATE runtime_jobs SET status=?,exit_code=?,stdout=?,stderr=?,output_limited=?,error=?,ended_at=? WHERE id=?",
                (
                    status,
                    exit_code,
                    stdout,
                    stderr,
                    int(output_limited),
                    error,
                    self.clock() if exit_code is not None else None,
                    job_id,
                ),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "job.observed",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "job_id": job_id,
                    "status": status,
                    "exit_code": exit_code,
                    "output_limited": output_limited,
                },
            )
            if exit_code is None:
                run = self._row(conn, lease.project_id, lease.run_id)
                if run["current_attempt_id"] == lease.attempt_id and (
                    (run["status"] == "running" and run["fence"] == lease.fence)
                    or run["status"] == "cancelling"
                ):
                    self._withdraw(conn, run, "reconciling")
                    self._event(
                        conn,
                        lease.project_id,
                        lease.task_id,
                        "run.effects_uncertain",
                        {
                            "run_id": lease.run_id,
                            "attempt_id": lease.attempt_id,
                            "job_id": job_id,
                        },
                    )
            return self._job_view(self._job_row(conn, lease.project_id, job_id))

    def _withdraw(self, conn, row, status, *, cancel_requested=None):
        now = self.clock()
        conn.execute(
            "UPDATE runtime_runs SET status=?,fence=fence+1,updated_at=?,cancel_requested=COALESCE(?,cancel_requested) WHERE id=?",
            (status, now, cancel_requested, row["id"]),
        )
        if row["current_attempt_id"] is not None and row["attempt_status"] == "running":
            conn.execute(
                "UPDATE runtime_attempts SET status='reconciling' WHERE id=?",
                (row["current_attempt_id"],),
            )
        conn.execute(
            "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE runtime_attempt_id=?",
            (now, row["current_attempt_id"]),
        )

    def cancel(self, project_id, run_id):
        """Withdraw one original run through the existing transaction; labels never prove its physical closure."""
        with self._transaction(write=True) as conn:
            return self._cancel(conn, project_id, run_id)

    def _cancel(self, conn, project_id, run_id):
        """Reuse exact original cancellation/fence/grant/question/event semantics in an atomic observed-project Stop decision."""
        row = self._row(conn, project_id, run_id)
        if row["cancel_requested"]:
            return self._view(row)
        status = cancel_outcome(row["status"])
        if row["status"] in ("failed", "cancelled", "superseded"):
            return self._view(row)
        self._withdraw(conn, row, status, cancel_requested=1)
        conn.execute(
            "UPDATE user_requests SET status='expired' WHERE status='pending' AND id IN (SELECT request_id FROM runtime_question_links WHERE project_id=? AND run_id=?)",
            (project_id, run_id),
        )
        self._event(
            conn,
            project_id,
            row["task_id"],
            "run.cancel_requested",
            {
                "run_id": run_id,
                "attempt_id": row["current_attempt_id"],
                "status": status,
            },
        )
        return self._view(self._row(conn, project_id, run_id))

    def expire(self, project_id, run_id) -> bool:
        with self._transaction(write=True) as conn:
            row = self._row(conn, project_id, run_id)
            return self._expire_current(conn, row, self.clock())

    def _expire_current(self, conn, row, now):
        if (
            row["status"] != "running"
            or row["lease_expires_at"] is None
            or row["lease_expires_at"] > now
        ):
            return False
        self._withdraw(conn, row, "reconciling")
        self._event(
            conn,
            row["project_id"],
            row["task_id"],
            "run.authority_expired",
            {
                "run_id": row["id"],
                "attempt_id": row["current_attempt_id"],
            },
        )
        return True

    def _advance_context(
        self,
        conn,
        *,
        project_id,
        task_id,
        expected_version,
        statement,
        source_kind,
        source_reference,
    ):
        """Advance owner/evidence context and reopen a previously accepted version without erasing history."""
        task = self._existing_task(conn, project_id, task_id)
        if self._context(conn, task_id) != expected_version:
            raise RunConflict(
                "Context changed; reconcile the correction against its current version"
            )
        if (
            task["status"] == "done"
            and (conn.execute(
                "SELECT 1 FROM runtime_result_acceptances a JOIN runtime_result_proposals p ON p.id=a.proposal_id WHERE a.project_id=? AND a.task_id=? AND p.context_version=? LIMIT 1",
                (project_id, task_id, expected_version),
            ).fetchone() or (
                conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_code_acceptances'").fetchone()
                and conn.execute("SELECT 1 FROM runtime_code_acceptances WHERE project_id=? AND task_id=? AND context_version=? LIMIT 1", (project_id, task_id, expected_version)).fetchone()
            ))
        ):
            conn.execute(
                "UPDATE tasks SET status='pending',completed_at=NULL WHERE project_id=? AND id=?",
                (project_id, task_id),
            )
        elif task["status"] in ("done", "cancelled", "failed"):
            raise RunConflict("Task no longer accepts context corrections")
        version, now = expected_version + 1, self.clock()
        conn.execute(
            "INSERT INTO task_contexts(task_id,version) VALUES(?,?) ON CONFLICT(task_id) DO UPDATE SET version=excluded.version",
            (task_id, version),
        )
        conn.execute(
            "INSERT INTO runtime_context_revisions(project_id,task_id,version,statement,source_kind,source_reference,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                project_id,
                task_id,
                version,
                statement,
                source_kind,
                source_reference,
                now,
            ),
        )
        runs = conn.execute(
            "SELECT id FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
            (project_id, task_id),
        ).fetchall()
        for run in runs:
            row = self._row(conn, project_id, run["id"])
            self._withdraw(conn, row, invalidated_outcome(row["status"]))
        conn.execute(
            "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE project_id=? AND task_id=?",
            (now, project_id, task_id),
        )
        self._event(
            conn,
            project_id,
            task_id,
            "context.corrected",
            {
                "version": version,
                "previous_version": expected_version,
                "source_kind": source_kind,
                "source_reference": source_reference,
            },
        )
        conn.execute(
            """UPDATE user_requests SET status='expired' WHERE status='pending' AND id IN
            (SELECT q.request_id FROM runtime_question_links q JOIN runtime_runs r ON r.id=q.run_id
             WHERE q.project_id=? AND r.task_id=? AND q.context_version<?)""",
            (project_id, task_id, version),
        )
        return version

    def correct_context(
        self,
        *,
        project_id,
        task_id,
        expected_version,
        operation_key,
        statement,
        source_kind,
        source_reference,
    ):
        validate_correction(
            project_id=project_id,
            task_id=task_id,
            expected_version=expected_version,
            operation_key=operation_key,
            statement=statement,
            source_kind=source_kind,
            source_reference=source_reference,
        )
        intent = self._correction_intent(
            {
                "project_id": project_id,
                "task_id": task_id,
                "expected_version": expected_version,
                "operation_key": operation_key,
                "statement": statement,
                "source_kind": source_kind,
                "source_reference": source_reference,
            }
        )
        with self._transaction(write=True) as conn:
            receipt = self._receipt(conn, project_id, task_id, operation_key, intent)
            if receipt is not None:
                return receipt["version"]
            version = self._advance_context(
                conn,
                project_id=project_id,
                task_id=task_id,
                expected_version=expected_version,
                statement=statement,
                source_kind=source_kind,
                source_reference=source_reference,
            )
            self._save_receipt(
                conn, project_id, task_id, operation_key, intent, {"version": version}
            )
            return version

    def events(self, project_id, *, after_id=0, limit=100) -> EventPage:
        identity(project_id)
        if (
            type(after_id) is not int
            or after_id < 0
            or type(limit) is not int
            or not 1 <= limit <= 200
        ):
            raise ValueError("Invalid event cursor or page size")
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM events_log WHERE project_id=? AND id>? ORDER BY id ASC LIMIT ?",
                (project_id, after_id, limit + 1),
            ).fetchall()
            page = tuple(
                RunEvent(
                    row["id"],
                    row["project_id"],
                    row["entity_type"],
                    row["entity_id"],
                    row["event_type"],
                    row["event_source"],
                    json.loads(row["event_data_json"]),
                    row["created_at"],
                )
                for row in rows[:limit]
            )
            return EventPage(
                page, page[-1].event_id if page else after_id, len(rows) > limit
            )
