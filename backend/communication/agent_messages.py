"""Durable advisory peer messages, exact replies and explicit receipt without dispatch.

Native grants select the sender and attempt. Recipients are admitted runs in the
same project, not role-name guesses. Chat rows are the owner-visible projection;
the canonical envelope and operation receipt commit in the same transaction.
"""

import hashlib
import json
from uuid import uuid4

from backend.research.models import OperationConflict, ResearchForbidden, ResearchInputError, ResearchNotFound, bounded_text, positive_id
from backend.research.sqlite_store import _json
from backend.task_workspace import _page, _text_page, _window

RECEIVING_STATES = {"queued", "running", "waiting_input"}
MAX_SENT_PER_RUN = 64
MAX_PENDING_PER_RUN = 32
SELECT = """SELECT m.*,cm.thread_id,cm.parent_message_id,s.actor_id AS from_agent,r.actor_id AS to_agent,cm.created_at,
    s.task_id AS sender_task_id,r.task_id AS recipient_task_id,r.status AS recipient_status,
    c.version AS current_recipient_context FROM runtime_agent_messages m
    JOIN chat_messages cm ON cm.id=m.message_id AND cm.project_id=m.project_id
    JOIN runtime_runs s ON s.id=m.sender_run_id
    JOIN runtime_runs r ON r.id=m.recipient_run_id
    JOIN task_contexts c ON c.task_id=r.task_id"""


