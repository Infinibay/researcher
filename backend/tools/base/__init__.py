"""Lightweight database/context exports; the old CrewAI tool base is loaded only by explicit legacy tool consumers."""

from .context import (
    ToolContext,
    get_current_agent_id,
    get_current_project_id,
    set_context,
)
from .db import DBConnection, execute_with_retry, get_connection, get_db_path

__all__ = [
    "get_connection",
    "execute_with_retry",
    "get_db_path",
    "DBConnection",
    "ToolContext",
    "get_current_project_id",
    "get_current_agent_id",
    "set_context",
    "InfinibayBaseTool",
]


def __getattr__(name: str):
    """Avoid importing the old tool framework while a native caller only needs database or context access."""
    if name != "InfinibayBaseTool":
        raise AttributeError(name)
    from .base_tool import InfinibayBaseTool

    return InfinibayBaseTool
