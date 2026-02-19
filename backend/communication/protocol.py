"""Pre-ticket check-in protocol enforcement.

Ensures that developer/researcher agents post their understanding of a task
to the team lead and receive approval before beginning work.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.communication.service import CommunicationService
from backend.communication.thread_manager import ThreadManager
from backend.flows.event_listeners import FlowEvent, event_bus
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class TicketProtocol:
    """Enforce the mandatory pre-ticket check-in flow."""

    def __init__(self, bus=None) -> None:
        self.bus = bus or event_bus
        self.comms = CommunicationService(bus=self.bus)
        self.thread_manager = ThreadManager()

    def initiate_checkin(
        self,
        project_id: int,
        task_id: int,
        agent_id: str,
        agent_role: str,
    ) -> str:
        """Start a check-in for *task_id*.

        Creates (or reuses) a ``task_discussion`` thread, sends an initial
        message to the team lead, and emits ``ticket_checkin_initiated``.

        Returns the thread_id.
        """
        thread_id = self.thread_manager.get_or_create_task_thread(
            project_id=project_id,
            task_id=task_id,
            thread_type="task_discussion",
        )

        # Fetch task summary for the initial message
        task_summary = self._get_task_summary(task_id)

        self.comms.send(
            project_id=project_id,
            from_agent=agent_id,
            message=(
                f"[Check-in] {agent_role} {agent_id} has taken task #{task_id}.\n\n"
                f"Task summary:\n{task_summary}\n\n"
                f"Awaiting understanding post and team lead approval before work begins."
            ),
            to_role="team_lead",
            thread_id=thread_id,
        )

        self.bus.emit(
            FlowEvent(
                event_type="ticket_checkin_initiated",
                project_id=project_id,
                entity_type="task",
                entity_id=task_id,
                data={
                    "thread_id": thread_id,
                    "agent_id": agent_id,
                    "agent_role": agent_role,
                },
            )
        )

        logger.info(
            "Check-in initiated for task %d by %s (thread %s)",
            task_id, agent_id, thread_id,
        )
        return thread_id

    def post_understanding(
        self,
        thread_id: str,
        agent_id: str,
        understanding_summary: str,
    ) -> None:
        """Agent posts their interpretation of the task."""
        thread = self.comms.get_thread(thread_id)
        if not thread:
            logger.warning("post_understanding: thread %s not found", thread_id)
            return

        self.comms.send(
            project_id=thread["project_id"],
            from_agent=agent_id,
            message=f"[Understanding]\n{understanding_summary}",
            to_role="team_lead",
            thread_id=thread_id,
        )
        logger.info(
            "Understanding posted to thread %s by %s", thread_id, agent_id,
        )

    def approve_checkin(
        self,
        thread_id: str,
        team_lead_id: str,
        notes: str = "",
    ) -> None:
        """Team lead approves the check-in; emits ``ticket_checkin_approved``."""
        thread = self.comms.get_thread(thread_id)
        if not thread:
            logger.warning("approve_checkin: thread %s not found", thread_id)
            return

        approval_msg = "[Approved] Check-in approved by team lead."
        if notes:
            approval_msg += f"\nNotes: {notes}"

        self.comms.send(
            project_id=thread["project_id"],
            from_agent=team_lead_id,
            message=approval_msg,
            thread_id=thread_id,
        )

        self.bus.emit(
            FlowEvent(
                event_type="ticket_checkin_approved",
                project_id=thread["project_id"],
                entity_type="task",
                entity_id=thread.get("task_id"),
                data={"thread_id": thread_id, "team_lead_id": team_lead_id},
            )
        )

        # Mark the thread as resolved
        self.thread_manager.resolve_thread(thread_id)
        logger.info("Check-in approved for thread %s by %s", thread_id, team_lead_id)

    def request_clarification(
        self,
        thread_id: str,
        team_lead_id: str,
        clarification: str,
    ) -> None:
        """Team lead asks for more info; emits ``ticket_checkin_clarification_needed``."""
        thread = self.comms.get_thread(thread_id)
        if not thread:
            logger.warning(
                "request_clarification: thread %s not found", thread_id,
            )
            return

        self.comms.send(
            project_id=thread["project_id"],
            from_agent=team_lead_id,
            message=f"[Clarification Needed]\n{clarification}",
            thread_id=thread_id,
        )

        self.bus.emit(
            FlowEvent(
                event_type="ticket_checkin_clarification_needed",
                project_id=thread["project_id"],
                entity_type="task",
                entity_id=thread.get("task_id"),
                data={"thread_id": thread_id, "team_lead_id": team_lead_id},
            )
        )

        logger.info(
            "Clarification requested for thread %s by %s",
            thread_id, team_lead_id,
        )

    def get_checkin_status(self, task_id: int) -> dict[str, Any]:
        """Return the status of the check-in for a task."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any]:
            thread = conn.execute(
                """SELECT thread_id, status, last_message_at
                   FROM conversation_threads
                   WHERE task_id = ? AND thread_type = 'task_discussion'
                   ORDER BY created_at DESC LIMIT 1""",
                (task_id,),
            ).fetchone()

            if not thread:
                return {"status": "none", "thread_id": None, "last_message": None}

            last_msg = conn.execute(
                """SELECT from_agent, message, created_at
                   FROM chat_messages
                   WHERE thread_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (thread["thread_id"],),
            ).fetchone()

            return {
                "status": thread["status"] or "active",
                "thread_id": thread["thread_id"],
                "last_message_at": thread["last_message_at"],
                "last_message": dict(last_msg) if last_msg else None,
            }

        return execute_with_retry(_query)

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_task_summary(task_id: int) -> str:
        def _query(conn: sqlite3.Connection) -> str:
            row = conn.execute(
                "SELECT title, description FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                return f"Task #{task_id} (not found)"
            title = row["title"] or "Untitled"
            desc = row["description"] or "No description"
            return f"{title}\n{desc}"

        return execute_with_retry(_query)
