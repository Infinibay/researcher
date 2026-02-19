"""Tests for CodeReviewFlow."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from backend.flows.helpers import get_task_by_id, increment_task_retry
from backend.flows.state_models import CodeReviewState, ReviewStatus
from backend.tests.flows.conftest import make_mock_agent, make_mock_crew


class TestCodeReviewState:
    """Test CodeReviewState model."""

    def test_default_state(self):
        state = CodeReviewState()
        assert state.rejection_count == 0
        assert state.max_rejections == 7
        assert state.review_status == ReviewStatus.PENDING
        assert state.reviewer_comments == []

    def test_state_with_values(self):
        state = CodeReviewState(
            project_id=1,
            task_id=42,
            branch_name="task-42-feature",
            max_rejections=5,
        )
        assert state.max_rejections == 5
        assert state.branch_name == "task-42-feature"


class TestCodeReviewFlowStart:
    """Test review request handling."""

    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_receive_review_request(self, mock_log, db_conn, executing_project):
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1-feature"

        result = flow.receive_review_request()
        # @start() methods no longer return routing strings
        assert result is None
        assert flow.state.review_status == ReviewStatus.REVIEWING

        # Routing is now handled by the router method
        route = flow.route_review_request()
        assert route == "review_requested"

    def test_receive_review_request_missing_task(self, db_conn):
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.project_id = 1
        flow.state.task_id = 99999
        flow.state.branch_name = "task-99999-feature"

        result = flow.receive_review_request()
        # @start() methods no longer return routing strings
        assert result is None

        # Routing is now handled by the router method
        route = flow.route_review_request()
        assert route == "error"


class TestCodeReviewFlowReview:
    """Test the review execution and routing."""

    @patch("backend.flows.code_review_flow.Crew")
    @patch("backend.flows.code_review_flow.Task")
    @patch("backend.flows.code_review_flow.get_available_agent_by_role")
    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_perform_review_approved(self, mock_log, mock_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("code_reviewer", executing_project)
        MockCrew.return_value = make_mock_crew("APPROVED: Code looks good")
        MockTask.return_value = MagicMock()

        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1-feature"

        result = flow.perform_review()
        # @listen() methods no longer return routing strings
        assert result is None
        assert flow.state.review_status == ReviewStatus.APPROVED

        # Routing is now handled by the router method
        route = flow.review_outcome_router()
        assert route == "review_approved"

    @patch("backend.flows.code_review_flow.Crew")
    @patch("backend.flows.code_review_flow.Task")
    @patch("backend.flows.code_review_flow.get_available_agent_by_role")
    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_perform_review_rejected(self, mock_log, mock_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("code_reviewer", executing_project)
        MockCrew.return_value = make_mock_crew("REJECTED: Missing error handling")
        MockTask.return_value = MagicMock()

        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1-feature"

        result = flow.perform_review()
        # @listen() methods no longer return routing strings
        assert result is None
        assert flow.state.review_status == ReviewStatus.REJECTED
        assert len(flow.state.reviewer_comments) == 1

        # Routing is now handled by the router method
        route = flow.review_outcome_router()
        assert route == "request_rework"


class TestCodeReviewFlowRejectionRouting:
    """Test rejection routing and escalation."""

    def test_rejection_count_below_max(self):
        state = CodeReviewState(rejection_count=0, max_rejections=3)
        state.rejection_count += 1
        assert state.rejection_count < state.max_rejections

    def test_rejection_count_at_max(self):
        state = CodeReviewState(rejection_count=2, max_rejections=3)
        state.rejection_count += 1
        assert state.rejection_count >= state.max_rejections


class TestCodeReviewFlowEscalation:
    """Test escalation behavior."""

    @patch("backend.flows.code_review_flow.notify_team_lead")
    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_handle_escalation(self, mock_log, mock_notify, db_conn, executing_project):
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1-feature"
        flow.state.rejection_count = 3
        flow.state.reviewer_id = "code_reviewer_p1"
        flow.state.reviewer_comments = [
            "REJECTED: Issue 1",
            "REJECTED: Issue 2",
            "REJECTED: Issue 3",
        ]

        result = flow.handle_escalation()
        # @listen() methods no longer return routing strings
        assert result is None
        assert flow.state.review_status == ReviewStatus.ESCALATED
        mock_notify.assert_called_once()


class TestIncrementTaskRetry:
    """Test the retry counter helper."""

    def test_increment_retry(self, db_conn, executing_project):
        task = get_task_by_id(1)
        assert task["retry_count"] == 0

        new_count = increment_task_retry(1)
        assert new_count == 1

        new_count = increment_task_retry(1)
        assert new_count == 2
