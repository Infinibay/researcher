"""Tests for CodeReviewFlow."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from backend.flows.helpers import get_task_by_id, increment_task_retry
from backend.flows.state_models import CodeReviewState, ReviewStatus
from backend.tests.flows.conftest import make_mock_agent, make_mock_engine


class TestCodeReviewState:
    """Test CodeReviewState model."""

    def test_default_state(self):
        state = CodeReviewState()
        assert state.rejection_count == 0
        assert state.review_status == ReviewStatus.PENDING
        assert state.reviewer_comments == []

    def test_state_with_values(self):
        state = CodeReviewState(
            project_id=1,
            task_id=42,
            branch_name="task-42-feature",
        )
        assert state.branch_name == "task-42-feature"


class TestCodeReviewFlowStart:
    """Test review request handling."""

    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_receive_review_request(self, mock_log, db_conn, executing_project):
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 4  # in_progress task from fixture
        flow.state.branch_name = "task-4-feature"

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

    @patch("backend.flows.code_review_flow.get_engine")
    @patch("backend.flows.code_review_flow.get_available_agent_by_role")
    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_perform_review_approved(self, mock_log, mock_agent, mock_get_engine, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("code_reviewer", executing_project)
        mock_get_engine.return_value = make_mock_engine("APPROVED: Code looks good")

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

    @patch("backend.flows.code_review_flow.get_engine")
    @patch("backend.flows.code_review_flow.get_available_agent_by_role")
    @patch("backend.flows.code_review_flow.log_flow_event")
    def test_perform_review_rejected(self, mock_log, mock_agent, mock_get_engine, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("code_reviewer", executing_project)
        mock_get_engine.return_value = make_mock_engine("REJECTED: Missing error handling")

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
    """Test rejection routing — always loops back to rework, no escalation."""

    @patch("backend.flows.code_review_flow.increment_task_retry")
    def test_rejection_always_routes_to_rework(self, mock_retry):
        """Rejections always route to request_rework regardless of count."""
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.review_status = ReviewStatus.REJECTED
        flow.state.rejection_count = 0

        route = flow.review_outcome_router()
        assert route == "request_rework"
        assert flow.state.rejection_count == 1

    @patch("backend.flows.code_review_flow.increment_task_retry")
    def test_high_rejection_count_still_routes_to_rework(self, mock_retry):
        """Even high rejection counts route to rework, not escalation."""
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.task_id = 1
        flow.state.review_status = ReviewStatus.REJECTED
        flow.state.rejection_count = 99

        route = flow.review_outcome_router()
        assert route == "request_rework"
        assert flow.state.rejection_count == 100


class TestIncrementTaskRetry:
    """Test the retry counter helper."""

    def test_increment_retry(self, db_conn, executing_project):
        task = get_task_by_id(1)
        assert task["retry_count"] == 0

        new_count = increment_task_retry(1)
        assert new_count == 1

        new_count = increment_task_retry(1)
        assert new_count == 2
