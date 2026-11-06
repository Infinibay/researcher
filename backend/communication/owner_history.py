"""Scoped owner access to retained conversations without role dispatch, automatic approvals or legacy polling services."""

from backend.communication.ownership import LEGACY_THREAD_CLAUSE
from backend.runtime.contracts import RunNotFound


class OwnerHistory:
    """Keep historical inbox reads and thread archival separate from native peer authority and message receipts."""

    def __init__(self, runs):
        """Reuse the canonical store transaction and durable event writer without constructing another controller."""
        self.runs = runs

    def archive(self, project_id: int, thread_id: str) -> bool:
        """Archive the actual project's thread once with its event; preserve all messages, acknowledgements and running work."""
        with self.runs._transaction(write=True) as conn:
            row = conn.execute(
                "SELECT status FROM conversation_threads WHERE project_id=? AND thread_id=?",
                (project_id, thread_id),
            ).fetchone()
            if row is None:
                raise RunNotFound("Conversation not found in this project")
            if row["status"] == "archived":
                return False
            conn.execute(
                "UPDATE conversation_threads SET status='archived' WHERE project_id=? AND thread_id=?",
                (project_id, thread_id),
            )
            self.runs._event(conn, project_id, None, "conversation.archived", {
                "thread_id": thread_id, "previous_status": row["status"],
                "work_authorized": False, "work_cancelled": False,
            })
            return True

    def legacy_inbox(self, project_id: int, agent_id: str, *, unread_only: bool = False, limit: int = 50) -> list[dict]:
        """Read the newest historical messages in stable order; old role/read labels cannot reinterpret canonical native threads or acknowledge peers."""
        if not 1 <= limit <= 200:
            raise ValueError("Historical inbox limit must be between 1 and 200")
        with self.runs._transaction() as conn:
            rows = conn.execute(
                f"""SELECT cm.* FROM chat_messages cm
                    WHERE cm.project_id=? AND {LEGACY_THREAD_CLAUSE}
                      AND NOT EXISTS(SELECT 1 FROM runtime_chat_links link
                        WHERE link.project_id=cm.project_id AND link.thread_id=cm.thread_id)
                      AND NOT EXISTS(SELECT 1 FROM runtime_agent_messages peer
                        JOIN chat_messages original ON original.id=peer.message_id AND original.project_id=peer.project_id
                        WHERE peer.project_id=cm.project_id AND original.thread_id=cm.thread_id)
                      AND (cm.to_agent=? OR cm.to_role IN(SELECT role FROM roster WHERE agent_id=?)
                        OR (cm.to_agent IS NULL AND cm.to_role IS NULL))
                      AND (?=0 OR NOT EXISTS(SELECT 1 FROM message_reads read
                        WHERE read.message_id=cm.id AND read.agent_id=?))
                    ORDER BY cm.id DESC LIMIT ?""",
                (project_id, agent_id, agent_id, unread_only, agent_id, limit),
            ).fetchall()
            return [dict(row) for row in reversed(rows)]
