"""Tests for MainProjectFlow."""

from __future__ import annotations

from backend.flows.helpers import load_project_state, update_project_status
from backend.flows.state_models import ProjectState, ProjectStatus


class TestMainProjectFlowHelpers:
    """Test the helper functions used by MainProjectFlow."""

    def test_load_project_state_existing(self, db_conn, sample_project):
        state = load_project_state(sample_project)
        assert state is not None
        assert state["name"] == "Test Project"
        assert state["status"] == "new"
        assert state["total_tasks"] == 0

    def test_load_project_state_nonexistent(self, db_conn):
        state = load_project_state(99999)
        assert state is None

    def test_load_project_with_task_counts(self, db_conn, executing_project):
        state = load_project_state(executing_project)
        assert state is not None
        assert state["status"] == "executing"
        assert state["total_tasks"] == 4
        assert state["task_counts"]["pending"] == 2
        assert state["task_counts"]["backlog"] == 1
        assert state["task_counts"]["in_progress"] == 1

    def test_update_project_status(self, db_conn, sample_project):
        update_project_status(sample_project, "planning")
        row = db_conn.execute(
            "SELECT status FROM projects WHERE id = ?", (sample_project,)
        ).fetchone()
        assert row["status"] == "planning"


class TestProjectState:
    """Test ProjectState model."""

    def test_default_state(self):
        state = ProjectState()
        assert state.project_id == 0
        assert state.status == ProjectStatus.NEW
        assert state.requirements == ""
        assert state.user_approved is False
        assert state.current_task_id is None

    def test_state_with_values(self):
        state = ProjectState(
            project_id=1,
            project_name="My Project",
            status=ProjectStatus.EXECUTING,
            requirements="Build a web app",
        )
        assert state.project_id == 1
        assert state.project_name == "My Project"
        assert state.status == ProjectStatus.EXECUTING


class TestMainProjectCompatibility:
    """Old project entry preserves history and exposes owner policy instead of planning or completion."""

    def test_existing_project_returns_owner_entry(self, db_conn, executing_project):
        """A legacy executing label does not start the new planner or alter tasks."""
        from backend.flows.main_project_flow import MainProjectFlow

        before = [tuple(row) for row in db_conn.execute("SELECT * FROM tasks ORDER BY id")]
        hint = MainProjectFlow().kickoff({"project_id": executing_project})
        assert hint["native_admission_run_id"] is None
        assert hint["event_authorizes_work"] is False
        assert [tuple(row) for row in db_conn.execute("SELECT * FROM tasks ORDER BY id")] == before
