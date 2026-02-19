"""Cleanup manager — removes stale containers and orphaned workspaces."""

import logging
import sqlite3
import threading

from backend.security.container_runtime import get_runtime, runtime_available
from backend.security.workspace_manager import workspace_manager
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class CleanupManager:
    """Periodic cleanup of sandbox containers and agent workspaces."""

    def __init__(self, ws_manager=None):
        self._ws_manager = ws_manager or workspace_manager
        self._timer: threading.Timer | None = None
        self._running = False

    # ── Container cleanup ───────────────────────────────────────────────

    def cleanup_stale_containers(self) -> int:
        """Remove all exited pabada-sandbox-* containers. Returns count removed."""
        if not runtime_available():
            return 0

        runtime = get_runtime()
        stale = runtime.list_stale_containers("pabada-sandbox-")
        removed = 0
        for c in stale:
            if runtime.remove_container(c["id"]):
                removed += 1
                logger.info("Removed stale container %s (%s)", c["name"], c["id"])
        return removed

    # ── Workspace cleanup ───────────────────────────────────────────────

    def cleanup_agent_workspace(self, agent_id: str) -> None:
        """Remove an agent's workspace if the agent is idle or completed."""
        if not self._agent_is_inactive(agent_id):
            logger.debug("Agent %s is still active — skipping workspace cleanup", agent_id)
            return
        self._ws_manager.remove_workspace(agent_id)

    def cleanup_all_stale(self, project_id: int | None = None) -> None:
        """Run full cleanup: stale containers + orphaned workspaces."""
        self.cleanup_stale_containers()

        inactive_agents = self._list_inactive_agents(project_id)
        for aid in inactive_agents:
            if self._ws_manager.workspace_exists(aid):
                self._ws_manager.remove_workspace(aid)
                logger.info("Cleaned up workspace for inactive agent %s", aid)

    # ── Periodic scheduling ─────────────────────────────────────────────

    def schedule_periodic_cleanup(self, interval_seconds: int = 300) -> None:
        """Start a daemon thread that runs cleanup_stale_containers periodically."""
        if self._running:
            return

        self._running = True

        def _loop():
            while self._running:
                try:
                    removed = self.cleanup_stale_containers()
                    if removed:
                        logger.info("Periodic cleanup removed %d stale containers", removed)
                except Exception:
                    logger.warning("Periodic cleanup failed", exc_info=True)

                # Sleep in small increments so we can stop quickly
                event = threading.Event()
                event.wait(timeout=interval_seconds)

        t = threading.Thread(target=_loop, daemon=True, name="pabada-cleanup")
        t.start()
        logger.info("Periodic cleanup started (interval=%ds)", interval_seconds)

    def stop_periodic_cleanup(self) -> None:
        self._running = False

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _agent_is_inactive(agent_id: str) -> bool:
        """Check if an agent is idle or completed in the roster table."""
        try:
            result = {"inactive": False}

            def _check(conn: sqlite3.Connection):
                row = conn.execute(
                    "SELECT status FROM roster WHERE agent_id = ?", (agent_id,)
                ).fetchone()
                if row is None or row[0] in ("idle", "completed", "failed"):
                    result["inactive"] = True

            execute_with_retry(_check)
            return result["inactive"]
        except Exception:
            # If we can't check, assume active to be safe
            return False

    @staticmethod
    def _list_inactive_agents(project_id: int | None = None) -> list[str]:
        """Return agent_ids that are idle/completed/failed."""
        agents: list[str] = []

        def _query(conn: sqlite3.Connection):
            sql = "SELECT agent_id FROM roster WHERE status IN ('idle', 'completed', 'failed')"
            params: list = []
            if project_id is not None:
                sql += " AND project_id = ?"
                params.append(project_id)
            for row in conn.execute(sql, params):
                agents.append(row[0])

        try:
            execute_with_retry(_query)
        except Exception:
            logger.debug("Failed to list inactive agents", exc_info=True)
        return agents


# ── Module-level singleton ──────────────────────────────────────────────────

cleanup_manager = CleanupManager()
