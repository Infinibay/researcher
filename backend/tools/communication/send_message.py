"""Tool for sending messages between agents."""

import json
import sqlite3
import time
import uuid
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class SendMessageInput(BaseModel):
    message: str = Field(..., description="Message content to send")
    to_agent: str | None = Field(
        default=None, description="Target agent ID for direct message"
    )
    to_role: str | None = Field(
        default=None, description="Target role for role-based message"
    )
    thread_id: str | None = Field(
        default=None, description="Thread ID to reply to. Creates new thread if None."
    )
    priority: int = Field(
        default=0, ge=0, le=3, description="Message priority (0=normal, 3=urgent)"
    )


class SendMessageTool(PabadaBaseTool):
    name: str = "send_message"
    description: str = (
        "Send a message to a specific agent, role, or broadcast to all. "
        "Messages are threaded for organized conversations."
    )
    args_schema: Type[BaseModel] = SendMessageInput

    @staticmethod
    def _resolve_to_agent(to_agent: str, project_id: int) -> str:
        """Normalise *to_agent* to a canonical agent_id via the roster.

        If the value already matches an ``agent_id`` in the roster it is
        returned as-is.  Otherwise we try matching it as a display name
        (case-insensitive) scoped to the project.  Falls back to the
        original value when no match is found so the caller still stores
        *something* meaningful.
        """
        def _query(conn: sqlite3.Connection) -> str:
            # Exact agent_id match
            row = conn.execute(
                "SELECT agent_id FROM roster WHERE agent_id = ?",
                (to_agent,),
            ).fetchone()
            if row:
                return row["agent_id"]

            # Match by display name within project
            row = conn.execute(
                """SELECT agent_id FROM roster
                   WHERE LOWER(name) = LOWER(?)
                     AND agent_id LIKE ? ESCAPE '\\'
                     AND status != 'retired'""",
                (to_agent, f"%\\_p{project_id}"),
            ).fetchone()
            if row:
                return row["agent_id"]

            # Match composite "role_name" (e.g. "team_lead_harper")
            row = conn.execute(
                """SELECT agent_id FROM roster
                   WHERE LOWER(?) LIKE LOWER(role || '_%')
                     AND agent_id LIKE ? ESCAPE '\\'
                     AND status != 'retired'
                   ORDER BY LENGTH(role) DESC LIMIT 1""",
                (to_agent, f"%\\_p{project_id}"),
            ).fetchone()
            if row:
                return row["agent_id"]

            return to_agent

        return execute_with_retry(_query)

    def _run(
        self,
        message: str,
        to_agent: str | None = None,
        to_role: str | None = None,
        thread_id: str | None = None,
        priority: int = 0,
    ) -> str:
        from_agent = self._validate_agent_context()
        project_id = self.project_id

        # Resolve to_agent: agents may pass a display name instead of a
        # canonical agent_id.  Look up the roster to normalise.
        if to_agent is not None:
            to_agent = self._resolve_to_agent(to_agent, project_id)

        # Determine conversation type
        if to_agent is None and to_role is None:
            conv_type = "broadcast"
        else:
            conv_type = "agent_to_agent"

        # ── LoopGuard check ──────────────────────────────────────────
        from backend.communication.loop_guard import LoopGuard

        guard = LoopGuard()
        verdict = guard.check_all(
            from_agent=from_agent,
            message=message,
            to_agent=to_agent,
            to_role=to_role,
            thread_id=thread_id,
            project_id=project_id,
        )
        if verdict.action == "block":
            return self._error(
                f"Message blocked: {verdict.reason}. "
                "Review conversation history before sending."
            )
        if verdict.action == "escalate":
            return self._error(
                f"Message blocked (escalated): {verdict.reason}. "
                "A communication loop has been detected. "
                "Stop messaging and proceed with your best judgment."
            )
        if verdict.action == "throttle":
            time.sleep(min(verdict.delay_seconds, 10))

        def _send(conn: sqlite3.Connection) -> dict:
            # Create or get thread
            actual_thread_id = thread_id
            if actual_thread_id is None:
                actual_thread_id = f"thread-{uuid.uuid4().hex[:12]}"
                # Determine thread type
                thread_type = "team_sync" if conv_type == "broadcast" else "task_discussion"
                conn.execute(
                    """INSERT INTO conversation_threads
                       (thread_id, project_id, thread_type, participants_json, status)
                       VALUES (?, ?, ?, ?, 'active')""",
                    (actual_thread_id, project_id, thread_type,
                     json.dumps([from_agent, to_agent or to_role or "all"])),
                )
            else:
                # Verify thread exists
                row = conn.execute(
                    "SELECT thread_id FROM conversation_threads WHERE thread_id = ?",
                    (actual_thread_id,),
                ).fetchone()
                if not row:
                    raise ValueError(f"Thread '{actual_thread_id}' not found")

            # Insert message
            cursor = conn.execute(
                """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, to_agent, to_role,
                    conversation_type, message, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, actual_thread_id, from_agent, to_agent,
                 to_role, conv_type, message, priority),
            )
            msg_id = cursor.lastrowid

            # Update thread last_message_at
            conn.execute(
                """UPDATE conversation_threads
                   SET last_message_at = CURRENT_TIMESTAMP
                   WHERE thread_id = ?""",
                (actual_thread_id,),
            )

            conn.commit()
            return {"message_id": msg_id, "thread_id": actual_thread_id}

        try:
            result = execute_with_retry(_send)
        except ValueError as e:
            return self._error(str(e))

        # Record fingerprint for future dedup checks
        guard.record_fingerprint(
            message_id=result["message_id"],
            message=message,
            from_agent=from_agent,
            to_agent=to_agent,
            to_role=to_role,
            thread_id=result["thread_id"],
            project_id=project_id,
        )

        target = to_agent or to_role or "broadcast"
        self._log_tool_usage(f"Sent message to {target}")

        response = {
            "message_id": result["message_id"],
            "thread_id": result["thread_id"],
            "to": target,
            "priority": priority,
        }
        # Include thread context so agent sees prior conversation
        if verdict.context_summary:
            response["thread_context"] = verdict.context_summary

        return self._success(response)
