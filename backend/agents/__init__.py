"""PABADA Agent definitions and registry."""

from backend.agents.project_lead import create_project_lead_agent
from backend.agents.team_lead import create_team_lead_agent
from backend.agents.developer import create_developer_agent
from backend.agents.code_reviewer import create_code_reviewer_agent
from backend.agents.researcher import create_researcher_agent
from backend.agents.research_reviewer import create_research_reviewer_agent
from backend.agents.registry import (
    register_agent,
    get_agent_by_role,
    get_all_agents,
    update_agent_status,
    create_agent_run_record,
    complete_agent_run,
)

__all__ = [
    "create_project_lead_agent",
    "create_team_lead_agent",
    "create_developer_agent",
    "create_code_reviewer_agent",
    "create_researcher_agent",
    "create_research_reviewer_agent",
    "register_agent",
    "get_agent_by_role",
    "get_all_agents",
    "update_agent_status",
    "create_agent_run_record",
    "complete_agent_run",
]
