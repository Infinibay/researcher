"""Workspace isolation — one directory per agent."""

import logging
import shutil
from pathlib import Path

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages isolated workspace directories for each agent."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.WORKSPACE_BASE_DIR)

    def get_workspace(self, agent_id: str) -> Path:
        """Create (if needed) and return the workspace path for an agent."""
        ws = self.base_dir / agent_id
        ws.mkdir(parents=True, exist_ok=True)
        ws.chmod(0o755)
        return ws

    def workspace_exists(self, agent_id: str) -> bool:
        return (self.base_dir / agent_id).is_dir()

    def list_workspaces(self) -> list[str]:
        """List all agent IDs that have a workspace directory."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def remove_workspace(self, agent_id: str) -> None:
        """Remove an agent's workspace directory (best-effort)."""
        ws = self.base_dir / agent_id
        if ws.exists():
            try:
                shutil.rmtree(ws)
                logger.info("Removed workspace for agent %s", agent_id)
            except Exception:
                logger.warning(
                    "Failed to remove workspace for agent %s", agent_id, exc_info=True
                )


# ── Module-level singleton ──────────────────────────────────────────────────

workspace_manager = WorkspaceManager()
