"""Project Lead agent — bridge between user and technical team."""

from __future__ import annotations

from typing import Any

from backend.agents.base import InfinibayAgent
from backend.config.settings import settings
from backend.prompts.project_lead.system import build_system_prompt


def create_project_lead_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Project Lead",
    teammates: list[dict[str, str]] | None = None,
    llm: Any | None = None,
) -> InfinibayAgent:
    """Instantiate a Project Lead agent."""
    return InfinibayAgent(
        agent_id=agent_id,
        role="project_lead",
        name=agent_name,
        goal=(
            "Produce a complete, unambiguous, and prioritized PRD that the "
            "Team Lead can use directly to plan and execute the project, "
            "ensuring all requirements are validated by the user"
        ),
        backstory=build_system_prompt(
            agent_name=agent_name,
            agent_id=agent_id,
            teammates=teammates,
            engine=settings.AGENT_ENGINE,
        ),
        project_id=project_id,
        allow_delegation=False,
        max_iter=20,
        llm=llm,
    )
