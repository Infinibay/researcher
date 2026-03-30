"""Tests for backend.orchestrator.ProjectOrchestrator.

The orchestrator module has a heavy import chain (agents -> tools -> flows)
that triggers a circular import. We work around this by pre-mocking the
problematic modules in sys.modules before importing the orchestrator.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _ensure_mock_module(name):
    """Insert a mock module into sys.modules if not already present."""
    if name not in sys.modules:
        mod = ModuleType(name)
        sys.modules[name] = mod
        return mod, True
    return sys.modules[name], False


@pytest.fixture(autouse=True)
def _mock_heavy_imports():
    """Mock the heavy agent/tool/flow imports to avoid circular import errors.

    We create proper ModuleType mocks (not MagicMock) for packages so that
    sub-module imports like 'backend.engine.loop_models' still work.
    """
    originals = {}
    to_mock = {
        # Mock the agents package and its key members
        "backend.agents": True,
        "backend.agents.base": True,
        "backend.agents.registry": True,
        "backend.agents.project_lead": True,
        "backend.tools.base.context": True,
    }

    for mod_name in to_mock:
        if mod_name in sys.modules:
            originals[mod_name] = sys.modules[mod_name]
        mock_mod = ModuleType(mod_name)
        # Add common attributes
        mock_mod.InfinibayAgent = MagicMock()
        mock_mod.bind_tools_to_agent = MagicMock()
        mock_mod.set_context = MagicMock()
        mock_mod.get_tools_for_role = MagicMock(return_value=[])
        sys.modules[mod_name] = mock_mod

    # Clear cached orchestrator so it reimports cleanly
    sys.modules.pop("backend.orchestrator", None)

    yield

    # Restore
    for mod_name in to_mock:
        if mod_name in originals:
            sys.modules[mod_name] = originals[mod_name]
        else:
            sys.modules.pop(mod_name, None)
    sys.modules.pop("backend.orchestrator", None)


def _import_orchestrator():
    """Import orchestrator after mocks are in place."""
    sys.modules.pop("backend.orchestrator", None)
    from backend.orchestrator import AgentTask, ProjectOrchestrator, TaskStatus
    return ProjectOrchestrator, AgentTask, TaskStatus


class TestInit:
    def test_default_values(self):
        ProjectOrchestrator, _, _ = _import_orchestrator()
        orch = ProjectOrchestrator(project_id=99, workspace_path="/tmp/test-workspace")
        assert orch.project_id == 99
        assert orch.workspace_path == "/tmp/test-workspace"
        assert orch.agents == {}
        assert orch.tasks == []
        assert orch._task_counter == 0
        assert orch._initialized is False

    def test_default_workspace(self):
        ProjectOrchestrator, _, _ = _import_orchestrator()
        import os
        orch = ProjectOrchestrator()
        assert orch.project_id == 1
        assert orch.workspace_path == os.getcwd()


class TestAddTask:
    def test_creates_task_with_incrementing_id(self):
        ProjectOrchestrator, _, _ = _import_orchestrator()
        orch = ProjectOrchestrator()

        t1 = orch.add_task("First task")
        t2 = orch.add_task("Second task")
        t3 = orch.add_task("Third task")

        assert t1.id == 1
        assert t2.id == 2
        assert t3.id == 3

    def test_task_defaults(self):
        ProjectOrchestrator, _, TaskStatus = _import_orchestrator()
        orch = ProjectOrchestrator()
        task = orch.add_task("Do something", expected_output="result")
        assert task.description == "Do something"
        assert task.expected_output == "result"
        assert task.status == TaskStatus.PENDING
        assert task.assigned_to is None

    def test_tasks_appended(self):
        ProjectOrchestrator, _, _ = _import_orchestrator()
        orch = ProjectOrchestrator()
        orch.add_task("t1")
        orch.add_task("t2")
        assert len(orch.tasks) == 2


class TestGetStatus:
    def test_returns_agent_and_task_info(self):
        ProjectOrchestrator, _, _ = _import_orchestrator()
        orch = ProjectOrchestrator()

        mock_agent = MagicMock()
        mock_agent.role = "developer"
        mock_agent.name = "Dev"
        orch.agents["dev-1"] = mock_agent

        orch.add_task("Test task")

        status = orch.get_status()
        assert "agents" in status
        assert "tasks" in status
        assert "dev-1" in status["agents"]
        assert status["agents"]["dev-1"]["role"] == "developer"
        assert len(status["tasks"]) == 1
        assert status["tasks"][0]["description"] == "Test task"
        assert "multi_dev" in status
        assert "workspace" in status


class TestAgentTask:
    def test_task_status_enum(self):
        _, AgentTask, TaskStatus = _import_orchestrator()
        task = AgentTask(id=1, description="test")
        assert task.status == TaskStatus.PENDING

        task.status = TaskStatus.IN_PROGRESS
        assert task.status.value == "in_progress"

        task.status = TaskStatus.DONE
        assert task.status.value == "done"


class TestGetTeamComposition:
    def test_returns_correct_roles(self):
        # Mock prompts modules that _get_team_composition imports locally
        prompt_mods = [
            "backend.prompts.developer.system",
            "backend.prompts.code_reviewer.system",
            "backend.prompts.researcher.system",
            "backend.prompts.research_reviewer.system",
            "backend.prompts.project_lead.system",
        ]
        saved = {}
        for mod in prompt_mods:
            saved[mod] = sys.modules.get(mod)
            m = ModuleType(mod)
            m.get_system_prompt = lambda: "system prompt"
            sys.modules[mod] = m

        try:
            ProjectOrchestrator, _, _ = _import_orchestrator()
            orch = ProjectOrchestrator()

            with patch("backend.orchestrator._get_role_backstory", return_value="backstory"):
                team = orch._get_team_composition()

            assert "project_lead" in team
            assert team["project_lead"]["role"] == "project_lead"

            dev_roles = [k for k, v in team.items() if v["role"] == "developer"]
            assert len(dev_roles) >= 1

            assert "code_reviewer" in team
            assert "researcher" in team
            assert "research_reviewer" in team
        finally:
            for mod, orig in saved.items():
                if orig is None:
                    sys.modules.pop(mod, None)
                else:
                    sys.modules[mod] = orig
