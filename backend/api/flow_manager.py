"""Manages active CrewAI flows and event listeners per project."""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.agents.registry import initialize_project_team
from backend.config.settings import settings
from backend.flows.event_listeners import ListenerManager, event_bus
from backend.flows.helpers import load_project_state, update_project_status

logger = logging.getLogger(__name__)


class FlowManager:
    """Tracks running flows and listener managers across projects."""

    def __init__(self) -> None:
        self._flows: dict[int, Any] = {}
        self._listeners: dict[int, ListenerManager] = {}
        self._autonomy: dict[int, Any] = {}
        self._lock = threading.Lock()

    def start_project_flow(self, project_id: int) -> None:
        """Start the MainProjectFlow and event listeners for a project."""
        from backend.flows.main_project_flow import MainProjectFlow
        from backend.flows.snapshot_service import load_snapshot

        with self._lock:
            if project_id in self._flows:
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
                            project_id, type(parsed).__name__,
                        )
                    logger.info(
                        "Loaded snapshot for project %d (step=%s)",
                        project_id, snapshot.get("current_step", "?"),
                    )
                except Exception:
                    logger.warning(
                        "Could not parse snapshot state_json for project %d",
                        project_id, exc_info=True,
                    )

            # Start flow in a background thread to avoid blocking
            flow = MainProjectFlow()
            self._flows[project_id] = flow

            thread = threading.Thread(
                target=self._run_flow,
                args=(flow, project_id, snapshot_inputs),
                name=f"MainProjectFlow-p{project_id}",
                daemon=True,
            )
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
        self, flow: Any, project_id: int, snapshot_inputs: dict[str, Any] | None = None,
    ) -> None:
        """Run the flow in a thread. Cleans up on completion."""
        try:
            inputs: dict[str, Any] = {"project_id": project_id}
            if snapshot_inputs:
                # Merge snapshot state — snapshot values take precedence except project_id
                merged = {**snapshot_inputs, **inputs}
                inputs = merged
            flow.kickoff(inputs=inputs)
        except Exception:
            logger.exception("Flow failed for project %d", project_id)
        finally:
            with self._lock:
                self._flows.pop(project_id, None)

    def stop_project_flow(self, project_id: int) -> None:
        """Stop listeners for a project. Snapshots flow state before teardown."""
        with self._lock:
            # Snapshot flow state before tearing down
            flow = self._flows.get(project_id)
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
                        "Could not snapshot flow for project %d",
                        project_id,
                        exc_info=True,
                    )

            # Stop agent loops — signal all loops first, then join.
            # Kill pods BEFORE joining so blocked exec_in_pod calls terminate.
            loop_mgr = self._autonomy.pop(project_id, None)
            if loop_mgr:
                loop_mgr.stop_signal()  # signal all stop events (non-blocking)

            if loop_mgr:
                loop_mgr.stop_join()  # now join threads (pods already dead)

            # Reset in_progress tasks to pending so they can be picked up on restart.
            # This runs AFTER agent loops are stopped, so no agent is actively working.
            self._reset_in_progress_tasks(project_id)

            lm = self._listeners.pop(project_id, None)
            if lm:
                lm.stop_all()
            self._flows.pop(project_id, None)
            update_project_status(project_id, "paused")
            logger.info("Stopped flow/listeners for project %d", project_id)

    @staticmethod
    def _reset_in_progress_tasks(project_id: int) -> None:
        """Reset in_progress tasks to pending during graceful shutdown.

        Since we just stopped all agent loops, any in_progress task has no
        agent working on it. Reset to pending so it gets picked up on restart.
        Also marks their in_progress events as failed with 'graceful_shutdown'.
        """
        import sqlite3

        def _reset(conn: sqlite3.Connection) -> int:
            # Reset tasks
            cursor = conn.execute(
                """UPDATE tasks SET status = 'pending', assigned_to = NULL
                   WHERE project_id = ? AND status = 'in_progress'""",
                (project_id,),
            )
            count = cursor.rowcount

            # Mark in_progress/claimed events as failed
            conn.execute(
                """UPDATE agent_events
                   SET status = 'failed',
                       error_message = 'graceful_shutdown',
                       completed_at = CURRENT_TIMESTAMP
                   WHERE project_id = ?
                     AND status IN ('in_progress', 'claimed')""",
                (project_id,),
            )

            conn.commit()
            return count

        try:
            from backend.tools.base.db import execute_with_retry as _db_retry

            count = _db_retry(_reset)
            if count:
                logger.info(
                    "Graceful shutdown: reset %d in_progress tasks to pending for project %d",
                    count, project_id,
                )
        except Exception:
            logger.warning(
                "Could not reset in_progress tasks for project %d",
                project_id, exc_info=True,
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
                    cancelled, project_id,
                )
        except Exception:
            logger.debug(
                "Could not clear stale events for project %d",
                project_id, exc_info=True,
            )

    def get_flow_status(self, project_id: int) -> str:
        """Get the running status of a project's flow."""
        if project_id in self._flows:
            return "running"
        return "stopped"

    def is_project_running(self, project_id: int) -> bool:
        """Check if a project's flow is currently running."""
        return project_id in self._flows


# Global instance
flow_manager = FlowManager()
