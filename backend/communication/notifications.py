"""Structured notification layer over CommunicationService."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.communication.service import CommunicationService
from backend.flows.event_listeners import FlowEvent, event_bus
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class NotificationService:
    """Fire-and-forget notifications that also emit typed FlowEvents.

    Every method persists the notification as a chat message (via
    ``CommunicationService``) and emits a ``notification_sent`` event so the
    WebSocket manager automatically pushes it to the frontend.
    """

    def __init__(self, bus=None) -> None:
        self.bus = bus or event_bus
        self.comms = CommunicationService(bus=self.bus)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _emit_notification(
        self,
        project_id: int,
        msg_id: int,
        kind: str,
        target: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        data: dict[str, Any] = {"kind": kind, "target": target, "message_id": msg_id}
        if extra:
            data.update(extra)
        self.bus.emit(
            FlowEvent(
                event_type="notification_sent",
                project_id=project_id,
                entity_type="notification",
                entity_id=msg_id,
                data=data,
            )
        )

    # ── Agent notification ────────────────────────────────────────────────

    def notify_agent(
        self,
        project_id: int,
        from_agent: str,
        to_agent: str,
        message: str,
        priority: int = 0,
    ) -> int:
        """Send a notification to a specific agent."""
        msg_id = self.comms.send(
            project_id=project_id,
            from_agent=from_agent,
            message=message,
            to_agent=to_agent,
            priority=priority,
        )
        self._emit_notification(project_id, msg_id, "agent", to_agent)
        return msg_id

    # ── Role notification ─────────────────────────────────────────────────

    def notify_role(
        self,
        project_id: int,
        from_agent: str,
        to_role: str,
        message: str,
        priority: int = 0,
    ) -> int:
        """Send a notification to all agents with a given role."""
        msg_id = self.comms.send(
            project_id=project_id,
            from_agent=from_agent,
            message=message,
            to_role=to_role,
            priority=priority,
        )
        self._emit_notification(project_id, msg_id, "role", to_role)
        return msg_id

    # ── Broadcast ─────────────────────────────────────────────────────────

    def broadcast(
        self,
        project_id: int,
        from_agent: str,
        message: str,
    ) -> int:
        """Broadcast a notification to all agents in the project."""
        msg_id = self.comms.send(
            project_id=project_id,
            from_agent=from_agent,
            message=message,
        )
        self._emit_notification(project_id, msg_id, "broadcast", None)
        return msg_id

    # ── User notification (fire-and-forget) ───────────────────────────────

    def notify_user(
        self,
        project_id: int,
        from_agent: str,
        message: str,
        title: str = "Notification",
        options: list[str] | None = None,
    ) -> int:
        """Insert a user-facing request without polling for a reply."""

        def _insert(conn: sqlite3.Connection) -> int:
            import json

            cursor = conn.execute(
                """INSERT INTO user_requests
                       (project_id, agent_id, request_type, title, body,
                        options_json, status, created_at)
                   VALUES (?, ?, 'question', ?, ?, ?, 'pending', CURRENT_TIMESTAMP)""",
                (
                    project_id,
                    from_agent,
                    title,
                    message,
                    json.dumps(options) if options else "[]",
                ),
            )
            conn.commit()
            return cursor.lastrowid

        req_id = execute_with_retry(_insert)
        self._emit_notification(
            project_id, req_id, "user", "user", extra={"request_id": req_id}
        )
        logger.info("User notification %d from %s", req_id, from_agent)
        return req_id

    # ── System notice ─────────────────────────────────────────────────────

    def create_notice(
        self,
        project_id: int,
        title: str,
        content: str,
        priority: int = 0,
        expires_at: str | None = None,
    ) -> int:
        """Insert a project-wide notice."""

        def _insert(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO notices
                       (project_id, title, content, priority,
                        expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (project_id, title, content, priority, expires_at),
            )
            conn.commit()
            return cursor.lastrowid

        notice_id = execute_with_retry(_insert)
        self._emit_notification(
            project_id, notice_id, "notice", None, extra={"title": title}
        )
        logger.info("Notice %d created for project %d: %s", notice_id, project_id, title)
        return notice_id
