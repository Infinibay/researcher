"""Researcher agent — scientific investigation specialist."""

from __future__ import annotations

from typing import Any

from backend.agents.base import InfinibayAgent
from backend.config.settings import settings
from backend.prompts.researcher.system import build_system_prompt


def create_researcher_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Researcher",
    teammates: list[dict[str, str]] | None = None,
    llm: Any | None = None,
    knowledge_service: Any | None = None,
) -> InfinibayAgent:
    """Instantiate a Researcher agent."""
    knowledge_sources = None
    if knowledge_service is not None:
        knowledge_sources = knowledge_service.get_sources_for_role(
            "researcher", project_id,
        )

    backstory = build_system_prompt(
        agent_name=agent_name, agent_id=agent_id, teammates=teammates,
        engine=settings.AGENT_ENGINE,
    )

    return InfinibayAgent(
        agent_id=agent_id,
        role="researcher",
        name=agent_name,
        goal=(
            "Conduct rigorous research, formulate hypotheses, validate them, "
            "and document findings"
        ),
        backstory=backstory,
        project_id=project_id,
        allow_delegation=False,
        max_iter=40,
        llm=llm,
        knowledge_sources=knowledge_sources,
    )
