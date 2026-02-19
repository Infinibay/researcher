"""Tool for reading messages directed to the current agent."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReadMessagesInput(BaseModel):
    from_agent: str | None = Field(
        default=None, description="Filter by sender agent ID"
    )
    thread_id: str | None = Field(
        default=None, description="Filter by thread ID"
    )
    unread_only: bool = Field(
        default=True, description="Only return unread messages"
    )
    limit: int = Field(default=50, ge=1, le=200, description="Max messages to return")


class ReadMessagesTool(PabadaBaseTool):
    name: str = "read_messages"
    description: str = (
        "Read messages directed to you (by agent ID, role, or broadcast). "
        "Marks messages as read. Includes active notices."
    )
    args_schema: Type[BaseModel] = ReadMessagesInput

    def _run(
        self,
        from_agent: str | None = None,
        thread_id: str | None = None,
        unread_only: bool = True,
        limit: int = 50,
    ) -> str:
        agent_id = self._validate_agent_context()
        project_id = self.project_id

        def _read(conn: sqlite3.Connection) -> dict:
            # First, get active notices
            notices = []
            if project_id:
                notice_rows = conn.execute(
                    """SELECT id, title, content, priority, created_by, created_at
                       FROM notices
                       WHERE (project_id = ? OR project_id IS NULL)
                         AND active = 1
                         AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                       ORDER BY priority DESC, created_at DESC""",
                    (project_id,),
                ).fetchall()
                notices = [dict(n) for n in notice_rows]

            # Build message query
            # Agent receives: direct (to_agent=me), role-based (to_role=my_role),
            # or broadcast (to_agent IS NULL AND to_role IS NULL)
            conditions = [
                """(cm.to_agent = ? OR cm.to_role IN (
                       SELECT role FROM roster WHERE agent_id = ?
                   ) OR (cm.to_agent IS NULL AND cm.to_role IS NULL))""",
            ]
            params: list = [agent_id, agent_id]

            # Exclude own messages
            conditions.append("cm.from_agent != ?")
            params.append(agent_id)

            if project_id:
                conditions.append("(cm.project_id = ? OR cm.project_id IS NULL)")
                params.append(project_id)

            if from_agent:
                conditions.append("cm.from_agent = ?")
                params.append(from_agent)

            if thread_id:
                conditions.append("cm.thread_id = ?")
                params.append(thread_id)

            if unread_only:
                conditions.append(
                    """cm.id NOT IN (
                        SELECT message_id FROM message_reads WHERE agent_id = ?
                    )"""
                )
                params.append(agent_id)

            where = " AND ".join(conditions)
            params.append(limit)

            rows = conn.execute(
                f"""SELECT cm.id, cm.thread_id, cm.from_agent, cm.to_agent,
                           cm.to_role, cm.conversation_type, cm.message,
                           cm.priority, cm.created_at
                    FROM chat_messages cm
                    WHERE {where}
                    ORDER BY cm.priority DESC, cm.created_at ASC
                    LIMIT ?""",
                params,
            ).fetchall()

            messages = [dict(r) for r in rows]

            # Mark as read
            for msg in messages:
                conn.execute(
                    """INSERT OR IGNORE INTO message_reads (message_id, agent_id)
                       VALUES (?, ?)""",
                    (msg["id"], agent_id),
                )

            conn.commit()
            return {"notices": notices, "messages": messages}

        try:
            result = execute_with_retry(_read)
        except ValueError as e:
            return self._error(str(e))

        return self._success({
            "notices": result["notices"],
            "messages": result["messages"],
            "count": len(result["messages"]),
            "has_notices": len(result["notices"]) > 0,
        })
