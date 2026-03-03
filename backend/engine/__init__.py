"""Agent execution engine abstraction.

Provides a pluggable engine interface so PABADA can run agents via CrewAI
or Claude Code CLI, selected by ``PABADA_AGENT_ENGINE``.
"""

from __future__ import annotations

from backend.engine.base import AgentEngine, AgentKilledError

_engine_instance: AgentEngine | None = None


def get_engine() -> AgentEngine:
    """Return the configured agent engine singleton.

    Reads ``settings.AGENT_ENGINE`` on first call and caches the result.
    """
    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance

    from backend.config.settings import settings

    engine_name = settings.AGENT_ENGINE

    if engine_name == "crewai":
        from backend.engine.crewai_engine import CrewAIEngine
        _engine_instance = CrewAIEngine()
    elif engine_name == "claude_code":
        from backend.engine.claude_code_engine import ClaudeCodeEngine
        _engine_instance = ClaudeCodeEngine()
    else:
        raise ValueError(
            f"Unknown AGENT_ENGINE '{engine_name}'. Valid: crewai, claude_code"
        )

    return _engine_instance


def reset_engine() -> None:
    """Reset the cached engine (for testing)."""
    global _engine_instance
    _engine_instance = None


__all__ = ["AgentEngine", "AgentKilledError", "get_engine", "reset_engine"]
