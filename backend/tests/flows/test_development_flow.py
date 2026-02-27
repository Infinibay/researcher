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
from backend.flows.helpers.db_helpers import promote_unblocked_dependents
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
        # Walk through valid transitions: pending → in_progress → review_ready → done
        update_task_status(1, "in_progress")
        update_task_status(1, "review_ready")
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

    def test_state_with_values(self):
        state = DevelopmentState(
            project_id=1,
            task_id=42,
            branch_name="task-42-feature",
            developer_id="dev_p1",
        )
        assert state.task_id == 42
        assert state.branch_name == "task-42-feature"

    def test_no_checkin_fields(self):
        """Verify checkin_thread_id and checkin_approved were removed."""
        state = DevelopmentState()
        assert not hasattr(state, "checkin_thread_id")
        assert not hasattr(state, "checkin_approved")


class TestDevelopmentFlowAssignment:
    """Test task assignment logic."""

    @patch("backend.flows.development_flow.get_available_agent_by_role")
    @patch("backend.flows.development_flow.log_flow_event")
    def test_assign_task_success(self, mock_log, mock_avail_agent, db_conn, executing_project):
        mock_avail_agent.return_value = make_mock_agent("developer", executing_project)

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1

        result = flow.assign_task()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.dependencies_met is True
        assert flow.state.developer_id == f"developer_p{executing_project}"

        # Routing is now handled by the router method
        route = flow.route_assignment()
        assert route == "task_assigned"

        # Verify task was moved to in_progress in DB
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 1").fetchone()
        assert row["status"] == "in_progress"

    @patch("backend.flows.development_flow.log_flow_event")
    def test_assign_task_blocked(self, mock_log, db_conn, executing_project):
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

    def test_assign_task_not_found(self, db_conn):
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


class TestDevelopmentFlowReview:
    """Test review handling — CodeReviewFlow runs the full cycle internally."""

    @patch("backend.flows.code_review_flow.CodeReviewFlow")
    @patch("backend.flows.development_flow.log_flow_event")
    def test_request_review_delegates_to_code_review_flow(self, mock_log, MockReviewFlow, db_conn, executing_project):
        mock_review_instance = MagicMock()
        mock_review_instance.state.review_status = ReviewStatus.APPROVED
        MockReviewFlow.return_value = mock_review_instance

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.task_title = "Implement feature A"
        flow.state.branch_name = "task-1-feature"
        flow.state.developer_id = "developer_p1"

        result = flow.request_review()
        assert result is None
        assert flow.state.review_status == ReviewStatus.APPROVED
        mock_review_instance.kickoff.assert_called_once()


class TestPromoteUnblockedDependents:
    """Test dependency promotion when tasks complete."""

    def test_promote_single_dep_done(self, db_conn, executing_project):
        """Task with 1 dependency gets promoted when that dep completes."""
        # Task 3 (backlog) depends on task 1 (pending)
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.commit()

        # Verify task 3 is in backlog
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "backlog"

        # Complete task 1 through valid transitions
        update_task_status(1, "in_progress")
        update_task_status(1, "review_ready")
        update_task_status(1, "done")  # This triggers promote_unblocked_dependents

        # Task 3 should now be pending
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "pending"

    def test_no_promote_partial_deps(self, db_conn, executing_project):
        """Task with 2 deps — only 1 done — should NOT be promoted."""
        # Task 3 (backlog) depends on task 1 AND task 2
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 2, 'blocks')"""
        )
        db_conn.commit()

        # Complete only task 1
        update_task_status(1, "in_progress")
        update_task_status(1, "review_ready")
        update_task_status(1, "done")

        # Task 3 should still be backlog (task 2 not done)
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "backlog"

    def test_promote_all_deps_done(self, db_conn, executing_project):
        """Task with 2 deps gets promoted when both complete."""
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 2, 'blocks')"""
        )
        db_conn.commit()

        # Complete task 1
        update_task_status(1, "in_progress")
        update_task_status(1, "review_ready")
        update_task_status(1, "done")

        # Task 3 still backlog
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "backlog"

        # Complete task 2
        update_task_status(2, "in_progress")
        update_task_status(2, "review_ready")
        update_task_status(2, "done")

        # Now task 3 should be pending
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "pending"

    def test_promote_idempotent(self, db_conn, executing_project):
        """Calling promote twice should not cause errors."""
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.commit()

        # Complete task 1
        update_task_status(1, "in_progress")
        update_task_status(1, "review_ready")
        update_task_status(1, "done")

        # Task 3 is now pending
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "pending"

        # Calling promote again should return empty list, no error
        result = promote_unblocked_dependents(1)
        assert result == []

        # Task 3 still pending
        row = db_conn.execute("SELECT status FROM tasks WHERE id = 3").fetchone()
        assert row["status"] == "pending"
