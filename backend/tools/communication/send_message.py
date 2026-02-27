"""Tool for sending messages between agents."""

import json
import re
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


# ---------------------------------------------------------------------------
# Acknowledgment-only message filter (module-level to avoid Pydantic issues)
# ---------------------------------------------------------------------------

_ACK_PATTERNS = re.compile(
    r"^(?:"
    r"(?:recibido|entendido|gracias|de acuerdo|confirmo|ok|understood|"
    r"received|acknowledged|noted|roger|thanks|thank you|will do|"
    r"got it|copy that|affirmative)"
    r"[.!,;]?\s*"
    r")+$",
    re.IGNORECASE,
)

_ACK_PHRASES = (
    "recibido", "entendido", "gracias", "procederé",
    "confirmo", "estaré atento", "understood", "received",
    "acknowledged", "will proceed", "got it", "noted",
    "thank you for", "thanks for the",
    "waiting for", "monitoring", "keeping an eye",
    "standing by", "awaiting", "i'm available",
    "ready when", "estoy esperando", "estoy monitoreando",
)


def _is_acknowledgment_only(message: str) -> bool:
    """Return True if the message is a pure acknowledgment with no substance."""
    stripped = message.strip().rstrip(".")
    if len(stripped) < 5:
        return True
    if _ACK_PATTERNS.match(stripped):
        return True
    # Heuristic: very short message (<80 chars) with typical ack phrases
    # and no questions, URLs, code, or task IDs
    if len(stripped) < 80:
        lower = stripped.lower()
        has_ack = any(p in lower for p in _ACK_PHRASES)
        has_substance = any(c in stripped for c in ("?", "http", "```", "#"))
        if has_ack and not has_substance:
            remainder = lower
            for p in _ACK_PHRASES:
                remainder = remainder.replace(p, "")
            remainder = re.sub(r"[.,;:!\s]+", "", remainder)
            if len(remainder) < 20:
                return True
    return False


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

    @staticmethod
    def _validate_task_ids_in_message(
        message: str, project_id: int | None
    ) -> str | None:
        """Check if the message references task IDs that don't exist.

        Returns a warning string if phantom IDs are found, else None.
        Purely advisory — does not block the message.
        """
        if not project_id:
            return None
        # Match patterns like "task 123", "task #123", "#123", "task_id 123"
        matches = re.findall(
            r"(?:task\s*#?\s*|#|task_id\s*[:=]?\s*)(\d{2,})", message, re.IGNORECASE
        )
        if not matches:
            return None

        candidate_ids = list({int(m) for m in matches})

        def _check(conn: sqlite3.Connection) -> list[int]:
            placeholders = ",".join("?" for _ in candidate_ids)
            rows = conn.execute(
                f"SELECT id FROM tasks WHERE id IN ({placeholders}) AND project_id = ?",
                candidate_ids + [project_id],
            ).fetchall()
            existing = {r["id"] for r in rows}
            return [cid for cid in candidate_ids if cid not in existing]

        try:
            phantom = execute_with_retry(_check)
        except Exception:
            return None

        if phantom:
            ids_str = ", ".join(f"#{pid}" for pid in phantom)
            return (
                f"WARNING: Your message references task IDs that do not exist "
                f"in this project: {ids_str}. Use ReadTasksTool or GetTaskTool "
                f"to obtain valid IDs before referencing them."
            )
        return None

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

        # Block acknowledgment-only messages — they waste cycles and cause loops
        if _is_acknowledgment_only(message):
            return self._success({
                "status": "skipped",
                "reason": (
                    "Message was an acknowledgment with no actionable content. "
                    "Acknowledgments are unnecessary — proceed with your actual work instead."
                ),
            })

        # Soft-validate task IDs mentioned in the message (BUG-1 mitigation)
        id_warning = self._validate_task_ids_in_message(message, project_id)

        # Resolve to_agent: agents may pass a display name instead of a
        # canonical agent_id.  Look up the roster to normalise.
        if to_agent is not None:
            to_agent = self._resolve_to_agent(to_agent, project_id)

        # Normalise thread_id — LLMs sometimes pass "None" as a string
        if thread_id is not None and (
            thread_id.lower() == "none" or thread_id.strip() == ""
        ):
            thread_id = None

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
                # Verify thread exists — if not, auto-create it.
                # Agents sometimes invent thread IDs (hallucination); refusing
                # the message is worse than creating the thread on-the-fly.
                row = conn.execute(
                    "SELECT thread_id FROM conversation_threads WHERE thread_id = ?",
                    (actual_thread_id,),
                ).fetchone()
                if not row:
                    thread_type = "team_sync" if conv_type == "broadcast" else "task_discussion"
                    conn.execute(
                        """INSERT INTO conversation_threads
                           (thread_id, project_id, thread_type, participants_json, status)
                           VALUES (?, ?, ?, ?, 'active')""",
                        (actual_thread_id, project_id, thread_type,
                         json.dumps([from_agent, to_agent or to_role or "all"])),
                    )

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

        from backend.flows.event_listeners import FlowEvent, event_bus

        event_bus.emit(
            FlowEvent(
                event_type="message_sent",
                project_id=project_id,
                entity_type="message",
                entity_id=result["message_id"],
                data={
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "to_role": to_role,
                    "thread_id": result["thread_id"],
                    "priority": priority,
                    "conversation_type": conv_type,
                    "content": message,
                },
            )
        )

        # Notify any waiting ask_team_lead / ask_project_lead callers
        from backend.communication.response_event_registry import response_event_registry
        response_event_registry.notify(result["thread_id"])

        # Create persistent agent_events so the autonomy system can dispatch
        # the message to the target agent (e.g. kick off a Crew for the PL
        # to answer a question from the TL).
        # Skip if someone is already waiting on this thread via ask_*_lead
        # tools — in that case, response_event_registry.notify() already
        # unblocked the caller and an extra dispatch would be redundant.
        if not response_event_registry.is_registered(result["thread_id"]):
            try:
                from backend.autonomy.events import create_message_event
                create_message_event(
                    project_id=project_id,
                    from_agent=from_agent,
                    to_agent=to_agent,
                    to_role=to_role,
                    message=message,
                    thread_id=result["thread_id"],
                    message_id=result["message_id"],
                    conversation_type=conv_type,
                )
            except Exception:
                pass  # non-fatal — autonomy may not be active

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

        # Warn about phantom task IDs (advisory, non-blocking)
        if id_warning:
            response["warning"] = id_warning

        return self._success(response)
