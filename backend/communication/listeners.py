"""Event listeners for inter-agent messaging and ticket check-in threads."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from backend.flows.event_listeners import BaseEventListener, FlowEvent
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class AgentMessageListener(BaseEventListener):
    """Poll ``chat_messages`` for new agent-to-agent messages and emit events.

    Fills the gap left by ``UserMessageListener`` which only handles
    ``conversation_type = 'user_to_agent'``.
    """

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        kwargs.setdefault("poll_interval", 3.0)
        super().__init__(project_id, **kwargs)
        self._last_message_id: int = 0
        self._initialize_last_message_id()

    def _initialize_last_message_id(self) -> None:
        """Start from the current max id to avoid replaying history."""

        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                """SELECT MAX(id) as max_id FROM chat_messages
                   WHERE project_id = ? AND conversation_type = 'agent_to_agent'""",
                (self.project_id,),
            ).fetchone()
            return row["max_id"] if row and row["max_id"] else 0

        self._last_message_id = execute_with_retry(_query)

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, from_agent, to_agent, to_role, thread_id, message
                   FROM chat_messages
                   WHERE project_id = ?
                     AND id > ?
                     AND conversation_type = 'agent_to_agent'
                   ORDER BY id ASC""",
                (self.project_id, self._last_message_id),
            ).fetchall()
            return [dict(r) for r in rows]

        messages = execute_with_retry(_query)

        for msg in messages:
            self._last_message_id = msg["id"]

            if msg.get("to_agent"):
                target_type, target_id = "agent", msg["to_agent"]
            elif msg.get("to_role"):
                target_type, target_id = "role", msg["to_role"]
            else:
                target_type, target_id = "broadcast", None

            self.bus.emit(
                FlowEvent(
                    event_type="agent_message_received",
                    project_id=self.project_id,
                    entity_type="message",
                    entity_id=msg["id"],
                    data={
                        "target_type": target_type,
                        "target_id": target_id,
                        "from_agent": msg.get("from_agent"),
                        "message_id": msg["id"],
                        "thread_id": msg.get("thread_id"),
                        "content": msg.get("message", ""),
                    },
                )
            )


class TicketCheckinListener(BaseEventListener):
    """Poll ``conversation_threads`` for updated task-discussion threads.

    Emits ``ticket_thread_updated`` so that ``DevelopmentFlow`` can react to
    team lead responses without its own polling.
    """

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        kwargs.setdefault("poll_interval", 5.0)
        super().__init__(project_id, **kwargs)
        self._thread_timestamps: dict[str, str] = {}
        self._initialize_timestamps()

    def _initialize_timestamps(self) -> None:
        """Snapshot current last_message_at for all task_discussion threads."""

        def _query(conn: sqlite3.Connection) -> dict[str, str]:
            rows = conn.execute(
                """SELECT thread_id, last_message_at
                   FROM conversation_threads
                   WHERE project_id = ?
                     AND thread_type = 'task_discussion'""",
                (self.project_id,),
            ).fetchall()
            return {
                r["thread_id"]: r["last_message_at"] or ""
                for r in rows
            }

        self._thread_timestamps = execute_with_retry(_query)

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT thread_id, task_id, last_message_at, status
                   FROM conversation_threads
                   WHERE project_id = ?
                     AND thread_type = 'task_discussion'""",
                (self.project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        threads = execute_with_retry(_query)

        for thread in threads:
            tid = thread["thread_id"]
            last_at = thread.get("last_message_at") or ""
            prev_at = self._thread_timestamps.get(tid, "")

            if last_at != prev_at:
                self._thread_timestamps[tid] = last_at
                self.bus.emit(
                    FlowEvent(
                        event_type="ticket_thread_updated",
                        project_id=self.project_id,
                        entity_type="thread",
                        data={
                            "thread_id": tid,
                            "task_id": thread.get("task_id"),
                            "status": thread.get("status"),
                            "last_message_at": last_at,
                        },
                    )
                )


class CommunicationLoopListener(BaseEventListener):
    """Safety net: poll active threads for loop patterns every 30 seconds.

    Scans threads with recent activity for ping-pong or repetition patterns
    and escalates via LoopGuard if detected.
    """

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        kwargs.setdefault("poll_interval", 30.0)
        super().__init__(project_id, **kwargs)

    def check(self) -> None:
        from backend.communication.loop_guard import LoopGuard

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT DISTINCT thread_id FROM chat_messages
                   WHERE project_id = ?
                     AND conversation_type = 'agent_to_agent'
                     AND created_at > datetime('now', '-5 minutes')""",
                (self.project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        active_threads = execute_with_retry(_query)

        for thread_row in active_threads:
            thread_id = thread_row["thread_id"]
            self._check_thread_for_loops(thread_id)

    def _check_thread_for_loops(self, thread_id: str) -> None:
        from backend.communication.loop_guard import LoopGuard
        from backend.config.settings import settings

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT from_agent, message FROM chat_messages
                   WHERE thread_id = ?
                   ORDER BY created_at DESC LIMIT 10""",
                (thread_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        recent = execute_with_retry(_query)
        if len(recent) < settings.LOOP_PING_PONG_THRESHOLD:
            return

        # Check for alternating pattern
        agents = [m["from_agent"] for m in recent]
        unique = set(agents[:settings.LOOP_PING_PONG_THRESHOLD])
        if len(unique) == 2:
            is_alternating = all(
                agents[i] != agents[i + 1]
                for i in range(min(len(agents) - 1, settings.LOOP_PING_PONG_THRESHOLD - 1))
            )
            if is_alternating:
                guard = LoopGuard()
                agent_list = list(unique)
                guard.escalate_loop(
                    project_id=self.project_id,
                    thread_id=thread_id,
                    agents=agent_list,
                    reason=(
                        f"Background scan detected ping-pong loop between "
                        f"{agent_list[0]} and {agent_list[1]} in thread {thread_id}"
                    ),
                )
                self.bus.emit(
                    FlowEvent(
                        event_type="communication_loop_detected",
                        project_id=self.project_id,
                        entity_type="thread",
                        data={
                            "thread_id": thread_id,
                            "agents": agent_list,
                            "detection_source": "background_listener",
                        },
                    )
                )
                logger.warning(
                    "CommunicationLoopListener: loop detected in thread %s "
                    "between %s (project %d)",
                    thread_id, agent_list, self.project_id,
                )
