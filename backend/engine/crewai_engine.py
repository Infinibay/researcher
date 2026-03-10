"""CrewAI-based agent execution engine."""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.engine.base import AgentEngine

logger = logging.getLogger(__name__)

# Transient LLM errors that should be retried
_TRANSIENT_LLM_ERRORS = (
    "Invalid response from LLM call",
    "Connection error",
    "Rate limit",
    "timeout",
    "503",
    "502",
    "429",
)

DEFAULT_LLM_RETRIES = 3
DEFAULT_LLM_RETRY_DELAY = 5.0  # seconds


def _is_transient_llm_error(exc: Exception) -> bool:
    """Check if an exception looks like a transient LLM provider error."""
    msg = str(exc)
    return any(pattern.lower() in msg.lower() for pattern in _TRANSIENT_LLM_ERRORS)


class CrewAIEngine(AgentEngine):
    """Executes agent tasks using CrewAI Crew + Task."""

    def execute(
        self,
        agent: Any,
        task_prompt: tuple[str, str],
        *,
        verbose: bool = True,
        guardrail: Any | None = None,
        guardrail_max_retries: int = 5,
        output_pydantic: type | None = None,
        task_tools: list | None = None,
        event_id: int | None = None,
        resume_state: dict | None = None,
    ) -> str:
        from crewai import Crew, Task

        from backend.knowledge.service import KnowledgeService

        memory_kwargs = KnowledgeService.build_crew_memory_kwargs()

        desc, expected = task_prompt
        task_kwargs: dict[str, Any] = {
            "description": desc,
            "agent": agent.crewai_agent,
            "expected_output": expected,
        }
        if output_pydantic is not None:
            task_kwargs["output_pydantic"] = output_pydantic
        if guardrail is not None:
            task_kwargs["guardrail"] = guardrail
            task_kwargs["guardrail_max_retries"] = guardrail_max_retries
        if task_tools is not None:
            from backend.tools.base.context import bind_tools_to_agent

            bind_tools_to_agent(task_tools, agent.agent_id)
            task_kwargs["tools"] = task_tools

        crew = Crew(
            agents=[agent.crewai_agent],
            tasks=[Task(**task_kwargs)],
            verbose=verbose,
            max_rpm=30,
            **memory_kwargs,
        )

        return str(self._kickoff_with_retry(crew))

    def _kickoff_with_retry(
        self,
        crew: Any,
        *,
        max_retries: int = DEFAULT_LLM_RETRIES,
        base_delay: float = DEFAULT_LLM_RETRY_DELAY,
    ) -> Any:
        """Run crew.kickoff() with exponential-backoff retries for transient errors."""
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                return crew.kickoff()
            except Exception as exc:
                last_exc = exc
                if not _is_transient_llm_error(exc) or attempt == max_retries:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                    attempt, max_retries, delay, str(exc)[:200],
                )
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]
