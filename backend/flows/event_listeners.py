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
            elif new_status == "rejected":
                self.bus.emit(FlowEvent(
                    event_type="task_rejected",
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
                event_type="task_created",
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
                     AND type NOT IN ('research', 'investigation')""",
                (self.project_id,),
            ).fetchone()

            # Count research/investigation tasks still in progress
            research_in_progress = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ?
                     AND status = 'in_progress'
                     AND type IN ('research', 'investigation')""",
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


# ── Agent resolver ────────────────────────────────────────────────────────────


class AgentResolver:
    """Resolves agent identifiers and roles from the roster table."""

    def resolve_for_role(self, project_id: int, role: str) -> list[str]:
        """Look up agent IDs from the roster for a given role and project."""
        def _query(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """SELECT agent_id FROM roster
                   WHERE agent_id LIKE ? ESCAPE '\\' AND role = ? AND status != 'retired'""",
                (f"%\\_p{project_id}", role),
            ).fetchall()
            return [r["agent_id"] for r in rows]

        return execute_with_retry(_query)

    def resolve_all(self, project_id: int) -> list[str]:
        """Look up all active agent IDs from the roster for a project."""
        def _query(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """SELECT agent_id FROM roster
                   WHERE agent_id LIKE ? ESCAPE '\\' AND status != 'retired'""",
                (f"%\\_p{project_id}",),
            ).fetchall()
            return [r["agent_id"] for r in rows]

        return execute_with_retry(_query)

    def resolve_identity(
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


# ── Listener manager ─────────────────────────────────────────────────────────
# (FlowEventHandlersMixin removed — agent work routing now uses
#  persistent agent_events via AgentLoop instead of ephemeral EventBus handlers)


class ListenerManager:
    """Manages event listeners for a project.

    Listeners emit to the EventBus for WebSocket relay to the frontend.
    Agent work scheduling is now handled by AgentLoop via persistent
    agent_events in the DB — these handlers create agent_events for
    aggregate conditions (stagnation, all-tasks-done) detected by listeners.
    """

    def __init__(self, project_id: int, bus: EventBus | None = None) -> None:
        self.project_id = project_id
        self.bus = bus or event_bus
        self._listeners: list[BaseEventListener] = []

    def start_all(self) -> None:
        """Start all default listeners for the project."""
        from backend.communication.listeners import CommunicationLoopListener

        self._listeners = [
            TaskStatusChangedListener(self.project_id, bus=self.bus),
            NewTaskCreatedListener(self.project_id, bus=self.bus),
            UserMessageListener(self.project_id, bus=self.bus),
            StagnationDetectedListener(self.project_id, bus=self.bus),
            AllTasksDoneListener(self.project_id, bus=self.bus),
            EpicCreatedListener(self.project_id, bus=self.bus),
            CommunicationLoopListener(self.project_id, bus=self.bus),
        ]
        for listener in self._listeners:
            listener.start()
        logger.info(
            "Started %d event listeners for project %d",
            len(self._listeners), self.project_id,
        )

    def wire_flow_handlers(self) -> None:
        """Subscribe handlers for aggregate events → persistent agent_events.

        Agent work routing is handled by AgentLoop via persistent DB events.
        These handlers create agent_events for conditions detected by listeners.
        """
        self.bus.subscribe("task_created", self._create_task_available_events)
        self.bus.subscribe("stagnation_detected", self._create_stagnation_events)
        self.bus.subscribe("all_tasks_done", self._create_all_done_events)
        self.bus.subscribe("waiting_for_research", self._create_waiting_events)
        self.bus.subscribe("task_rejected", self._create_task_rejected_events)
        self.bus.subscribe("communication_loop_detected", self._handle_communication_loop)
        logger.info("Wired flow handlers for project %d", self.project_id)

    def _create_task_available_events(self, event: FlowEvent) -> None:
        """Create persistent agent_events when a new task is created.

        This bridges the gap between the DB trigger (events_log) and the
        agent loop system (agent_events).  Without this, agent loops never
        learn about newly created tasks.
        """
        try:
            from backend.autonomy.events import create_task_event

            task_id = event.entity_id
            if task_id is None:
                return

            task_data = event.data or {}
            task_type = task_data.get("type", "code")

            if task_type in ("research", "investigation"):
                target_role = "researcher"
            elif task_type == "review":
                target_role = "code_reviewer"
            else:
                target_role = "developer"

            create_task_event(
                event.project_id, task_id, "task_available",
                target_role=target_role,
                source="task_created_listener",
                extra_payload={
                    "task_type": task_type,
                    "task_title": task_data.get("title", ""),
                },
            )
        except Exception:
            logger.debug("Could not create task_available events for task %s", event.entity_id, exc_info=True)

    def _create_stagnation_events(self, event: FlowEvent) -> None:
        """Create agent_events for team leads when stagnation is detected."""
        try:
            from backend.autonomy.events import _resolve_agents_for_role, create_system_event

            team_leads = _resolve_agents_for_role(event.project_id, "team_lead")
            for agent_id in team_leads:
                create_system_event(
                    event.project_id, agent_id, "stagnation_detected",
                    payload=event.data,
                )
        except Exception:
            logger.debug("Could not create stagnation events", exc_info=True)

    def _create_all_done_events(self, event: FlowEvent) -> None:
        """Create agent_events when all tasks are done."""
        try:
            from backend.autonomy.events import _resolve_agents_for_role, create_system_event

            for role in ("team_lead", "project_lead"):
                agents = _resolve_agents_for_role(event.project_id, role)
                for agent_id in agents:
                    create_system_event(
                        event.project_id, agent_id, "all_tasks_done",
                        payload=event.data,
                    )
        except Exception:
            logger.debug("Could not create all_done events", exc_info=True)

    def _create_waiting_events(self, event: FlowEvent) -> None:
        """Create agent_events when only research tasks remain."""
        try:
            from backend.autonomy.events import _resolve_agents_for_role, create_system_event

            project_leads = _resolve_agents_for_role(event.project_id, "project_lead")
            for agent_id in project_leads:
                create_system_event(
                    event.project_id, agent_id, "waiting_for_research",
                    payload=event.data,
                )
        except Exception:
            logger.debug("Could not create waiting_for_research events", exc_info=True)

    def _create_task_rejected_events(self, event: FlowEvent) -> None:
        """Create persistent agent_events when a task is rejected."""
        try:
            from backend.autonomy.events import create_task_event

            task_id = event.entity_id
            if task_id is None:
                return

            task_data = self._get_task_assignment(task_id)
            if not task_data or not task_data.get("assigned_to"):
                return

            create_task_event(
                event.project_id, task_id, "task_rejected",
                target_agent_id=task_data["assigned_to"],
                source="task_rejected_listener",
                extra_payload={"task_type": task_data.get("type", "code")},
            )
        except Exception:
            logger.debug("Could not create task_rejected events", exc_info=True)

    def _get_task_assignment(self, task_id: int) -> dict[str, Any] | None:
        """Query tasks table for assigned_to and type."""
        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT assigned_to, type FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def _handle_communication_loop(self, event: FlowEvent) -> None:
        """Handle communication loop detection — notify user via WebSocket.

        Sends the alert INTO the original thread (not a random UUID) and
        deduplicates: if a system loop-detection message was already posted
        in this thread within the last 5 minutes, skip.
        """
        import sqlite3 as _sqlite3

        from backend.flows.helpers import send_agent_message
        from backend.tools.base.db import execute_with_retry as _exec

        agents = event.data.get("agents", [])
        thread_id = event.data.get("thread_id", "unknown")

        # Deduplicate: check if we already posted a loop alert in this thread recently
        def _has_recent_alert(conn: _sqlite3.Connection) -> bool:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM chat_messages
                   WHERE thread_id = ?
                     AND from_agent = 'system'
                     AND message LIKE '%Communication loop detected%'
                     AND created_at > datetime('now', '-5 minutes')""",
                (thread_id,),
            ).fetchone()
            return (row["cnt"] if row else 0) > 0

        try:
            already_alerted = _exec(_has_recent_alert)
        except Exception:
            already_alerted = False

        if already_alerted:
            logger.debug(
                "Skipping duplicate loop alert for thread %s (project %d)",
                thread_id, event.project_id,
            )
            return

        logger.warning(
            "Communication loop detected in thread %s between %s (project %d)",
            thread_id, agents, event.project_id,
        )
        send_agent_message(
            project_id=event.project_id,
            from_agent="system",
            to_agent=None,
            to_role="team_lead",
            thread_id=thread_id,
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


