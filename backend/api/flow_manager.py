"""Manages active CrewAI flows and event listeners per project."""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.agents.registry import initialize_project_team
from backend.config.settings import settings
from backend.flows.event_listeners import ListenerManager, event_bus
from backend.flows.helpers import update_project_status

logger = logging.getLogger(__name__)


class FlowManager:
    """Tracks running flows and listener managers across projects."""

    def __init__(self) -> None:
        """Track actual main/autonomy/listener workers and their own cooperative stop signals, without starting execution."""
        self._flows: dict[int, Any] = {}
        self._threads: dict[int, threading.Thread] = {}
        self._stop_signals: dict[int, threading.Event] = {}
        self._listeners: dict[int, ListenerManager] = {}
        self._autonomy: dict[int, Any] = {}
        self._lock = threading.Lock()

    def start_project_flow(self, project_id: int) -> dict[str, Any] | None:
        """Start remaining legacy projects only; native admission returns an owner hint before listeners, workers or stale-event clearing."""
        from backend.runtime.legacy_handoff import legacy_project_handoff

        handoff = legacy_project_handoff(project_id)
        if handoff is not None:
            return handoff
        from backend.flows.main_project_flow import MainProjectFlow
        from backend.flows.snapshot_service import load_snapshot

        with self._lock:
            if self.is_project_running(project_id):
                logger.warning("Flow already running for project %d", project_id)
                return

            # Start listeners
            lm = ListenerManager(project_id, bus=event_bus)
            lm.start_all()
            lm.wire_flow_handlers()
            self._listeners[project_id] = lm

            # Ensure all team workers exist (idempotent)
            initialize_project_team(project_id)

            # Clear stale agent events from previous sessions to prevent
            # loops from processing old messages when they resume.
            self._clear_stale_events(project_id)

            # Load snapshot to restore state on resume
            snapshot_inputs: dict[str, Any] = {}
            snapshot = load_snapshot(project_id)
            if snapshot and snapshot.get("state_json"):
                try:
                    import json

                    parsed = json.loads(snapshot["state_json"])
                    if isinstance(parsed, dict):
                        snapshot_inputs = parsed
                    else:
                        logger.warning(
                            "Snapshot state_json for project %d is not a dict (got %s), ignoring",
                            project_id,
                            type(parsed).__name__,
                        )
                    logger.info(
                        "Loaded snapshot for project %d (step=%s)",
                        project_id,
                        snapshot.get("current_step", "?"),
                    )
                except Exception:
                    logger.warning(
                        "Could not parse snapshot state_json for project %d",
                        project_id,
                        exc_info=True,
                    )

            # Start flow in a background thread to avoid blocking
            flow = MainProjectFlow()
            self._flows[project_id] = flow

            signal = threading.Event()
            self._stop_signals[project_id] = signal
            thread = threading.Thread(
                target=self._run_flow,
                args=(flow, project_id, snapshot_inputs, signal),
                name=f"MainProjectFlow-p{project_id}",
                daemon=True,
            )
            self._threads[project_id] = thread
            thread.start()

            # Start agent loops paused — the flow resumes them when entering
            # execution phase.  This prevents loops from processing stale events
            # or interfering while the flow drives agents during planning.
            if settings.AUTONOMY_ENABLED:
                from backend.autonomy.agent_loop import AgentLoopManager

                loop_mgr = AgentLoopManager(project_id)
                loop_mgr.start_all()
                loop_mgr.pause_all()
                self._autonomy[project_id] = loop_mgr

            logger.info("Started flow and listeners for project %d", project_id)

    def _run_flow(
        self,
        flow: Any,
        project_id: int,
        snapshot_inputs: dict[str, Any] | None = None,
        stop_requested: threading.Event | None = None,
    ) -> None:
        """Run the flow in a thread. Cleans up on completion."""
        try:
            inputs: dict[str, Any] = {"project_id": project_id}
            if snapshot_inputs:
                # Merge snapshot state — snapshot values take precedence except project_id
                merged = {**snapshot_inputs, **inputs}
                inputs = merged
            from backend.runtime.legacy_scope import legacy_stop_scope

            with legacy_stop_scope(project_id, stop_requested or threading.Event()):
                flow.kickoff(inputs=inputs)
        except Exception:
            logger.exception("Flow failed for project %d", project_id)
        finally:
            with self._lock:
                if self._flows.get(project_id) is flow:
                    self._flows.pop(project_id, None)

    def stop_project_flow(self, project_id: int) -> dict[str, Any]:
        """Signal and observe registered legacy controllers without dropping live references, holding the registry lock during joins or resetting native-owned tasks."""
        with self._lock:
            flow = self._flows.get(project_id)
            thread = self._threads.get(project_id)
            signal = self._stop_signals.get(project_id)
            from backend.autonomy.agent_loop import get_loop_manager

            loop_mgr = self._autonomy.get(project_id) or get_loop_manager(project_id)
            listeners = self._listeners.get(project_id)
        if signal is not None:
            signal.set()
        if flow is not None and hasattr(flow, "state"):
            try:
                from backend.flows.snapshot_service import save_snapshot

                save_snapshot(
                    project_id,
                    "main_project_flow",
                    getattr(flow.state, "current_step", "") or flow.state.status.value,
                    flow.state,
                )
            except Exception:
                logger.warning(
                    "Could not snapshot legacy flow %d", project_id, exc_info=True
                )
        if loop_mgr is not None:
            loop_mgr.stop_signal()
            loop_mgr.stop_join()
        if listeners is not None:
            try:
                listeners.stop_all()
            except TimeoutError:
                logger.warning(
                    "Legacy listener still stopping for project %d", project_id
                )
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        with self._lock:
            if thread is not None and not thread.is_alive():
                if self._threads.get(project_id) is thread:
                    self._threads.pop(project_id, None)
                    self._stop_signals.pop(project_id, None)
                if self._flows.get(project_id) is flow:
                    self._flows.pop(project_id, None)
            if (
                loop_mgr is not None
                and not self._registered_running(loop_mgr)
                and self._autonomy.get(project_id) is loop_mgr
            ):
                self._autonomy.pop(project_id, None)
            if (
                listeners is not None
                and not self._registered_running(listeners)
                and self._listeners.get(project_id) is listeners
            ):
                self._listeners.pop(project_id, None)
            closed = not self.is_project_running(project_id)
        if closed:
            self._reset_in_progress_tasks(project_id)
            from backend.runtime.legacy_handoff import legacy_project_handoff

            if legacy_project_handoff(project_id) is None:
                update_project_status(project_id, "paused")
        return {
            "project_id": project_id,
            "stop_requested": True,
            "registered_workers_closed": closed,
            "closure_scope": "registered_legacy_threads_only",
        }

    @staticmethod
    def _registered_running(owner) -> bool:
        """Observe known controller liveness; an opaque registry entry remains unresolved rather than presumed closed."""
        observed = getattr(owner, "is_running", None)
        return observed if isinstance(observed, bool) else True

    @staticmethod
    def _reset_in_progress_tasks(project_id: int) -> None:
        """Reset in_progress tasks to pending during graceful shutdown.

        Since we just stopped all agent loops, any in_progress task has no
        agent working on it. Reset to pending so it gets picked up on restart.
        Also marks their in_progress events as failed with 'graceful_shutdown'.
        """
        import sqlite3

        def _reset(conn: sqlite3.Connection) -> int:
            """Check native ownership under the write lock before clearing any legacy task/event state."""
            from backend.runtime.legacy_handoff import native_project_handoff

            conn.execute("BEGIN IMMEDIATE")
            if native_project_handoff(conn, project_id) is not None:
                conn.rollback()
                return 0
            from backend.runtime.task_profiles import OWNER_ONLY_LEGACY_TASK_TYPES

            excluded = ",".join("?" for _ in OWNER_ONLY_LEGACY_TASK_TYPES)
            # Migrated task types remain owner-controlled even before the first run.
            cursor = conn.execute(
                f"""UPDATE tasks SET status = 'pending', assigned_to = NULL
                   WHERE project_id = ? AND status = 'in_progress' AND type NOT IN ({excluded})""",
                (project_id, *OWNER_ONLY_LEGACY_TASK_TYPES),
            )
            count = cursor.rowcount

            # Mark in_progress/claimed events as failed
            conn.execute(
                f"""UPDATE agent_events
                   SET status = 'failed',
                       error_message = 'graceful_shutdown',
                       completed_at = CURRENT_TIMESTAMP
                   WHERE project_id = ?
                     AND status IN ('in_progress', 'claimed')
                     AND NOT EXISTS(SELECT 1 FROM tasks t WHERE t.project_id=agent_events.project_id
                       AND t.id=CASE WHEN json_valid(agent_events.payload_json) THEN json_extract(agent_events.payload_json,'$.task_id') END
                       AND t.type IN ({excluded}))""",
                (project_id, *OWNER_ONLY_LEGACY_TASK_TYPES),
            )

            conn.commit()
            return count

        try:
            from backend.tools.base.db import execute_with_retry as _db_retry

            count = _db_retry(_reset)
            if count:
                logger.info(
                    "Graceful shutdown: reset %d in_progress tasks to pending for project %d",
                    count,
                    project_id,
                )
        except Exception:
            logger.warning(
                "Could not reset in_progress tasks for project %d",
                project_id,
                exc_info=True,
            )

    @staticmethod
    def _clear_stale_events(project_id: int) -> None:
        """Cancel pending/in-progress agent events left over from a previous session.

        Without this, agent loops would process stale messages from before
        the restart, causing duplicate work and ping-pong loops.
        """
        import sqlite3

        def _cancel(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """UPDATE agent_events
                   SET status = 'failed',
                       error_message = 'cancelled: stale event from previous session'
                   WHERE project_id = ?
                     AND status IN ('pending', 'in_progress')""",
                (project_id,),
            )
            conn.commit()
            return cursor.rowcount

        try:
            from backend.tools.base.db import execute_with_retry as _db_retry

            cancelled = _db_retry(_cancel)
            if cancelled:
                logger.info(
                    "Cleared %d stale agent events for project %d",
                    cancelled,
                    project_id,
                )
        except Exception:
            logger.debug(
                "Could not clear stale events for project %d",
                project_id,
                exc_info=True,
            )

    def get_flow_status(self, project_id: int) -> str:
        """Get the running status of a project's flow."""
        return "running" if self.is_project_running(project_id) else "stopped"

    def is_project_running(self, project_id: int) -> bool:
        """Detect every registered legacy owner; a finished flow thread does not prove its autonomy or listeners closed."""
        from backend.autonomy.agent_loop import get_loop_manager

        thread = self._threads.get(project_id)
        external = get_loop_manager(project_id)
        return (
            project_id in self._flows
            or (thread is not None and thread.is_alive())
            or (external is not None and self._registered_running(external))
            or (
                project_id in self._autonomy
                and self._registered_running(self._autonomy[project_id])
            )
            or (
                project_id in self._listeners
                and self._registered_running(self._listeners[project_id])
            )
        )


# Global instance
flow_manager = FlowManager()
