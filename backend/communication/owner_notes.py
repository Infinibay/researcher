"""Owner explanatory conversation adapter: atomic original notes and receipts without work assignment, inference or agent-event activation."""

import json
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.runtime.contracts import RunConflict, RunNotFound, command_key


class OwnerNotes:
    """Preserve attributed owner messages separately from typed native instructions and context corrections."""

    def __init__(self, runs):
        """Reuse the canonical journal transaction and events; never initialize another database or runtime."""
        self.runs = runs

    def record(self, project_id, packet):
        """Append one explanatory note, or recover its exact original receipt after reply loss; destination labels grant no execution authority."""
        key = packet["operation_key"] or "legacy-note-" + uuid4().hex
        command_key(key)
        fingerprint = digest(packet)
        with self.runs._transaction(write=True) as conn:
            if (
                conn.execute(
                    "SELECT 1 FROM projects WHERE id=?", (project_id,)
                ).fetchone()
                is None
            ):
                raise RunNotFound("Project not found")
            previous = conn.execute(
                "SELECT *FROM runtime_owner_notes WHERE project_id=? AND operation_key=?",
                (project_id, key),
            ).fetchone()
            if previous:
                if previous["request_sha256"] != fingerprint:
                    raise RunConflict(
                        "Original note key already identifies different content or conversation"
                    )
                return json.loads(previous["receipt_json"])
            thread = packet["thread_id"]
            if thread is None:
                thread = uuid4().hex
                conn.execute(
                    "INSERT INTO conversation_threads(thread_id,project_id,thread_type)VALUES(?,?,'user_chat')",
                    (thread, project_id),
                )
            else:
                existing = conn.execute(
                    "SELECT status FROM conversation_threads WHERE thread_id=? AND project_id=?",
                    (thread, project_id),
                ).fetchone()
                if existing is None:
                    raise RunNotFound("Conversation not found in this project")
                if existing["status"] != "active":
                    raise RunConflict(
                        "Conversation is closed; retain its history and open another conversation"
                    )
            mid = conn.execute(
                "INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,to_role,message,conversation_type)VALUES(?,?,'user',?,?,?,'user_to_agent')",
                (
                    project_id,
                    thread,
                    packet["to_agent"],
                    packet["to_role"],
                    packet["message"],
                ),
            ).lastrowid
            conn.execute(
                "UPDATE conversation_threads SET last_message_at=CURRENT_TIMESTAMP WHERE thread_id=?",
                (thread,),
            )
            result = {
                **dict(
                    conn.execute(
                        "SELECT *FROM chat_messages WHERE id=?", (mid,)
                    ).fetchone()
                ),
                "operation_key": key,
                "delivery": "recorded",
            }
            conn.execute(
                "INSERT INTO runtime_owner_notes VALUES(?,?,?,?,?,?)",
                (
                    project_id,
                    key,
                    fingerprint,
                    mid,
                    canonical(result),
                    self.runs.clock(),
                ),
            )
            self.runs._event(
                conn,
                project_id,
                None,
                "conversation.note_recorded",
                {
                    "message_id": mid,
                    "thread_id": thread,
                    "operation_key": key,
                    "source_kind": "user_message",
                    "work_authorized": False,
                },
            )
            return result
