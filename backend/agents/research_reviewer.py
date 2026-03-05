"""Research Reviewer agent — scientific peer review specialist."""

from __future__ import annotations

from typing import Any

from backend.agents.base import PabadaAgent
from backend.config.settings import settings
from backend.prompts.research_reviewer.system import build_system_prompt


def create_research_reviewer_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Research Reviewer",
    teammates: list[dict[str, str]] | None = None,
    llm: Any | None = None,
    knowledge_service: Any | None = None,
) -> PabadaAgent:
    """Instantiate a Research Reviewer agent."""
    knowledge_sources = None
    if knowledge_service is not None:
        knowledge_sources = knowledge_service.get_sources_for_role(
            "research_reviewer", project_id,
        )

    backstory = build_system_prompt(
        agent_name=agent_name, agent_id=agent_id, teammates=teammates,
        engine=settings.AGENT_ENGINE,
    )

    return PabadaAgent(
        agent_id=agent_id,
        role="research_reviewer",
        name=agent_name,
        goal=(
            "Validate scientific rigor, methodology, and conclusions "
            "of research outputs"
        ),
        backstory=backstory,
        project_id=project_id,
        allow_delegation=False,
        max_iter=15,
        llm=llm,
        knowledge_sources=knowledge_sources,
    )
