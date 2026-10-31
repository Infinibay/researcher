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
    EventPage,
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
    def _task(conn, project_id, task_id):
        identity(project_id)
        identity(task_id)
        row = conn.execute(
            "SELECT status FROM tasks WHERE project_id=? AND id=?",
            (project_id, task_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Task not found in this project")
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
            a.lease_expires_at,a.native_result_json,a.fence AS attempt_fence
            FROM runtime_runs r LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id
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

    def admit(self, spec: RunSpec) -> RunView:
        intent = {"kind": "admit", **asdict(spec)}
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

    def _authority(self, conn, lease, *, allow_finished=False):
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
            or row["lease_expires_at"] <= self.clock()
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
            if row["status"] != "running" or row["lease_expires_at"] > self.clock():
                return False
            self._withdraw(conn, row, "reconciling")
            self._event(
                conn,
                project_id,
                row["task_id"],
                "run.authority_expired",
                {"run_id": run_id, "attempt_id": row["current_attempt_id"]},
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
        identity(expected_version)
        command_key(operation_key)
        text(statement, "statement", 50000)
        text(source_reference, "source_reference", 1200)
        if source_kind not in (
            "user_message",
            "user_example",
            "tool_evidence",
            "assumption",
        ):
            raise ValueError("Unknown context source kind")
        intent = {
            "kind": "correct_context",
            "project_id": project_id,
            "task_id": task_id,
            "expected_version": expected_version,
            "statement": statement,
            "source_kind": source_kind,
            "source_reference": source_reference,
        }
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
