"""High-level communication service for inter-agent messaging."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any

from backend.communication.thread_manager import ThreadManager
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class CommunicationService:
    """Unified API for sending and reading inter-agent messages.

    Agents and flows should use this instead of calling
    ``send_agent_message()`` from ``backend.flows.helpers`` directly.
    """

    def __init__(self, bus=None) -> None:
        if bus is None:
            from backend.flows.event_listeners import event_bus
            bus = event_bus
        self.bus = bus
        self.thread_manager = ThreadManager()

    # ── Send ──────────────────────────────────────────────────────────────

    def send(
        self,
        project_id: int,
        from_agent: str,
        message: str,
        to_agent: str | None = None,
        to_role: str | None = None,
        thread_id: str | None = None,
        priority: int = 0,
        conv_type: str = "agent_to_agent",
    ) -> int:
        """Insert a message, update the thread, and emit ``message_sent``."""
        # LoopGuard check — bypass for system messages
        if from_agent != "system":
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
            if verdict.action == "block" or verdict.action == "escalate":
                logger.warning(
                    "LoopGuard blocked message from %s: %s",
                    from_agent, verdict.reason,
                )
                return -1
            if verdict.action == "throttle":
                time.sleep(min(verdict.delay_seconds, 10))

        def _insert(conn: sqlite3.Connection) -> tuple[int, str]:
            actual_thread_id = thread_id
            if actual_thread_id is None:
                import uuid

                actual_thread_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT OR IGNORE INTO conversation_threads
                           (thread_id, project_id, thread_type, created_at, last_message_at)
                       VALUES (?, ?, 'team_sync', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (actual_thread_id, project_id),
                )

            cursor = conn.execute(
                """INSERT INTO chat_messages
                       (project_id, thread_id, from_agent, to_agent, to_role,
                        message, conversation_type, priority, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    project_id,
                    actual_thread_id,
                    from_agent,
                    to_agent,
                    to_role,
                    message,
                    conv_type,
                    priority,
                ),
            )

            # Update thread last_message_at
            conn.execute(
                """UPDATE conversation_threads
                   SET last_message_at = CURRENT_TIMESTAMP
                   WHERE thread_id = ?""",
                (actual_thread_id,),
            )
            conn.commit()
            return cursor.lastrowid, actual_thread_id

        msg_id, actual_thread = execute_with_retry(_insert)

        # Record fingerprint for future dedup (skip for system messages)
        if from_agent != "system":
            try:
                from backend.communication.loop_guard import LoopGuard as _LG

                guard_obj = _LG()
                guard_obj.record_fingerprint(
                    message_id=msg_id,
                    message=message,
                    from_agent=from_agent,
                    to_agent=to_agent,
                    to_role=to_role,
                    thread_id=actual_thread,
                    project_id=project_id,
                )
            except Exception:
                logger.debug("Failed to record fingerprint for message %d", msg_id)

        from backend.flows.event_listeners import FlowEvent

        self.bus.emit(
            FlowEvent(
                event_type="message_sent",
                project_id=project_id,
                entity_type="message",
                entity_id=msg_id,
                data={
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "to_role": to_role,
                    "thread_id": actual_thread,
                    "priority": priority,
                    "conversation_type": conv_type,
                    "content": message,
                },
            )
        )

        logger.debug(
            "Message %d sent from %s -> agent=%s role=%s (thread %s)",
            msg_id, from_agent, to_agent, to_role, actual_thread,
        )
        return msg_id

    # ── Read ──────────────────────────────────────────────────────────────

    def get_messages(
        self,
        project_id: int,
        thread_id: str | None = None,
        agent_id: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve messages with optional filtering."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            clauses = ["cm.project_id = ?"]
            params: list[Any] = [project_id]

            if thread_id:
                clauses.append("cm.thread_id = ?")
                params.append(thread_id)

            if agent_id:
                clauses.append(
                    "(cm.to_agent = ? OR cm.to_role IN ("
                    "  SELECT role FROM roster WHERE agent_id = ?"
                    ") OR (cm.to_agent IS NULL AND cm.to_role IS NULL))"
                )
                params.extend([agent_id, agent_id])

            if unread_only and agent_id:
                clauses.append(
                    "cm.id NOT IN ("
                    "  SELECT message_id FROM message_reads WHERE agent_id = ?"
                    ")"
                )
                params.append(agent_id)

            params.append(limit)
            where = " AND ".join(clauses)
            rows = conn.execute(
                f"""SELECT cm.* FROM chat_messages cm
                    WHERE {where}
                    ORDER BY cm.created_at DESC
                    LIMIT ?""",
                params,
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

        return execute_with_retry(_query)

    # ── Mark read ─────────────────────────────────────────────────────────

    def mark_read(self, message_ids: list[int], agent_id: str) -> None:
        """Record that an agent has read the given messages."""

        def _insert(conn: sqlite3.Connection) -> None:
            conn.executemany(
                """INSERT OR IGNORE INTO message_reads
                       (message_id, agent_id, read_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)""",
                [(mid, agent_id) for mid in message_ids],
            )
            conn.commit()

        execute_with_retry(_insert)

    # ── Unread count ──────────────────────────────────────────────────────

    def get_unread_count(self, project_id: int, agent_id: str) -> int:
        """Count unread messages directed at *agent_id*."""

        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM chat_messages cm
                   WHERE cm.project_id = ?
                     AND (cm.to_agent = ? OR cm.to_role IN (
                         SELECT role FROM roster WHERE agent_id = ?
                     ) OR (cm.to_agent IS NULL AND cm.to_role IS NULL))
                     AND cm.id NOT IN (
                         SELECT message_id FROM message_reads WHERE agent_id = ?
                     )""",
                (project_id, agent_id, agent_id, agent_id),
            ).fetchone()
            return row["cnt"] if row else 0

        return execute_with_retry(_query)

    # ── Thread lookup ─────────────────────────────────────────────────────

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Fetch a single thread by ID."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT * FROM conversation_threads WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)
