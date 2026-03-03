"""Code Reviewer agent — quality assurance for code changes."""

from __future__ import annotations

from typing import Any

from backend.agents.base import PabadaAgent
from backend.config.settings import settings
from backend.prompts.code_reviewer.system import build_system_prompt


def create_code_reviewer_agent(
    agent_id: str,
    project_id: int,
    *,
    agent_name: str = "Code Reviewer",
    teammates: list[dict[str, str]] | None = None,
    llm: Any | None = None,
) -> PabadaAgent:
    """Instantiate a Code Reviewer agent."""
    backstory = build_system_prompt(
        agent_name=agent_name, teammates=teammates,
        engine=settings.AGENT_ENGINE,
    )

    return PabadaAgent(
        agent_id=agent_id,
        role="code_reviewer",
        name=agent_name,
        goal=(
            "Ensure code quality, performance, and adherence to "
            "specifications"
        ),
        backstory=backstory,
        project_id=project_id,
        allow_delegation=False,
        max_iter=15,
        llm=llm,
    )