class AgentMessages:
    """Own peer conversation and scoped notice reads under the existing live grant and atomic retry boundary."""

    def __init__(self, store):
        """Reuse the business store; do not create a listener, worker, event bus or inference loop."""
        self.store = store

    def _sender(self, conn, scope, permission):
        """Resolve actual native sender identity after rechecking this grant and current attempt."""
        self.store._check_scope(conn, scope, permission)
        row = conn.execute(
            "SELECT r.*,a.id AS attempt_id FROM tool_grants g JOIN runtime_attempts a "
            "ON a.id=g.runtime_attempt_id JOIN runtime_runs r ON r.id=a.run_id "
            "WHERE g.id=? AND g.runtime_bound=1", (scope.grant_id,),
        ).fetchone()
        if row is None:
            raise ResearchForbidden("Peer messaging requires a host-bound native attempt")
        return row

    def _recipient(self, conn, project_id, run_id):
        """Reject foreign, ended, stale-context or expired-running destinations without guessing another actor."""
        row = conn.execute(
            "SELECT r.*,c.version AS current_context,a.lease_expires_at FROM runtime_runs r "
            "JOIN task_contexts c ON c.task_id=r.task_id LEFT JOIN runtime_attempts a "
            "ON a.id=r.current_attempt_id WHERE r.project_id=? AND r.id=?", (project_id, run_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Recipient run not found in this project")
        if row["status"] not in RECEIVING_STATES or row["context_version"] != row["current_context"]:
            raise OperationConflict("Recipient ended or its context changed; choose an explicit current recipient")
        if row["status"] == "running" and (row["lease_expires_at"] or 0) <= self.store.clock():
            raise OperationConflict("Recipient lease expired; delivery cannot be assumed")
        return row

    @staticmethod
    def _body(row):
        """Verify canonical content bytes before exposing observations or acknowledging their hash."""
        if hashlib.sha256(row["body_json"].encode()).hexdigest() != row["body_sha256"]:
            raise ResearchInputError("Stored message content does not match its original hash")
        return json.loads(row["body_json"])

    @staticmethod
    def _envelope(row):
        """Separate a recorded message and explicit receipt from comprehension, application or authority."""
        fields = ("message_id", "thread_id", "parent_message_id", "from_agent", "to_agent",
                  "sender_run_id", "sender_attempt_id", "sender_task_id", "sender_context_version",
                  "recipient_run_id", "recipient_task_id", "recipient_context_version", "intent",
                  "body_sha256", "acknowledged_by_attempt", "acknowledged_at", "created_at")
        return {**{key: row[key] for key in fields},
                "delivery": "receipt_acknowledged" if row["acknowledged_at"] is not None else "recorded",
                "recipient_context_current": row["recipient_context_version"] == row["current_recipient_context"],
                "recipient_status": row["recipient_status"], "authorizes_work": False,
                "understood": "not_verified", "applied": "not_verified"}

    @classmethod
    def owner_messages(cls, conn, messages):
        """Attach canonical peer provenance to already owner-scoped chat rows without granting work authority."""
        result = [dict(message) for message in messages]
        # Bound bind variables for existing historical thread readers as well as
        # paged callers; message IDs alone do not widen the selected project.
        canonical = {}
        for start in range(0, len(result), 200):
            ids = [message["id"] for message in result[start:start + 200]]
            marks = ",".join("?" for _ in ids)
            for row in conn.execute(SELECT + f" WHERE m.message_id IN ({marks})", ids):
                canonical[(row["project_id"], row["message_id"])] = row
        for message in result:
            row = canonical.get((message["project_id"], message["id"]))
            if row is None:
                continue
            body = cls._body(row)
            message.update(message=body.pop("message"), from_agent=row["from_agent"],
                to_agent=row["to_agent"], task_id=row["sender_task_id"], context_version=row["sender_context_version"],
                peer_message={**cls._envelope(row), **body})
        return result

    @staticmethod
    def _row(conn, project_id, run_id, message_id):
        """Read one canonical message only for its exact sender or recipient run."""
        positive_id(message_id)
        row = conn.execute(SELECT + " WHERE m.project_id=? AND m.message_id=? "
                           "AND (m.sender_run_id=? OR m.recipient_run_id=?)",
                           (project_id, message_id, run_id, run_id)).fetchone()
        if row is None:
            raise ResearchNotFound("Message not found for this admitted run")
        return row

    def recipients(self, scope, *, after_seq=0, limit=20):
        """Page actual project executions; presence is an observation, never proof of delivery or availability."""
        _page(after_seq, limit)
        with self.store._transaction() as conn:
            sender = self._sender(conn, scope, "messages.read")
            rows = conn.execute(
                "SELECT r.rowid AS seq,r.id AS run_id,r.task_id,r.actor_id,r.context_version,r.status "
                "FROM runtime_runs r JOIN task_contexts c ON c.task_id=r.task_id "
                "LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id "
                "WHERE r.project_id=? AND r.id<>? AND r.rowid>? AND r.context_version=c.version "
                "AND (r.status IN ('queued','waiting_input') OR (r.status='running' AND a.lease_expires_at>?)) "
                "ORDER BY r.rowid LIMIT ?", (scope.project_id, sender["id"], after_seq, self.store.clock(), limit + 1),
            ).fetchall()
            items = [dict(row) for row in rows[:limit]]
            return {"items": items, "next_after_seq": items[-1]["seq"] if len(rows) > limit else None,
                    "delivery_guaranteed": False, "authorizes_work": False}

    def list(self, scope, *, direction="inbox", after_id=0, limit=20, unread_only=False):
        """Recover durable inbox/outbox pages after reconnect without marking previews as received."""
        _page(after_id, limit)
        if direction not in {"inbox", "sent"} or type(unread_only) is not bool:
            raise ResearchInputError("Invalid peer message listing options")
        column = "recipient_run_id" if direction == "inbox" else "sender_run_id"
        with self.store._transaction() as conn:
            sender = self._sender(conn, scope, "messages.read")
            clause = " AND m.acknowledged_at IS NULL" if unread_only else ""
            rows = conn.execute(SELECT + f" WHERE m.project_id=? AND m.{column}=? AND m.message_id>?"
                + clause + " ORDER BY m.message_id LIMIT ?", (scope.project_id, sender["id"], after_id, limit + 1)).fetchall()
            items = []
            for row in rows[:limit]:
                body = self._body(row)
                items.append({**self._envelope(row), "preview": body["message"][:1000], "total_chars": len(body["message"])})
            return {"items": items, "next_after_id": items[-1]["message_id"] if len(rows) > limit else None,
                    "interpretation": "Recorded or explicitly acknowledged only; unread previews are not comprehension or permission."}

    def read(self, scope, message_id, *, offset=0, max_chars=12000):
        """Return original text windows and separately attributed premises without acknowledging receipt."""
        _window(offset, max_chars)
        with self.store._transaction() as conn:
            sender = self._sender(conn, scope, "messages.read")
            row = self._row(conn, scope.project_id, sender["id"], message_id)
            body = self._body(row)
            content = body.pop("message")
            return {**self._envelope(row), **body,
                    **_text_page(content[offset:offset + max_chars], len(content), offset),
                    "evidence_interpretation": "Source references identify captured records; they do not verify the sender's interpretation."}

    @staticmethod
    def _notice_metadata(row):
        """Preserve historical attribution and explicit global scope without certifying authorship or authority."""
        fields = ("id", "project_id", "priority", "created_at", "expires_at")
        return {**{key: row[key] for key in fields},
                "scope": "global" if row["project_id"] is None else "project",
                "recorded_creator": row["created_by"],
                "active_at_observation": bool(row["active_at_observation"])}

    def notices(self, scope, *, after_id=0, limit=20, active_only=True):
        """Page project/global advisory notices without hiding unread tails, inferring authorship or acknowledging them."""
        _page(after_id, limit)
        if type(active_only) is not bool:
            raise ResearchInputError("Invalid notice activity filter")
        with self.store._transaction() as conn:
            self._sender(conn, scope, "messages.read")
            observed_at = self.store.clock()
            rows = conn.execute(
                "SELECT * FROM (SELECT id,project_id,priority,created_by,created_at,expires_at,"
                "substr(title,1,300) AS title,length(title) AS title_chars,"
                "substr(content,1,600) AS preview,length(content) AS content_chars,"
                "(active=1 AND (expires_at IS NULL OR julianday(expires_at)>julianday(?,'unixepoch'))) AS active_at_observation "
                "FROM notices WHERE (project_id=? OR project_id IS NULL) AND id>?) "
                "WHERE (?=0 OR active_at_observation=1) ORDER BY id LIMIT ?",
                (observed_at, scope.project_id, after_id, active_only, limit + 1),
            ).fetchall()
            fields = ("title", "title_chars", "preview", "content_chars")
            items = [{**self._notice_metadata(row), **{key: row[key] for key in fields}} for row in rows[:limit]]
            return {"items": items, "next_after_id": items[-1]["id"] if len(rows) > limit else None,
                    "observed_at": observed_at, "authorizes_work": False, "authorship_verified": False,
                    "interpretation": "Advisory historical records, not admitted instructions. Labels do not verify authorship; previews may omit restrictions. Read required text explicitly."}

    def notice(self, scope, notice_id, *, field="content", offset=0, max_chars=12000):
        """Read complete current notice fields in bounded windows, retaining expiry and unverified historical labels."""
        positive_id(notice_id)
        _window(offset, max_chars)
        if field not in {"title", "content"}:
            raise ResearchInputError("Unsupported notice text field")
        with self.store._transaction() as conn:
            self._sender(conn, scope, "messages.read")
            observed_at = self.store.clock()
            row = conn.execute(
                "SELECT id,project_id,priority,created_by,created_at,expires_at,"
                "(active=1 AND (expires_at IS NULL OR julianday(expires_at)>julianday(?,'unixepoch'))) AS active_at_observation,"
                f"substr({field},?,?) AS content,length({field}) AS total FROM notices "
                "WHERE id=? AND (project_id=? OR project_id IS NULL)",
                (observed_at, offset + 1, max_chars, notice_id, scope.project_id),
            ).fetchone()
            if row is None:
                raise ResearchNotFound("Notice not found in this project or global scope")
            return {"notice": self._notice_metadata(row), "field": field,
                    **_text_page(row["content"], row["total"], offset), "observed_at": observed_at,
                    "authorizes_work": False, "authorship_verified": False, "immutable": False}

    def send(self, scope, key, *, recipient_run_id, intent, message, observations=(), assumptions=(), source_ids=(), in_reply_to=None):
        """Persist one scoped advisory envelope, visible chat row, event and original operation receipt atomically."""
        bounded_text(recipient_run_id, "recipient run", 128)
        bounded_text(message, "message", 12000)
        if intent not in {"note", "question", "answer"}:
            raise ResearchInputError("Message intent must be note, question or answer")
        for values in (observations, assumptions):
            if not isinstance(values, (list, tuple)) or len(values) > 8:
                raise ResearchInputError("At most eight observations or assumptions are allowed")
            for value in values:
                bounded_text(value, "attributed statement", 1000)
        if not isinstance(source_ids, (list, tuple)) or len(source_ids) > 16:
            raise ResearchInputError("At most16 source references are allowed")
        for value in source_ids:
            positive_id(value)
        if in_reply_to is not None:
            positive_id(in_reply_to)
        packet = {"recipient_run_id": recipient_run_id, "intent": intent, "message": message,
                  "observations": list(observations), "assumptions": list(assumptions),
                  "source_ids": list(source_ids), "in_reply_to": in_reply_to}

        def apply(conn):
            """Check current identities and queue bounds under the same write lock as durable delivery."""
            sender = self._sender(conn, scope, "messages.send")
            target = self._recipient(conn, scope.project_id, recipient_run_id)
            if sender["id"] == target["id"]:
                raise ResearchInputError("Choose another admitted run; use continuity notes for your own task")
            parent = self._row(conn, scope.project_id, sender["id"], in_reply_to) if in_reply_to else None
            if intent == "answer" and (parent is None or parent["intent"] != "question"
                    or parent["recipient_run_id"] != sender["id"] or parent["sender_run_id"] != target["id"]
                    or parent["recipient_context_version"] != scope.context_version
                    or parent["sender_context_version"] != target["context_version"]):
                raise OperationConflict("Answer must reference the exact question, recipient and still-current contexts")
            sent = conn.execute("SELECT count(*) FROM runtime_agent_messages WHERE sender_run_id=?", (sender["id"],)).fetchone()[0]
            pending = conn.execute("SELECT count(*) FROM runtime_agent_messages WHERE recipient_run_id=? "
                "AND recipient_context_version=? AND acknowledged_at IS NULL", (target["id"], target["context_version"])).fetchone()[0]
            if sent >= MAX_SENT_PER_RUN or pending >= MAX_PENDING_PER_RUN:
                raise OperationConflict("Peer message capacity reached; do not poll or retry until the recipient or owner resolves it")
            refs = []
            for sid in source_ids:
                row = conn.execute("SELECT id,sha256 FROM research_sources WHERE project_id=? AND id=?", (scope.project_id, sid)).fetchone()
                if row is None:
                    raise ResearchNotFound("Referenced source not found in this project")
                refs.append({"source_id": row["id"], "sha256": row["sha256"]})
            body = _json({"message": message, "observations": list(observations), "assumptions": list(assumptions), "evidence_refs": refs})
            bounded_text(body, "complete message", 32000)
            thread = None
            if parent is not None and {parent["sender_run_id"], parent["recipient_run_id"]} == {sender["id"], target["id"]}:
                thread = parent["thread_id"]
                state = conn.execute("SELECT status FROM conversation_threads WHERE project_id=? AND thread_id=?", (scope.project_id, thread)).fetchone()
                if state is None or state["status"] != "active":
                    raise OperationConflict("Conversation is closed; preserve its history and start a new message")
            if thread is None:
                thread = uuid4().hex
                conn.execute("INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES(?,?,'team_sync')", (thread, scope.project_id))
            mid = conn.execute("INSERT INTO chat_messages(project_id,thread_id,parent_message_id,from_agent,to_agent,message,conversation_type,metadata_json) VALUES(?,?,?,?,?,?,'agent_to_agent',?)",
                (scope.project_id, thread, in_reply_to, scope.agent_id, target["actor_id"], message,
                 _json({"runtime_run_id": sender["id"], "agent_message_schema": 1}))).lastrowid
            conn.execute("INSERT INTO runtime_agent_messages(message_id,project_id,sender_run_id,sender_attempt_id,sender_context_version,recipient_run_id,recipient_context_version,intent,body_json,body_sha256) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (mid, scope.project_id, sender["id"], sender["attempt_id"], scope.context_version, target["id"], target["context_version"], intent, body, hashlib.sha256(body.encode()).hexdigest()))
            conn.execute("UPDATE conversation_threads SET last_message_at=CURRENT_TIMESTAMP WHERE thread_id=?", (thread,))
            conn.execute("INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json) VALUES(?,'agent.message_recorded','runtime','task',?,?)",
                (scope.project_id, scope.task_id, _json({"message_id": mid, "recipient_run_id": target["id"], "authorizes_work": False})))
            return self._envelope(self._row(conn, scope.project_id, sender["id"], mid))

        return self.store._write(scope, key, "message.send", packet, apply)

    def acknowledge(self, scope, key, message_id, expected_sha256):
        """Record explicit receipt of exact content under the current recipient attempt, never comprehension or execution."""
        positive_id(message_id)
        bounded_text(expected_sha256, "observed message hash", 64)

        def apply(conn):
            """Prevent senders, other runs and superseded recipient contexts from manufacturing receipt."""
            sender = self._sender(conn, scope, "messages.ack")
            row = self._row(conn, scope.project_id, sender["id"], message_id)
            self._body(row)
            if row["recipient_run_id"] != sender["id"] or row["recipient_context_version"] != scope.context_version:
                raise ResearchForbidden("Only the exact current recipient can acknowledge this message")
            if row["body_sha256"] != expected_sha256:
                raise OperationConflict("Observed message hash differs from the original content")
            if row["acknowledged_at"] is None:
                conn.execute("UPDATE runtime_agent_messages SET acknowledged_by_attempt=?,acknowledged_at=? WHERE message_id=?",
                             (sender["attempt_id"], self.store.clock(), message_id))
            return self._envelope(self._row(conn, scope.project_id, sender["id"], message_id))

        return self.store._write(scope, key, "message.ack", {"message_id": message_id, "expected_sha256": expected_sha256}, apply)
