"""Event listeners for PABADA — poll DB for state changes and trigger flows.

Listeners run in background threads, polling at configurable intervals.
Each listener checks specific DB conditions and emits events that flows can react to.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.tools.base.db import execute_with_retry, get_connection

logger = logging.getLogger(__name__)


# ── Event types ───────────────────────────────────────────────────────────────


@dataclass
class FlowEvent:
    """Represents an event that can trigger flow actions."""

    event_type: str
    project_id: int
    entity_type: str
    entity_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Event bus ─────────────────────────────────────────────────────────────────


class EventBus:
    """Simple pub/sub event bus for flow events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[FlowEvent], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[FlowEvent], None]) -> None:
        """Register a handler for an event type."""
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[FlowEvent], None]) -> None:
        """Remove a handler for an event type."""
        with self._lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]

    def emit(self, event: FlowEvent) -> None:
        """Emit an event to all registered handlers."""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            # Also notify wildcard listeners
            handlers.extend(self._handlers.get("*", []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Error in event handler for %s", event.event_type)


# Global event bus instance
event_bus = EventBus()


# ── Base listener ─────────────────────────────────────────────────────────────


class BaseEventListener(ABC):
    """Abstract base for DB-polling event listeners."""

    def __init__(
        self,
        project_id: int,
        poll_interval: float = 5.0,
        bus: EventBus | None = None,
    ) -> None:
        self.project_id = project_id
        self.poll_interval = poll_interval
        self.bus = bus or event_bus
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_check: str = datetime.now(timezone.utc).isoformat()

    def start(self) -> None:
        """Start the listener in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name=f"{self.__class__.__name__}-p{self.project_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "%s started for project %d (interval=%.1fs)",
            self.__class__.__name__, self.project_id, self.poll_interval,
        )

    def stop(self) -> None:
        """Signal the listener to stop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval * 2)
            self._thread = None
        logger.info("%s stopped for project %d", self.__class__.__name__, self.project_id)

    @property
    def is_running(self) -> bool:
        return self._running

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                self.check()
                self._last_check = datetime.now(timezone.utc).isoformat()
            except Exception:
                logger.exception("%s poll error", self.__class__.__name__)
            time.sleep(self.poll_interval)

    @abstractmethod
    def check(self) -> None:
        """Override: inspect DB and emit events if conditions are met."""
        ...


# ── Concrete listeners ────────────────────────────────────────────────────────


class TaskStatusChangedListener(BaseEventListener):
    """Listen for task status changes via events_log."""

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        super().__init__(project_id, **kwargs)
        self._last_event_id: int = 0
        self._initialize_last_event_id()

    def _initialize_last_event_id(self) -> None:
        """Set the starting event ID to avoid replaying old events."""
        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT MAX(id) as max_id FROM events_log WHERE project_id = ?",
                (self.project_id,),
            ).fetchone()
            return row["max_id"] if row and row["max_id"] else 0

        self._last_event_id = execute_with_retry(_query)

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, event_type, entity_type, entity_id, event_data_json
                   FROM events_log
                   WHERE project_id = ?
                     AND id > ?
                     AND event_type = 'task_status_changed'
                   ORDER BY id ASC""",
                (self.project_id, self._last_event_id),
            ).fetchall()
            return [dict(r) for r in rows]

        events = execute_with_retry(_query)

        for ev in events:
            self._last_event_id = ev["id"]
            data = json.loads(ev.get("event_data_json", "{}")) if ev.get("event_data_json") else {}
            new_status = data.get("new_status", "")

            self.bus.emit(FlowEvent(
                event_type="task_status_changed",
                project_id=self.project_id,
                entity_type="task",
                entity_id=ev.get("entity_id"),
                data={"new_status": new_status, "old_status": data.get("old_status", "")},
            ))

            # Specific sub-events
            if new_status == "review_ready":
                self.bus.emit(FlowEvent(
                    event_type="task_review_ready",
                    project_id=self.project_id,
                    entity_type="task",
                    entity_id=ev.get("entity_id"),
                ))
            elif new_status == "done":
                self.bus.emit(FlowEvent(
                    event_type="task_done",
                    project_id=self.project_id,
                    entity_type="task",
                    entity_id=ev.get("entity_id"),
                ))
            elif new_status == "failed":
                self.bus.emit(FlowEvent(
                    event_type="task_failed",
                    project_id=self.project_id,
                    entity_type="task",
                    entity_id=ev.get("entity_id"),
                ))


class NewTaskCreatedListener(BaseEventListener):
    """Listen for new tasks being created."""

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        super().__init__(project_id, **kwargs)
        self._last_event_id: int = 0
        self._initialize_last_event_id()

    def _initialize_last_event_id(self) -> None:
        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT MAX(id) as max_id FROM events_log WHERE project_id = ?",
                (self.project_id,),
            ).fetchone()
            return row["max_id"] if row and row["max_id"] else 0

        self._last_event_id = execute_with_retry(_query)

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, entity_id, event_data_json
                   FROM events_log
                   WHERE project_id = ?
                     AND id > ?
                     AND event_type = 'task_created'
                   ORDER BY id ASC""",
                (self.project_id, self._last_event_id),
            ).fetchall()
            return [dict(r) for r in rows]

        events = execute_with_retry(_query)

        for ev in events:
            self._last_event_id = ev["id"]
            data = json.loads(ev.get("event_data_json", "{}")) if ev.get("event_data_json") else {}

            self.bus.emit(FlowEvent(
                event_type="new_task_created",
                project_id=self.project_id,
                entity_type="task",
                entity_id=ev.get("entity_id"),
                data=data,
            ))


