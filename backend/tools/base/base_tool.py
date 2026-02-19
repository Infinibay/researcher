"""Base tool class for all PABADA tools."""

import json
import logging
import os
import sqlite3
from abc import ABC
from typing import Any

from crewai.tools import BaseTool

from backend.config.settings import settings
from backend.tools.base.context import (
    get_context,
    get_current_agent_id,
    get_current_agent_run_id,
    get_current_project_id,
    get_current_task_id,
)
from backend.tools.base.db import DBConnection, execute_with_retry, get_db_path

logger = logging.getLogger(__name__)


class PabadaBaseTool(BaseTool, ABC):
    """Abstract base class for all PABADA tools.

    Provides:
    - Database access with retry logic
    - Context awareness (project_id, agent_id, etc.)
    - Audit logging of tool usage
    - Standard error handling
    """

    @property
    def project_id(self) -> int | None:
        return get_current_project_id()

    @property
    def agent_id(self) -> str | None:
        return get_current_agent_id()

    @property
    def agent_run_id(self) -> str | None:
        return get_current_agent_run_id()

    @property
    def task_id(self) -> int | None:
        return get_current_task_id()

    def _execute_db(self, fn, db_path: str | None = None):
        """Execute a function with database retry logic."""
        return execute_with_retry(fn, db_path=db_path)

    def _log_tool_usage(self, message: str, progress: int | None = None):
        """Record tool usage in status_updates for audit."""
        project_id = self.project_id
        agent_id = self.agent_id or "unknown"
        agent_run_id = self.agent_run_id

        def _insert(conn: sqlite3.Connection):
            conn.execute(
                """INSERT INTO status_updates (project_id, agent_id, agent_run_id, message, progress)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_id, agent_id, agent_run_id, f"[{self.name}] {message}", progress),
            )
            conn.commit()

        try:
            execute_with_retry(_insert)
        except Exception:
            logger.debug("Failed to log tool usage for %s", self.name, exc_info=True)

    def _validate_project_context(self) -> int:
        """Validate that project_id is available, raise if not."""
        pid = self.project_id
        if pid is None:
            raise ValueError(
                "No project_id in context. Set PABADA_PROJECT_ID or call set_context()."
            )
        return pid

    def _validate_agent_context(self) -> str:
        """Validate that agent_id is available, raise if not."""
        aid = self.agent_id
        if aid is None:
            raise ValueError(
                "No agent_id in context. Set PABADA_AGENT_ID or call set_context()."
            )
        return aid

    @staticmethod
    def _validate_sandbox_path(path: str) -> str | None:
        """Validate that *path* is inside the sandbox.

        Resolves symlinks via ``os.path.realpath`` and checks proper
        directory boundaries (not just prefix matching).

        Returns ``None`` if valid, or an error message string if denied.
        """
        if not settings.SANDBOX_ENABLED:
            return None

        real = os.path.realpath(path)
        for allowed in settings.ALLOWED_BASE_DIRS:
            allowed_real = os.path.realpath(allowed)
            # Exact match or proper subdirectory (boundary on os.sep)
            if real == allowed_real or real.startswith(allowed_real + os.sep):
                return None

        return (
            f"Access denied: path '{path}' is outside allowed directories "
            f"({settings.ALLOWED_BASE_DIRS})"
        )

    def _error(self, message: str) -> str:
        """Return a JSON error string for consistent error formatting."""
        return json.dumps({"error": message})

    def _success(self, data: Any) -> str:
        """Return a JSON success string."""
        if isinstance(data, str):
            return data
        return json.dumps(data, default=str)
