"""Developer agent — code implementation specialist."""

from __future__ import annotations

from typing import Any

from backend.agents.base import InfinibayAgent
from backend.prompts.developer.system import build_system_prompt


def create_developer_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Developer",
    teammates: list[dict[str, str]] | None = None,
    tech_hints: list[str] | None = None,
    llm: Any | None = None,
) -> InfinibayAgent:
    """Instantiate a Developer agent."""
    backstory = build_system_prompt(
        agent_name=agent_name, agent_id=agent_id, teammates=teammates,
        tech_hints=tech_hints,
    )

    return InfinibayAgent(
        agent_id=agent_id,
        role="developer",
        name=agent_name,
        goal=(
            "Implement high-quality code following the task specifications"
        ),
        backstory=backstory,
        project_id=project_id,
        allow_delegation=False,
        max_iter=30,
        reasoning=True,
        max_reasoning_attempts=3,
        llm=llm,
    )
