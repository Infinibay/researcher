"""Native tools and historical reads work without the retired role constructors, CrewAI memory or executable role catalog."""

import importlib.util

import pytest


def test_role_factories_and_framework_memory_are_not_available():
    """A role name cannot construct a second model/tool owner or inject unversioned framework memory."""
    for name in (
        "backend.agents.base", "backend.agents.registry", "backend.agents.developer",
        "backend.agents.researcher", "backend.agents.project_lead",
        "backend.agents.team_lead", "backend.agents.code_reviewer",
        "backend.agents.research_reviewer", "backend.knowledge.service",
        "backend.knowledge.sources", "backend.tools._legacy_catalog",
        "backend.flows.crewai_event_bridge",
    ):
        try:
            found = importlib.util.find_spec(name)
        except ModuleNotFoundError as error:
            assert error.name in (name, name.rpartition('.')[0])
        else:
            assert found is None, f"Retired role integration remains: {name}"
    import backend.knowledge
    import backend.tools

    assert not hasattr(backend.tools, "get_tools_for_role")
    assert not hasattr(backend.knowledge, "KnowledgeService")


def test_historical_roster_reader_preserves_original_memory_and_runs(coordination):
    """Retiring constructors leaves old identities, memory text and recorded execution available without adopting or executing them."""
    from backend.api.routes.agents import list_agents

    c = coordination
    c.conn.execute("INSERT INTO roster(agent_id,name,role,memory,status,total_runs) VALUES('old_1_p101','Historical investigator','researcher','Original memory: an example, not approval.','idle',1)")
    c.conn.execute("INSERT INTO agent_runs(project_id,agent_run_id,agent_id,task_id,role,status) VALUES(101,'original-old-run','old_1_p101',1001,'researcher','running')")
    c.conn.commit()
    before = dict(c.conn.execute("SELECT * FROM roster WHERE agent_id='old_1_p101'").fetchone())
    response = list_agents(project_id=101)
    assert response.total == 1
    assert response.agents[0].agent_id == 'old_1_p101'
    assert response.agents[0].current_run.agent_run_id == 'original-old-run'
    assert dict(c.conn.execute("SELECT * FROM roster WHERE agent_id='old_1_p101'").fetchone()) == before
    assert c.conn.execute("SELECT status FROM agent_runs WHERE agent_run_id='original-old-run'").fetchone()[0] == 'running'
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0


@pytest.mark.parametrize(
    "profile", ["RESEARCH_NAMES", "REVIEW_NAMES", "INVESTIGATION_NAMES", "DEVELOPMENT_NAMES"],
)
def test_native_finding_catalog_can_inspect_actual_review_feedback(profile):
    """Native capabilities offering claim previews also expose actual review feedback; a historical role no longer selects tools."""
    from backend.runtime import business_mediation
    from backend.runtime.business_definitions import definitions

    tools = definitions(object(), names=getattr(business_mediation, profile))
    names = {tool.name for tool in tools}
    assert "researcher_finding_list" in names
    assert "researcher_review_read" in names

