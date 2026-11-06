"""Retain actual legacy worker liveness and Stop during native cutover; project start only returns the owner entry and preserves historical data."""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.flows.event_listeners import ListenerManager

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

    def start_project_flow(self, project_id: int) -> dict[str, Any]:
        """Return native owner policy before importing old flows, creating workers, clearing messages or resuming snapshots."""
        from backend.runtime.legacy_handoff import legacy_project_handoff

        return legacy_project_handoff(project_id)

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
