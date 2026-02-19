"""Developer agent — code implementation specialist."""

from __future__ import annotations

from typing import Any

from backend.agents.base import PabadaAgent
from backend.prompts.developer.system import build_system_prompt


def create_developer_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Developer",
    teammates: list[dict[str, str]] | None = None,
    tech_hints: list[str] | None = None,
    llm: Any | None = None,
) -> PabadaAgent:
    """Instantiate a Developer agent."""
    backstory = build_system_prompt(
        agent_name=agent_name, teammates=teammates, tech_hints=tech_hints,
    )

    return PabadaAgent(
        agent_id=agent_id,
        role="developer",
        name=agent_name,
        goal=(
            "Implement high-quality code following the task specifications"
        ),
        backstory=backstory,
        project_id=project_id,
        allow_delegation=False,
        max_iter=20,
        llm=llm,
    )