class UserMessageListener(BaseEventListener):
    """Listen for user messages directed at agents."""

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        super().__init__(project_id, **kwargs)
        self._last_message_id: int = 0
        self._initialize_last_message_id()

    def _initialize_last_message_id(self) -> None:
        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                """SELECT MAX(id) as max_id FROM chat_messages
                   WHERE project_id = ? AND conversation_type = 'user_to_agent'""",
                (self.project_id,),
            ).fetchone()
            return row["max_id"] if row and row["max_id"] else 0

        self._last_message_id = execute_with_retry(_query)

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, to_agent, to_role, message
                   FROM chat_messages
                   WHERE project_id = ?
                     AND id > ?
                     AND conversation_type = 'user_to_agent'
                   ORDER BY id ASC""",
                (self.project_id, self._last_message_id),
            ).fetchall()
            return [dict(r) for r in rows]

        messages = execute_with_retry(_query)

        for msg in messages:
            self._last_message_id = msg["id"]
            self.bus.emit(FlowEvent(
                event_type="user_message_received",
                project_id=self.project_id,
                entity_type="message",
                entity_id=msg["id"],
                data={
                    "to_agent": msg.get("to_agent"),
                    "to_role": msg.get("to_role"),
                    "content": msg.get("message", ""),
                },
            ))


class StagnationDetectedListener(BaseEventListener):
    """Monitor for project stagnation conditions."""

    def __init__(
        self,
        project_id: int,
        stagnation_threshold_minutes: int = 30,
        min_stuck_tasks: int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(project_id, poll_interval=30.0, **kwargs)
        self.stagnation_threshold_minutes = stagnation_threshold_minutes
        self.min_stuck_tasks = min_stuck_tasks
        self._stagnation_emitted = False

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> dict:
            # Check for recent task completions
            recent_completions = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ? AND status = 'done'
                     AND completed_at >= datetime('now', ?)""",
                (self.project_id, f"-{self.stagnation_threshold_minutes} minutes"),
            ).fetchone()

            # Check for stuck tasks
            stuck_tasks = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ?
                     AND status IN ('in_progress', 'rejected')
                     AND created_at <= datetime('now', ?)""",
                (self.project_id, f"-{self.stagnation_threshold_minutes} minutes"),
            ).fetchone()

            # Check if project is actually executing
            project = conn.execute(
                "SELECT status FROM projects WHERE id = ?",
                (self.project_id,),
            ).fetchone()

            return {
                "recent_completions": recent_completions["cnt"] if recent_completions else 0,
                "stuck_tasks": stuck_tasks["cnt"] if stuck_tasks else 0,
                "project_status": project["status"] if project else "unknown",
            }

        metrics = execute_with_retry(_query)

        # Only detect stagnation for executing projects
        if metrics["project_status"] != "executing":
            self._stagnation_emitted = False
            return

        is_stagnating = (
            metrics["recent_completions"] == 0
            and metrics["stuck_tasks"] >= self.min_stuck_tasks
        )

        if is_stagnating and not self._stagnation_emitted:
            logger.warning(
                "Stagnation detected for project %d: %d stuck tasks, 0 recent completions",
                self.project_id, metrics["stuck_tasks"],
            )
            self.bus.emit(FlowEvent(
                event_type="stagnation_detected",
                project_id=self.project_id,
                entity_type="project",
                entity_id=self.project_id,
                data=metrics,
            ))
            self._stagnation_emitted = True
        elif not is_stagnating:
            self._stagnation_emitted = False


class AllTasksDoneListener(BaseEventListener):
    """Listen for when all tasks in a project are completed or only research remains."""

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        super().__init__(project_id, poll_interval=10.0, **kwargs)
        self._all_done_emitted = False
        self._research_only_emitted = False

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> dict:
            project = conn.execute(
                "SELECT status FROM projects WHERE id = ?",
                (self.project_id,),
            ).fetchone()

            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM tasks WHERE project_id = ?",
                (self.project_id,),
            ).fetchone()

            pending = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ?
                     AND status NOT IN ('done', 'cancelled')""",
                (self.project_id,),
            ).fetchone()

            # Count non-research tasks still open
            non_research_open = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ?
                     AND status NOT IN ('done', 'cancelled')
                     AND type != 'research'""",
                (self.project_id,),
            ).fetchone()

            # Count research tasks still in progress
            research_in_progress = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ?
                     AND status = 'in_progress'
                     AND type = 'research'""",
                (self.project_id,),
            ).fetchone()

            return {
                "project_status": project["status"] if project else "unknown",
                "total_tasks": total["cnt"] if total else 0,
                "pending_tasks": pending["cnt"] if pending else 0,
                "non_research_open": non_research_open["cnt"] if non_research_open else 0,
                "research_in_progress": research_in_progress["cnt"] if research_in_progress else 0,
            }

        data = execute_with_retry(_query)

        if data["project_status"] != "executing":
            self._all_done_emitted = False
            self._research_only_emitted = False
            return

        all_done = data["total_tasks"] > 0 and data["pending_tasks"] == 0
        research_only = (
            data["total_tasks"] > 0
            and data["non_research_open"] == 0
            and data["research_in_progress"] > 0
        )

        # Emit all_tasks_done when every task is done/cancelled
        if all_done and not self._all_done_emitted:
            logger.info(
                "All tasks done for project %d (%d total)",
                self.project_id, data["total_tasks"],
            )
            self.bus.emit(FlowEvent(
                event_type="all_tasks_done",
                project_id=self.project_id,
                entity_type="project",
                entity_id=self.project_id,
                data=data,
            ))
            self._all_done_emitted = True
            self._research_only_emitted = False
        elif not all_done:
            self._all_done_emitted = False

        # Emit waiting_for_research when only research tasks remain in progress
        if research_only and not self._research_only_emitted and not all_done:
            logger.info(
                "Only research tasks running for project %d (%d research in progress)",
                self.project_id, data["research_in_progress"],
            )
            self.bus.emit(FlowEvent(
                event_type="waiting_for_research",
                project_id=self.project_id,
                entity_type="project",
                entity_id=self.project_id,
                data=data,
            ))
            self._research_only_emitted = True
        elif not research_only:
            self._research_only_emitted = False


