"""Tests for agent creation, roster registration, and run tracking."""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from backend.tools.base.context import set_context, get_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fake_llm_config(monkeypatch):
    """Provide dummy LLM config so CrewAI Agent() doesn't fail on init."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")
    monkeypatch.setenv("INFINIBAY_LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("INFINIBAY_LLM_API_KEY", "sk-test-fake-key-for-unit-tests")

    from backend.config.llm import _reset_llm_cache
    _reset_llm_cache()
    yield
    _reset_llm_cache()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def test_db(tmp_dir):
    db_path = os.path.join(tmp_dir, "test.db")
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "db", "schema.sql"
    )
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)

    # Seed minimal data
    conn.execute(
        """INSERT INTO projects (id, name, description, status)
           VALUES (1, 'Test Project', 'A test project', 'executing')"""
    )
    conn.execute(
        """INSERT INTO epics (id, project_id, title, description, status)
           VALUES (1, 1, 'Test Epic', 'Epic description', 'open')"""
    )
    conn.execute(
        """INSERT INTO milestones (id, project_id, epic_id, title, description, status)
           VALUES (1, 1, 1, 'Test Milestone', 'Milestone description', 'open')"""
    )
    # Insert a task so agent_runs FK is satisfied
    conn.execute(
        """INSERT INTO tasks (id, project_id, epic_id, milestone_id, type, status, title, created_by)
           VALUES (1, 1, 1, 1, 'code', 'backlog', 'Test Task', 'test')"""
    )
    conn.commit()
    conn.close()

    os.environ["INFINIBAY_DB"] = db_path
    yield db_path

    if "INFINIBAY_DB" in os.environ:
        del os.environ["INFINIBAY_DB"]


@pytest.fixture
def agent_context(test_db):
    set_context(project_id=1, agent_id="test-agent", agent_run_id="run-0", task_id=1)
    yield
    set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


# ---------------------------------------------------------------------------
# Agent creation tests
# ---------------------------------------------------------------------------


class TestAgentCreation:
    """Each factory should produce a InfinibayAgent with correct attributes."""

    @pytest.mark.parametrize(
        "role, factory_module, factory_name, expected_delegation",
        [
            ("project_lead", "backend.agents.project_lead", "create_project_lead_agent", False),
            ("team_lead", "backend.agents.team_lead", "create_team_lead_agent", True),
            ("developer", "backend.agents.developer", "create_developer_agent", False),
            ("code_reviewer", "backend.agents.code_reviewer", "create_code_reviewer_agent", False),
            ("researcher", "backend.agents.researcher", "create_researcher_agent", False),
            ("research_reviewer", "backend.agents.research_reviewer", "create_research_reviewer_agent", False),
        ],
    )
    def test_create_agent(
        self, test_db, role, factory_module, factory_name, expected_delegation
    ):
        import importlib

        mod = importlib.import_module(factory_module)
        factory = getattr(mod, factory_name)

        agent = factory(f"{role}_test", project_id=1)

        assert agent.role == role
        assert agent.project_id == 1
        assert agent.agent_id == f"{role}_test"
        assert agent.crewai_agent is not None
        assert agent.crewai_agent.allow_delegation == expected_delegation

    def test_agent_has_tools(self, test_db):
        from backend.agents.developer import create_developer_agent

        agent = create_developer_agent("dev-1", project_id=1)
        tools = agent.crewai_agent.tools
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        # Developer should have file and git tools
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "git_branch" in tool_names


# ---------------------------------------------------------------------------
# Roster tests
# ---------------------------------------------------------------------------


class TestRoster:
    def test_register_in_roster(self, test_db):
        from backend.agents.developer import create_developer_agent

        agent = create_developer_agent("dev-roster-1", project_id=1)
        agent.register_in_roster()

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM roster WHERE agent_id = ?", ("dev-roster-1",)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["role"] == "developer"
        assert row["status"] == "idle"
        assert row["name"] == "Developer"

    def test_register_idempotent(self, test_db):
        from backend.agents.developer import create_developer_agent

        agent = create_developer_agent("dev-idem", project_id=1)
        agent.register_in_roster()
        agent.register_in_roster()  # should not raise

        conn = sqlite3.connect(test_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM roster WHERE agent_id = ?", ("dev-idem",)
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_update_and_load_memory(self, test_db):
        from backend.agents.project_lead import create_project_lead_agent

        agent = create_project_lead_agent("pl-mem", project_id=1)
        agent.register_in_roster()
        agent.update_memory("User prefers short reports")

        loaded = agent.load_memory()
        assert loaded == "User prefers short reports"


# ---------------------------------------------------------------------------
# Registry module tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_agent_standalone(self, test_db):
        from backend.agents.registry import register_agent

        register_agent("reg-1", "My Developer", "developer")

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM roster WHERE agent_id = ?", ("reg-1",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["name"] == "My Developer"

    def test_register_invalid_role(self, test_db):
        from backend.agents.registry import register_agent

        with pytest.raises(ValueError, match="Unknown role"):
            register_agent("bad-1", "Bad", "nonexistent_role")

    def test_get_agent_by_role(self, test_db):
        from backend.agents.registry import get_agent_by_role

        agent = get_agent_by_role("developer", project_id=1)
        assert agent.role == "developer"
        assert agent.agent_id == "developer_p1"

        # Should be registered in roster
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM roster WHERE agent_id = ?", ("developer_p1",)
        ).fetchone()
        conn.close()
        assert row is not None

    def test_get_all_agents(self, test_db):
        from backend.agents.registry import get_all_agents, VALID_ROLES

        agents = get_all_agents(project_id=1)
        assert set(agents.keys()) == VALID_ROLES
        for role, agent in agents.items():
            assert agent.role == role

    def test_update_agent_status(self, test_db):
        from backend.agents.registry import register_agent, update_agent_status

        register_agent("status-1", "Agent", "researcher")
        update_agent_status("status-1", "active")

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM roster WHERE agent_id = ?", ("status-1",)
        ).fetchone()
        conn.close()
        assert row["status"] == "active"

    def test_update_agent_status_invalid(self, test_db):
        from backend.agents.registry import update_agent_status

        with pytest.raises(ValueError, match="Invalid status"):
            update_agent_status("x", "bogus")


# ---------------------------------------------------------------------------
# Agent run tracking
# ---------------------------------------------------------------------------


class TestAgentRuns:
    def test_create_and_complete_agent_run(self, test_db):
        from backend.agents.developer import create_developer_agent

        agent = create_developer_agent("dev-run-1", project_id=1)
        agent.register_in_roster()

        run_id = agent.create_agent_run(task_id=1)
        assert run_id  # non-empty UUID string

        # Verify running
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE agent_run_id = ?", (run_id,)
        ).fetchone()
        assert row["status"] == "running"

        # Roster should be active
        roster_row = conn.execute(
            "SELECT status, total_runs FROM roster WHERE agent_id = ?",
            ("dev-run-1",),
        ).fetchone()
        assert roster_row["status"] == "active"
        assert roster_row["total_runs"] == 1

        conn.close()

        # Complete the run
        agent.complete_agent_run(run_id, status="completed", tokens_used=500)

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE agent_run_id = ?", (run_id,)
        ).fetchone()
        assert row["status"] == "completed"
        assert row["tokens_used"] == 500

        # Performance updated
        perf = conn.execute(
            "SELECT * FROM agent_performance WHERE agent_id = ?",
            ("dev-run-1",),
        ).fetchone()
        assert perf["successful_runs"] == 1
        assert perf["total_tokens"] == 500

        # Roster back to idle
        roster_row = conn.execute(
            "SELECT status FROM roster WHERE agent_id = ?", ("dev-run-1",)
        ).fetchone()
        assert roster_row["status"] == "idle"
        conn.close()

    def test_create_agent_run_via_registry(self, test_db):
        from backend.agents.registry import (
            register_agent,
            create_agent_run_record,
            complete_agent_run,
        )

        register_agent("reg-run-1", "Researcher", "researcher")
        run_id = create_agent_run_record("reg-run-1", project_id=1, task_id=1, role="researcher")
        assert run_id

        # agent_id should be stored in agent_runs
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT agent_id FROM agent_runs WHERE agent_run_id = ?", (run_id,)
        ).fetchone()
        assert row["agent_id"] == "reg-run-1"

        # Roster should be active
        roster_row = conn.execute(
            "SELECT status FROM roster WHERE agent_id = ?", ("reg-run-1",)
        ).fetchone()
        assert roster_row["status"] == "active"
        conn.close()

        complete_agent_run(run_id, status="completed", tokens_used=200)

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE agent_run_id = ?", (run_id,)
        ).fetchone()
        assert row["status"] == "completed"

        # Roster should be back to idle
        roster_row = conn.execute(
            "SELECT status FROM roster WHERE agent_id = ?", ("reg-run-1",)
        ).fetchone()
        assert roster_row["status"] == "idle"

        # Performance should be attributed to the correct agent_id
        perf = conn.execute(
            "SELECT * FROM agent_performance WHERE agent_id = ?", ("reg-run-1",)
        ).fetchone()
        assert perf["successful_runs"] == 1
        assert perf["total_tokens"] == 200
        conn.close()

    def test_complete_nonexistent_run(self, test_db):
        from backend.agents.registry import complete_agent_run

        with pytest.raises(ValueError, match="No agent_run found"):
            complete_agent_run("nonexistent-uuid", status="completed")


# ---------------------------------------------------------------------------
# Context integration
# ---------------------------------------------------------------------------


class TestContextIntegration:
    def test_activate_context(self, test_db):
        from backend.agents.developer import create_developer_agent

        agent = create_developer_agent("ctx-dev", project_id=1)
        agent.activate_context(task_id=42)

        ctx = get_context()
        assert ctx.project_id == 1
        assert ctx.agent_id == "ctx-dev"
        assert ctx.task_id == 42


# ---------------------------------------------------------------------------
# Tool assignment validation
# ---------------------------------------------------------------------------


class TestToolAssignment:
    """Verify that each role gets the expected tool categories."""

    def test_project_lead_has_ask_user(self, test_db):
        from backend.agents.project_lead import create_project_lead_agent

        agent = create_project_lead_agent("pl-tools", project_id=1)
        names = {t.name for t in agent.crewai_agent.tools}
        assert "ask_user" in names

    def test_project_lead_no_file_tools(self, test_db):
        from backend.agents.project_lead import create_project_lead_agent

        agent = create_project_lead_agent("pl-nofile", project_id=1)
        names = {t.name for t in agent.crewai_agent.tools}
        assert "write_file" not in names
        assert "git_branch" not in names

    def test_developer_has_shell(self, test_db):
        from backend.agents.developer import create_developer_agent

        agent = create_developer_agent("dev-shell", project_id=1)
        names = {t.name for t in agent.crewai_agent.tools}
        assert "execute_command" in names

    def test_code_reviewer_no_shell(self, test_db):
        from backend.agents.code_reviewer import create_code_reviewer_agent

        agent = create_code_reviewer_agent("cr-noshell", project_id=1)
        names = {t.name for t in agent.crewai_agent.tools}
        assert "execute_command" not in names

    def test_researcher_has_web_tools(self, test_db):
        from backend.agents.researcher import create_researcher_agent

        agent = create_researcher_agent("res-web", project_id=1)
        names = {t.name for t in agent.crewai_agent.tools}
        assert "web_search" in names
        assert "web_fetch" in names

    def test_research_reviewer_has_validate(self, test_db):
        from backend.agents.research_reviewer import create_research_reviewer_agent

        agent = create_research_reviewer_agent("rr-val", project_id=1)
        names = {t.name for t in agent.crewai_agent.tools}
        assert "validate_finding" in names
        assert "reject_finding" in names

    def test_team_lead_delegation_enabled(self, test_db):
        from backend.agents.team_lead import create_team_lead_agent

        agent = create_team_lead_agent("tl-deleg", project_id=1)
        assert agent.crewai_agent.allow_delegation is True
