"""Tests for MainProjectFlow."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from backend.flows.helpers import load_project_state, update_project_status
from backend.flows.state_models import ProjectState, ProjectStatus
from backend.tests.flows.conftest import make_mock_agent, make_mock_crew


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
        assert state["total_tasks"] == 3
        assert state["task_counts"]["pending"] == 1
        assert state["task_counts"]["backlog"] == 2

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


class TestMainProjectFlowInitialize:
    """Test initialization paths of MainProjectFlow."""

    @patch("backend.flows.main_project_flow.log_flow_event")
    def test_initialize_new_project(self, mock_log, db_conn):
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.project_id = 0
        flow.state.project_name = "New Project"

        result = flow.initialize_project()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.project_id > 0
        assert flow.state.status == ProjectStatus.NEW

        # Routing is now handled by the router method
        route = flow.route_initialization()
        assert route == "new_project"

    @patch("backend.flows.main_project_flow.log_flow_event")
    def test_initialize_resume_executing(self, mock_log, db_conn, executing_project):
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.project_id = executing_project

        result = flow.initialize_project()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.status == ProjectStatus.EXECUTING

        # Routing is now handled by the router method
        route = flow.route_initialization()
        assert route == "resume_execution"

    @patch("backend.flows.main_project_flow.log_flow_event")
    def test_initialize_completed_project(self, mock_log, db_conn, sample_project):
        update_project_status(sample_project, "completed")

        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.project_id = sample_project

        result = flow.initialize_project()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.status == ProjectStatus.COMPLETED

        # Routing is now handled by the router method
        route = flow.route_initialization()
        assert route == "already_complete"


class TestMainProjectFlowTaskRouting:
    """Test the check_and_launch_tasks router and _launch_pending_tasks logic."""

    @patch("backend.flows.main_project_flow.MainProjectFlow._launch_pending_tasks")
    def test_check_and_launch_tasks_delegates(self, mock_launch, db_conn, executing_project):
        """check_and_launch_tasks router delegates to _launch_pending_tasks."""
        from backend.flows.main_project_flow import MainProjectFlow

        mock_launch.return_value = "task_completed"

        flow = MainProjectFlow()
        flow.state.project_id = executing_project

        result = flow.check_and_launch_tasks()
        assert result == "task_completed"
        mock_launch.assert_called_once()

    @patch("backend.flows.main_project_flow.MainProjectFlow._launch_pending_tasks")
    def test_check_and_launch_no_tasks(self, mock_launch, db_conn, sample_project):
        """check_and_launch_tasks returns no_pending_tasks when nothing to do."""
        from backend.flows.main_project_flow import MainProjectFlow

        mock_launch.return_value = "no_pending_tasks"

        flow = MainProjectFlow()
        flow.state.project_id = sample_project

        result = flow.check_and_launch_tasks()
        assert result == "no_pending_tasks"

    def test_route_initialization_new(self, db_conn):
        """route_initialization routes NEW status to new_project."""
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.status = ProjectStatus.NEW

        result = flow.route_initialization()
        assert result == "new_project"

    @patch("backend.flows.main_project_flow.log_flow_event")
    def test_route_initialization_executing(self, mock_log, db_conn):
        """route_initialization routes EXECUTING status to resume_execution."""
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.status = ProjectStatus.EXECUTING

        result = flow.route_initialization()
        assert result == "resume_execution"


class TestMainProjectFlowPlanRejection:
    """Test the plan rejection loop."""

    def test_handle_rejection_clears_plan(self):
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.project_id = 1
        flow.state.plan = "Some plan that was rejected"
        flow.state.feedback = "Need more detail"

        result = flow.handle_rejection()
        # @listen() methods no longer return routing strings
        assert result is None
        assert flow.state.plan == ""