class EpicCreatedListener(BaseEventListener):
    """Listen for new epics being created."""

    def __init__(self, project_id: int, **kwargs: Any) -> None:
        super().__init__(project_id, **kwargs)
        self._last_event_id: int = 0
        self._initialize_last_event_id()

    def _initialize_last_event_id(self) -> None:
        def _query(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT MAX(id) as max_id FROM events_log WHERE project_id = ?",
                (self.project_id,),
            ).fetchone()
            return row["max_id"] if row and row["max_id"] else 0

        self._last_event_id = execute_with_retry(_query)

    def check(self) -> None:
        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, entity_id, event_data_json
                   FROM events_log
                   WHERE project_id = ?
                     AND id > ?
                     AND event_type = 'epic_created'
                   ORDER BY id ASC""",
                (self.project_id, self._last_event_id),
            ).fetchall()
            return [dict(r) for r in rows]

        events = execute_with_retry(_query)

        for ev in events:
            self._last_event_id = ev["id"]
            self.bus.emit(FlowEvent(
                event_type="epic_created",
                project_id=self.project_id,
                entity_type="epic",
                entity_id=ev.get("entity_id"),
            ))


# ── Listener manager ─────────────────────────────────────────────────────────


class ListenerManager:
    """Manages all event listeners for a project."""

    def __init__(self, project_id: int, bus: EventBus | None = None) -> None:
        self.project_id = project_id
        self.bus = bus or event_bus
        self._listeners: list[BaseEventListener] = []

    def start_all(self) -> None:
        """Start all default listeners for the project."""
        from backend.communication.listeners import (
            AgentMessageListener,
            CommunicationLoopListener,
            TicketCheckinListener,
        )

        self._listeners = [
            TaskStatusChangedListener(self.project_id, bus=self.bus),
            NewTaskCreatedListener(self.project_id, bus=self.bus),
            UserMessageListener(self.project_id, bus=self.bus),
            StagnationDetectedListener(self.project_id, bus=self.bus),
            AllTasksDoneListener(self.project_id, bus=self.bus),
            EpicCreatedListener(self.project_id, bus=self.bus),
            AgentMessageListener(self.project_id, bus=self.bus),
            TicketCheckinListener(self.project_id, bus=self.bus),
            CommunicationLoopListener(self.project_id, bus=self.bus),
        ]
        for listener in self._listeners:
            listener.start()
        logger.info(
            "Started %d event listeners for project %d",
            len(self._listeners), self.project_id,
        )

    def wire_flow_handlers(self) -> None:
        """Subscribe event handlers that trigger flow invocations.

        Maps:
        - task_review_ready → start CodeReviewFlow
        - task_status_changed (rejected) → notify developer via send_agent_message
        - stagnation_detected → trigger BrainstormingFlow
        - all_tasks_done → prompt completion checks via MainProjectFlow
        """
        self.bus.subscribe("task_review_ready", self._handle_task_review_ready)
        self.bus.subscribe("task_status_changed", self._handle_task_rejected)
        self.bus.subscribe("stagnation_detected", self._handle_stagnation)
        self.bus.subscribe("all_tasks_done", self._handle_all_tasks_done)
        self.bus.subscribe("waiting_for_research", self._handle_waiting_for_research)
        self.bus.subscribe("agent_message_received", self._handle_agent_message_received)
        self.bus.subscribe("ticket_checkin_approved", self._handle_ticket_checkin_approved)
        self.bus.subscribe("communication_loop_detected", self._handle_communication_loop)
        logger.info("Wired flow handlers for project %d", self.project_id)

    def _handle_task_review_ready(self, event: FlowEvent) -> None:
        """Start a CodeReviewFlow when a task is ready for review.

        Guarded: skips if a code_reviewer agent_run is already active for this
        task (prevents duplicate flows when DevelopmentFlow directly invokes
        CodeReviewFlow).
        """
        from backend.flows.code_review_flow import CodeReviewFlow
        from backend.flows.helpers import get_task_by_id, has_active_review_run

        if event.entity_id is None:
            logger.warning("Wiring: task_review_ready event with no entity_id, skipping")
            return

        if has_active_review_run(event.entity_id):
            logger.info(
                "Wiring: CodeReviewFlow already active for task %d, skipping",
                event.entity_id,
            )
            return

        task = get_task_by_id(event.entity_id)
        branch_name = task.get("branch_name", "") if task else ""

        logger.info(
            "Wiring: starting CodeReviewFlow for task %d (project %d)",
            event.entity_id, event.project_id,
        )
        flow = CodeReviewFlow()
        flow.kickoff(inputs={
            "project_id": event.project_id,
            "task_id": event.entity_id,
            "branch_name": branch_name,
        })

    def _handle_task_rejected(self, event: FlowEvent) -> None:
        """Notify the developer when a task is rejected."""
        from backend.flows.helpers import send_agent_message

        new_status = event.data.get("new_status", "")
        if new_status != "rejected":
            return

        logger.info(
            "Wiring: notifying developer about rejected task %d (project %d)",
            event.entity_id, event.project_id,
        )
        send_agent_message(
            project_id=event.project_id,
            from_agent="code_reviewer",
            to_agent=None,
            to_role="developer",
            message=(
                f"Task {event.entity_id} has been rejected. "
                f"Please review the feedback and address the issues."
            ),
        )

    def _handle_agent_message_received(self, event: FlowEvent) -> None:
        """Route agent-to-agent messages to the target agent's active flow."""
        data = event.data
        target_type = data.get("target_type", "unknown")
        target_id = data.get("target_id")
        from_agent = data.get("from_agent", "unknown")
        content = data.get("content", "")

        logger.info(
            "Wiring: agent message %d received (target_type=%s, target_id=%s)",
            data.get("message_id", 0), target_type, target_id,
        )

        # Resolve agent IDs to notify
        agent_ids: list[str] = []
        if target_type == "agent" and target_id:
            agent_ids = [target_id]
        elif target_type == "role" and target_id:
            # Look up all agents with this role from the roster
            agent_ids = self._resolve_agents_for_role(event.project_id, target_id)
        elif target_type == "broadcast":
            agent_ids = self._resolve_all_agents(event.project_id)

        if not agent_ids:
            logger.debug(
                "No agents resolved for target_type=%s target_id=%s",
                target_type, target_id,
            )
            return

        # Dispatch a Crew task for each target agent in a background thread
        for agent_id in agent_ids:
            t = threading.Thread(
                target=self._dispatch_message_to_agent,
                args=(event.project_id, agent_id, from_agent, content),
                name=f"MsgDispatch-{data.get('message_id', 0)}-{agent_id}",
                daemon=True,
            )
            t.start()

    def _resolve_agents_for_role(self, project_id: int, role: str) -> list[str]:
        """Look up agent IDs from the roster for a given role and project."""
        def _query(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """SELECT agent_id FROM roster
                   WHERE agent_id LIKE ? ESCAPE '\\' AND role = ? AND status != 'retired'""",
                (f"%\\_p{project_id}", role),
            ).fetchall()
            return [r["agent_id"] for r in rows]

        return execute_with_retry(_query)

    def _resolve_all_agents(self, project_id: int) -> list[str]:
        """Look up all active agent IDs from the roster for a project."""
        def _query(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """SELECT agent_id FROM roster
                   WHERE agent_id LIKE ? ESCAPE '\\' AND status != 'retired'""",
                (f"%\\_p{project_id}",),
            ).fetchall()
            return [r["agent_id"] for r in rows]

        return execute_with_retry(_query)

    def _resolve_agent_identity(
        self, project_id: int, agent_id: str,
    ) -> tuple[str, str] | None:
        """Resolve an agent identifier (ID or display name) to *(canonical_id, role)*.

        Returns ``None`` when no matching roster entry is found.
        """
        def _query(conn: sqlite3.Connection) -> tuple[str, str] | None:
            # 1. Try exact agent_id match
            row = conn.execute(
                "SELECT agent_id, role FROM roster WHERE agent_id = ? AND status != 'retired'",
                (agent_id,),
            ).fetchone()
            if row:
                return (row["agent_id"], row["role"])

            # 2. Try matching by display name within this project
            row = conn.execute(
                """SELECT agent_id, role FROM roster
                   WHERE LOWER(name) = LOWER(?)
                     AND agent_id LIKE ? ESCAPE '\\'
                     AND status != 'retired'""",
                (agent_id, f"%\\_p{project_id}"),
            ).fetchone()
            if row:
                return (row["agent_id"], row["role"])

            # 3. Try name embedded in agent_id (e.g. "team_lead_harper")
            row = conn.execute(
                """SELECT agent_id, role FROM roster
                   WHERE LOWER(?) LIKE LOWER(role || '_%')
                     AND agent_id LIKE ? ESCAPE '\\'
                     AND status != 'retired'
                   ORDER BY LENGTH(role) DESC LIMIT 1""",
                (agent_id, f"%\\_p{project_id}"),
            ).fetchone()
            if row:
                return (row["agent_id"], row["role"])

            return None

        return execute_with_retry(_query)

    def _dispatch_message_to_agent(
        self,
        project_id: int,
        agent_id: str,
        from_agent: str,
        content: str,
    ) -> None:
        """Run a Crew task so the target agent processes the incoming message."""
        from backend.agents.registry import get_agent_by_role

        try:
            # Resolve agent_id (may be a display name or composite like "role_name")
            resolved = self._resolve_agent_identity(project_id, agent_id)
            if resolved is None:
                logger.warning(
                    "Cannot resolve agent '%s' in project %d — skipping dispatch.",
                    agent_id, project_id,
                )
                return
            canonical_id, role = resolved

            agent = get_agent_by_role(role, project_id, agent_id=canonical_id)
            agent.activate_context()

            from crewai import Crew, Task as CrewTask
            crew = Crew(
                agents=[agent.crewai_agent],
                tasks=[CrewTask(
                    description=(
                        f"You have received a message from {from_agent}:\n\n"
                        f"{content}\n\n"
                        "Read and process this message. If it requires action, "
                        "take the appropriate steps using your available tools. "
                        "If it requires a response, use SendMessage to reply."
                    ),
                    agent=agent.crewai_agent,
                    expected_output="Action taken or response sent.",
                )],
                verbose=True,
            )
            crew.kickoff()
            logger.info(
                "Message dispatched to agent %s (project %d) from %s",
                agent_id, project_id, from_agent,
            )
        except Exception:
            logger.exception(
                "Failed to dispatch message to agent %s (project %d)",
                agent_id, project_id,
            )

    def _handle_ticket_checkin_approved(self, event: FlowEvent) -> None:
        """Signal the DevelopmentFlow that the check-in gate has been passed."""
        logger.info(
            "Wiring: ticket check-in approved for task %d (project %d)",
            event.entity_id or 0, event.project_id,
        )

    def _handle_stagnation(self, event: FlowEvent) -> None:
        """Notify team lead about stagnation for analysis and intervention.

        Previously this launched a BrainstormingFlow (which creates MORE tasks
        instead of unblocking stuck ones).  Now we just emit the event so that
        ``MainProjectFlow.handle_stagnation`` can have the Team Lead analyze
        and intervene on each stuck task.
        """
        from backend.flows.helpers import send_agent_message

        logger.info(
            "Wiring: stagnation detected for project %d, notifying team lead",
            event.project_id,
        )
        send_agent_message(
            project_id=event.project_id,
            from_agent="system",
            to_agent=None,
            to_role="team_lead",
            message=(
                f"Stagnation detected for project {event.project_id}: "
                f"{event.data.get('stuck_tasks', '?')} tasks stuck with no "
                f"recent completions. Please analyze and unblock."
            ),
        )

    def _handle_waiting_for_research(self, event: FlowEvent) -> None:
        """Notify when only research tasks remain in progress."""
        from backend.flows.helpers import send_agent_message

        logger.info(
            "Wiring: only research tasks running for project %d",
            event.project_id,
        )
        send_agent_message(
            project_id=event.project_id,
            from_agent="system",
            to_agent=None,
            to_role="project_lead",
            message=(
                f"Project {event.project_id} is waiting for research tasks to complete. "
                f"Please review the findings once research is done and decide on next steps."
            ),
        )

    def _handle_all_tasks_done(self, event: FlowEvent) -> None:
        """Prompt completion checks when all tasks are done."""
        from backend.flows.helpers import send_agent_message
        from backend.state.completion import CompletionDetector, CompletionState

        logger.info(
            "Wiring: all tasks done for project %d, checking objectives",
            event.project_id,
        )
        state = CompletionDetector.detect(event.project_id)

        if state == CompletionState.IDLE_OBJECTIVES_MET:
            send_agent_message(
                project_id=event.project_id,
                from_agent="system",
                to_agent=None,
                to_role="project_lead",
                message=(
                    f"All tasks for project {event.project_id} are complete "
                    f"and all objectives have been met. "
                    f"Please finalize the project."
                ),
            )
        elif state == CompletionState.WAITING_FOR_RESEARCH:
            send_agent_message(
                project_id=event.project_id,
                from_agent="system",
                to_agent=None,
                to_role="project_lead",
                message=(
                    f"Project {event.project_id} is waiting for research tasks to complete. "
                    f"Please review the findings once research is done and decide on next steps."
                ),
            )
        else:
            # IDLE_OBJECTIVES_PENDING or ACTIVE (shouldn't happen here but handle gracefully)
            send_agent_message(
                project_id=event.project_id,
                from_agent="system",
                to_agent=None,
                to_role="team_lead",
                message=(
                    f"All current tasks for project {event.project_id} are done, "
                    f"but not all objectives are met. "
                    f"Consider creating additional tasks or starting a brainstorming session."
                ),
            )

    def _handle_communication_loop(self, event: FlowEvent) -> None:
        """Handle communication loop detection — notify user via WebSocket."""
        from backend.flows.helpers import send_agent_message

        agents = event.data.get("agents", [])
        thread_id = event.data.get("thread_id", "unknown")
        logger.warning(
            "Wiring: communication loop detected in thread %s between %s (project %d)",
            thread_id, agents, event.project_id,
        )
        send_agent_message(
            project_id=event.project_id,
            from_agent="system",
            to_agent=None,
            to_role="team_lead",
            message=(
                f"Communication loop detected in thread {thread_id} "
                f"between agents {', '.join(agents)}. "
                f"The loop has been automatically broken. "
                f"Please review and take corrective action if needed."
            ),
        )

    def stop_all(self) -> None:
        """Stop all running listeners."""
        for listener in self._listeners:
            listener.stop()
        self._listeners.clear()
        logger.info("Stopped all event listeners for project %d", self.project_id)

    def add_listener(self, listener: BaseEventListener) -> None:
        """Add and start a custom listener."""
        self._listeners.append(listener)
        listener.start()

    @property
    def listeners(self) -> list[BaseEventListener]:
        return list(self._listeners)
