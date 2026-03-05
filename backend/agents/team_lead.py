"""Team Lead agent — technical coordinator and planner."""

from __future__ import annotations

from typing import Any

from backend.agents.base import PabadaAgent
from backend.config.settings import settings
from backend.prompts.team_lead.system import build_system_prompt


def create_team_lead_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Team Lead",
    teammates: list[dict[str, str]] | None = None,
    llm: Any | None = None,
) -> PabadaAgent:
    """Instantiate a Team Lead agent."""
    backstory = build_system_prompt(
        agent_name=agent_name, agent_id=agent_id, teammates=teammates,
        engine=settings.AGENT_ENGINE,
    )

    return PabadaAgent(
        agent_id=agent_id,
        role="team_lead",
        name=agent_name,
        goal=(
            "Create detailed plans, coordinate the team, and ensure everyone "
            "follows best practices"
        ),
        backstory=backstory,
        project_id=project_id,
        allow_delegation=True,
        max_iter=30,
        reasoning=True,
        max_reasoning_attempts=3,
        llm=llm,
    )
