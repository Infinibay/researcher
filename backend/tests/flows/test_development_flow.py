"""Tests for DevelopmentFlow."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from backend.flows.helpers import (
    check_task_dependencies,
    get_task_by_id,
    update_task_status,
)
from backend.flows.state_models import DevelopmentState, ReviewStatus
from backend.tests.flows.conftest import make_mock_agent, make_mock_crew


class TestDevelopmentFlowHelpers:
    """Test helper functions used by DevelopmentFlow."""

    def test_get_task_by_id(self, db_conn, executing_project):
        task = get_task_by_id(1)
        assert task is not None
        assert task["title"] == "Implement feature A"
        assert task["type"] == "code"

    def test_get_task_by_id_nonexistent(self, db_conn):
        task = get_task_by_id(99999)
        assert task is None

    def test_check_dependencies_no_deps(self, db_conn, executing_project):
        result = check_task_dependencies(1)
        assert result is True

    def test_check_dependencies_with_blocking(self, db_conn, executing_project):
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.commit()
        result = check_task_dependencies(3)
        assert result is False

    def test_check_dependencies_resolved(self, db_conn, executing_project):
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.commit()
        update_task_status(1, "done")
        result = check_task_dependencies(3)
        assert result is True


class TestDevelopmentState:
    """Test DevelopmentState model."""

    def test_default_state(self):
        state = DevelopmentState()
        assert state.task_id == 0
        assert state.branch_name == ""
        assert state.review_status == ReviewStatus.PENDING
        assert state.escalated is False

    def test_state_with_values(self):
        state = DevelopmentState(
            project_id=1,
            task_id=42,
            branch_name="task-42-feature",
            developer_id="dev_p1",
        )
        assert state.task_id == 42
        assert state.branch_name == "task-42-feature"


class TestDevelopmentFlowAssignment:
    """Test task assignment logic."""

    @patch("backend.flows.development_flow.TicketProtocol")
    @patch("backend.flows.development_flow.Crew")
    @patch("backend.flows.development_flow.Task")
    @patch("backend.flows.development_flow.get_available_agent_by_role")
    @patch("backend.flows.development_flow.get_agent_by_role")
    @patch("backend.flows.development_flow.log_flow_event")
    def test_assign_task_success(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, MockProtocol, db_conn, executing_project):
        mock_get_agent.return_value = make_mock_agent("team_lead", executing_project)
        mock_avail_agent.return_value = make_mock_agent("developer", executing_project)
        MockCrew.return_value = make_mock_crew()
        MockTask.return_value = MagicMock()
        mock_protocol = MagicMock()
        mock_protocol.initiate_checkin.return_value = "test-thread-id"
        MockProtocol.return_value = mock_protocol

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1

        result = flow.assign_task()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.dependencies_met is True

        # Routing is now handled by the router method
        route = flow.route_assignment()
        assert route == "checkin_initiated"

    @patch("backend.flows.development_flow.get_agent_by_role")
    @patch("backend.flows.development_flow.log_flow_event")
    def test_assign_task_blocked(self, mock_log, mock_agent, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("team_lead", executing_project)

        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (1, 2, 'blocks')"""
        )
        db_conn.commit()

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1

        result = flow.assign_task()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.dependencies_met is False

        # Routing is now handled by the router method
        route = flow.route_assignment()
        assert route == "blocked"

    @patch("backend.flows.development_flow.get_agent_by_role")
    def test_assign_task_not_found(self, mock_agent, db_conn):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = 1
        flow.state.task_id = 99999

        result = flow.assign_task()
        # @start() methods no longer return routing strings
        assert result is None

        # Routing is now handled by the router method
        route = flow.route_assignment()
        assert route == "error"


class TestDevelopmentFlowEscalation:
    """Test escalation handling."""

    @patch("backend.flows.development_flow.Crew")
    @patch("backend.flows.development_flow.Task")
    @patch("backend.flows.development_flow.get_agent_by_role")
    @patch("backend.flows.development_flow.log_flow_event")
    def test_handle_escalation(self, mock_log, mock_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("team_lead", executing_project)
        MockCrew.return_value = make_mock_crew("Re-assigned to senior developer")
        MockTask.return_value = MagicMock()

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.task_title = "Implement feature A"
        flow.state.branch_name = "task-1-feature"
        flow.state.developer_id = "developer_p1"
        flow.state.escalated = True

        result = flow.handle_escalation()
        # @listen() methods no longer return routing strings
        assert result is None
