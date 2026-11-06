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
        assert route == "start_planning"

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

    def test_check_and_launch_tasks_hands_off(self, db_conn, executing_project):
        """Actual historical tasks are referenced without legacy dispatch or completion."""
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.project_id = executing_project
        assert flow.check_and_launch_tasks() == "native_owner_required"

    def test_empty_tasks_do_not_accept_a_project(self, db_conn, sample_project):
        """An empty list is not native owner acceptance of project completion."""
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.project_id = sample_project
        assert flow.check_and_launch_tasks() == "native_owner_required"

    def test_route_initialization_new(self, db_conn):
        """route_initialization routes NEW status to start_planning."""
        from backend.flows.main_project_flow import MainProjectFlow

        flow = MainProjectFlow()
        flow.state.status = ProjectStatus.NEW

        result = flow.route_initialization()
        assert result == "start_planning"

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
        assert result == "start_planning"
        assert flow.state.plan == ""
