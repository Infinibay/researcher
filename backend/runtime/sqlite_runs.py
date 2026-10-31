"""Host-owned execution identity and transactions; no inference or job replay.

This adapter persists admission, authority and observations. It does not run a
model, mint a business grant, prove remote job termination, accept a result or
publish. Those use cases must build on these identities rather than bypass them.
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
    cancel_outcome,
    command_key,
    identity,
    invalidated_outcome,
    native_outcome,
    text,
    validate_correction,
)


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
    def __init__(self, database: str | Path, *, clock: Callable[[], float] = time.time):
        self.database = str(database)
        self.clock = clock

    @contextmanager
    def _transaction(self, *, write=False):
        with closing(connect(self.database)) as conn, conn:
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
        row = SQLiteRunStore._existing_task(conn, project_id, task_id)
        if row["status"] in ("done", "cancelled", "failed"):
            raise RunConflict("Task no longer admits execution")
        return row

    @staticmethod
    def _context(conn, task_id):
        row = conn.execute(
            "SELECT version FROM task_contexts WHERE task_id=?", (task_id,)
        ).fetchone()
        return row[0] if row is not None else 1

    @staticmethod
    def _row(conn, project_id, run_id):
        identity(project_id)
        text(run_id, "run_id", 128)
        row = conn.execute(
            """SELECT r.*,a.thread_id,a.turn_id,a.owner_id,a.status AS attempt_status,
            a.lease_expires_at,a.native_result_json,a.fence AS attempt_fence,
            chat.thread_id AS conversation_thread_id,dispatch.model AS dispatch_model
            FROM runtime_runs r LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id
            LEFT JOIN runtime_chat_links chat ON chat.run_id=r.id
            LEFT JOIN runtime_inference_dispatches dispatch ON dispatch.attempt_id=a.id
            WHERE r.project_id=? AND r.id=?""",
            (project_id, run_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Run not found in this project")
        return row

    @staticmethod
    def _view(row):
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
            self._existing_task(conn, project_id, task_id)
            task = conn.execute(
                "SELECT title,description,type,status FROM tasks WHERE project_id=? AND id=?",
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
        with self._transaction(write=True) as conn:
            row = self._authority(conn, lease)
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
                    raise RunConflict(
                        "Attempt already reserved another inference intent"
                    )
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
                raise RunConflict(
                    "Project work budget exhausted; no native turn was sent"
                )
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
            unknown_job = conn.execute(
                "SELECT id FROM runtime_jobs WHERE attempt_id=? AND status IN ('dispatching','cancelling','unknown')",
                (lease.attempt_id,),
            ).fetchone()
            if unknown_job is not None:
                raise RunConflict("Owned jobs require terminal reconciliation")
            self._withdraw(conn, row, outcome)
            conn.execute(
                "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
                (self.clock(), lease.attempt_id),
            )
            conn.execute(
                "UPDATE runtime_inference_dispatches SET status='unknown' WHERE attempt_id=? AND status='reserved'",
                (lease.attempt_id,),
            )
            self._event(
                conn,
                lease.project_id,
                lease.task_id,
                "run.peers_retired",
                {
                    "run_id": lease.run_id,
                    "status": outcome,
                    "native_and_business_closed": True,
                },
            )
            return self._view(self._row(conn, lease.project_id, lease.run_id))

    @staticmethod
    def _admission_intent(spec, conversation_thread):
        intent = {"kind": "admit", **asdict(spec)}
        if conversation_thread is not None:
            command_key(conversation_thread)
            intent["conversation_thread"] = conversation_thread
        return intent

    def admission_receipt(self, spec, *, conversation_thread=None):
        intent = self._admission_intent(spec, conversation_thread)
        with self._transaction() as conn:
            receipt = self._receipt(
                conn, spec.project_id, spec.task_id, spec.operation_key, intent
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

    def admit(self, spec: RunSpec, *, conversation_thread=None) -> RunView:
        intent = self._admission_intent(spec, conversation_thread)
        with self._transaction(write=True) as conn:
            receipt = self._receipt(
                conn, spec.project_id, spec.task_id, spec.operation_key, intent
            )
            if receipt is not None:
                return self._view(self._row(conn, spec.project_id, receipt["run_id"]))
            self._task(conn, spec.project_id, spec.task_id)
            if self._context(conn, spec.task_id) != spec.context_version:
                raise RunConflict("Run context is already obsolete")
            active = conn.execute(
                "SELECT id FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','needs_review')",
                (spec.project_id, spec.task_id),
            ).fetchone()
            if active is not None:
                raise RunConflict("Task already has active or unreconciled work")
            conn.execute(
                "INSERT OR IGNORE INTO task_contexts(task_id,version) VALUES(?,1)",
                (spec.task_id,),
            )
            run_id = str(uuid4())
            now = self.clock()
            conn.execute(
                """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,'queued',?,?)""",
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
            if conversation_thread is not None:
                self._attach_conversation(conn, spec, run_id, conversation_thread)
            self._save_receipt(
                conn,
                spec.project_id,
                spec.task_id,
                spec.operation_key,
                intent,
                {"run_id": run_id},
            )
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
            return self._view(self._row(conn, spec.project_id, run_id))

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
        text(owner_id, "owner_id", 128)
        _duration(lease_seconds)
        with self._transaction(write=True) as conn:
            row = self._row(conn, project_id, run_id)
            self._task(conn, project_id, row["task_id"])
            if row["status"] != "queued" or row["context_version"] != self._context(
                conn, row["task_id"]
            ):
                raise RunConflict("Run is not claimable; reconcile existing work first")
            attempt_id, fence = str(uuid4()), row["fence"] + 1
            now = self.clock()
            expires = now + lease_seconds
            conn.execute(
                "INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES(?,?,?,?,'running',?,?)",
                (attempt_id, run_id, owner_id, fence, expires, now),
            )
            conn.execute(
                "UPDATE runtime_runs SET status='running',fence=?,current_attempt_id=?,updated_at=? WHERE id=?",
                (fence, attempt_id, now, run_id),
            )
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
        if actual != expected or row["context_version"] != self._context(
            conn, row["task_id"]
        ):
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
        self._task(conn, lease.project_id, lease.task_id)
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

    def bind_thread(self, lease, *, thread_id):
        """Persist the known thread before sending a possibly uncertain turn."""
        text(thread_id, "thread_id", 256)
        with self._transaction(write=True) as conn:
            row = self._authority(conn, lease)
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
        text(thread_id, "thread_id", 256)
        text(turn_id, "turn_id", 256)
        with self._transaction(write=True) as conn:
            row = self._authority(conn, lease)
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
        )

    @staticmethod
    def _job_row(conn, project_id, job_id):
        row = conn.execute(
            "SELECT j.* FROM runtime_jobs j JOIN runtime_runs r ON r.id=j.run_id WHERE j.id=? AND r.project_id=?",
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

    def reserve_job(
        self, lease, *, operation_key, spec: CommandSpec, workspace, executor_id
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
                return JobReservation(self._job_view(existing), False)
            self._authority(conn, lease)
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
                """INSERT INTO runtime_jobs(id,run_id,attempt_id,executor_id,operation_key,request_hash,argv_json,cwd,workspace,timeout_seconds,output_bytes,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,'dispatching',?)""",
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
        with self._transaction(write=True) as conn:
            row = self._row(conn, project_id, run_id)
            if row["cancel_requested"]:
                return self._view(row)
            status = cancel_outcome(row["status"])
            if row["status"] in ("failed", "cancelled", "superseded"):
                return self._view(row)
            self._withdraw(conn, row, status, cancel_requested=1)
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
            self._task(conn, project_id, task_id)
            if self._context(conn, task_id) != expected_version:
                raise RunConflict(
                    "Context changed; reconcile the correction against its current version"
                )
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
                "SELECT id FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','needs_review')",
                (project_id, task_id),
            ).fetchall()
            for run in runs:
                row = self._row(conn, project_id, run["id"])
                self._withdraw(conn, row, invalidated_outcome(row["status"]))
            conn.execute(
                "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE project_id=? AND task_id=?",
                (now, project_id, task_id),
            )
            self._save_receipt(
                conn, project_id, task_id, operation_key, intent, {"version": version}
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
