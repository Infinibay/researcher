"""Manages active CrewAI flows and event listeners per project."""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.flows.event_listeners import ListenerManager, event_bus
from backend.flows.helpers import load_project_state, update_project_status

logger = logging.getLogger(__name__)


class FlowManager:
    """Tracks running flows and listener managers across projects."""

    def __init__(self) -> None:
        self._flows: dict[int, Any] = {}
        self._listeners: dict[int, ListenerManager] = {}
        self._lock = threading.Lock()

    def start_project_flow(self, project_id: int) -> None:
        """Start the MainProjectFlow and event listeners for a project."""
        from backend.flows.main_project_flow import MainProjectFlow

        with self._lock:
            if project_id in self._flows:
                logger.warning("Flow already running for project %d", project_id)
                return

            # Start listeners
            lm = ListenerManager(project_id, bus=event_bus)
            lm.start_all()
            lm.wire_flow_handlers()
            self._listeners[project_id] = lm

            # Start flow in a background thread to avoid blocking
            flow = MainProjectFlow()
            self._flows[project_id] = flow

            thread = threading.Thread(
                target=self._run_flow,
                args=(flow, project_id),
                name=f"MainProjectFlow-p{project_id}",
                daemon=True,
            )
            thread.start()

            update_project_status(project_id, "executing")
            logger.info("Started flow and listeners for project %d", project_id)

    def _run_flow(self, flow: Any, project_id: int) -> None:
        """Run the flow in a thread. Cleans up on completion."""
        try:
            flow.kickoff(inputs={"project_id": project_id})
        except Exception:
            logger.exception("Flow failed for project %d", project_id)
        finally:
            with self._lock:
                self._flows.pop(project_id, None)

    def stop_project_flow(self, project_id: int) -> None:
        """Stop listeners for a project. Flows are harder to interrupt."""
        with self._lock:
            lm = self._listeners.pop(project_id, None)
            if lm:
                lm.stop_all()
            self._flows.pop(project_id, None)
            update_project_status(project_id, "paused")
            logger.info("Stopped flow/listeners for project %d", project_id)

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
