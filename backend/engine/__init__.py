"""Agent execution engine — loop engine only."""

from __future__ import annotations

from backend.engine.base import AgentEngine, AgentKilledError

_engine_instance: AgentEngine | None = None


def get_engine() -> AgentEngine:
    """Return the loop engine singleton."""
    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance

    from backend.engine.loop_engine import LoopEngine
    _engine_instance = LoopEngine()

    return _engine_instance


def reset_engine() -> None:
    """Reset the cached engine (for testing)."""
    global _engine_instance
    _engine_instance = None


__all__ = ["AgentEngine", "AgentKilledError", "get_engine", "reset_engine"]
