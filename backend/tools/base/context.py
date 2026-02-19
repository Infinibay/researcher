"""Agent context management using Python contextvars."""

import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

_project_id_var: ContextVar[Optional[int]] = ContextVar("project_id", default=None)
_agent_id_var: ContextVar[Optional[str]] = ContextVar("agent_id", default=None)
_agent_run_id_var: ContextVar[Optional[str]] = ContextVar("agent_run_id", default=None)
_task_id_var: ContextVar[Optional[int]] = ContextVar("task_id", default=None)


@dataclass
class ToolContext:
    """Immutable snapshot of current agent context."""
    project_id: Optional[int] = None
    agent_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    task_id: Optional[int] = None


def set_context(
    project_id: int | None = None,
    agent_id: str | None = None,
    agent_run_id: str | None = None,
    task_id: int | None = None,
) -> ToolContext:
    """Set context variables for the current execution scope."""
    if project_id is not None:
        _project_id_var.set(project_id)
    if agent_id is not None:
        _agent_id_var.set(agent_id)
    if agent_run_id is not None:
        _agent_run_id_var.set(agent_run_id)
    if task_id is not None:
        _task_id_var.set(task_id)
    return get_context()


def get_context() -> ToolContext:
    """Get current context, falling back to environment variables."""
    return ToolContext(
        project_id=_project_id_var.get() or _env_int("PABADA_PROJECT_ID"),
        agent_id=_agent_id_var.get() or os.environ.get("PABADA_AGENT_ID"),
        agent_run_id=_agent_run_id_var.get() or os.environ.get("PABADA_AGENT_RUN_ID"),
        task_id=_task_id_var.get() or _env_int("PABADA_TASK_ID"),
    )


def get_current_project_id() -> int | None:
    """Get the current project ID from context or environment."""
    return _project_id_var.get() or _env_int("PABADA_PROJECT_ID")


def get_current_agent_id() -> str | None:
    """Get the current agent ID from context or environment."""
    return _agent_id_var.get() or os.environ.get("PABADA_AGENT_ID")


def get_current_agent_run_id() -> str | None:
    """Get the current agent run ID from context or environment."""
    return _agent_run_id_var.get() or os.environ.get("PABADA_AGENT_RUN_ID")


def get_current_task_id() -> int | None:
    """Get the current task ID from context or environment."""
    return _task_id_var.get() or _env_int("PABADA_TASK_ID")


def _env_int(name: str) -> int | None:
    """Read an integer from environment, returning None if missing or invalid."""
    val = os.environ.get(name)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None
