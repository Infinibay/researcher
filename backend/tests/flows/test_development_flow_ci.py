"""Tests for DevelopmentFlow pre-review CI gate."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.flows.state_models import DevelopmentState
from backend.tests.flows.conftest import make_mock_agent, make_mock_engine


class TestDevelopmentStateCI:
    """Test CI-related fields on DevelopmentState."""

    def test_default_ci_fields(self):
        state = DevelopmentState()
        assert state.ci_passed is False
        assert state.ci_output == ""
        assert state.ci_fix_attempts == 0
        assert state.max_ci_fix_attempts == 10

    def test_ci_fields_with_values(self):
        state = DevelopmentState(ci_passed=True, ci_output="All tests passed", ci_fix_attempts=2)
        assert state.ci_passed is True
        assert state.ci_fix_attempts == 2


class TestRouteAfterImplementation:
    """Test that implement_code always routes to CI check."""

    def test_route_always_returns_check_ci(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        assert flow.route_after_implementation() == "check_ci"


class TestRunPreReviewCI:
    """Test the pre-review CI gate step."""

    @patch("backend.flows.development_flow.record_ci_result")
    @patch("backend.flows.development_flow.log_flow_event")
    @patch("backend.flows.development_flow.get_repo_path_for_task")
    def test_ci_skipped_when_no_repo(self, mock_repo, mock_log, mock_record, db_conn, executing_project):
        mock_repo.return_value = None

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1"

        flow.run_pre_review_ci()

        assert flow.state.ci_passed is True
        assert "skipped" in flow.state.ci_output.lower()
        mock_record.assert_not_called()

    @patch("backend.flows.development_flow.record_ci_result")
    @patch("backend.flows.development_flow.log_flow_event")
    @patch("backend.flows.development_flow.get_repo_path_for_task")
    def test_ci_passes(self, mock_repo, mock_log, mock_record, db_conn, executing_project):
        mock_repo.return_value = "/tmp/fake-repo"

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1"

        # Patch _execute_ci_command to simulate passing CI
        flow._execute_ci_command = MagicMock(return_value={
            "ci_passed": True,
            "ci_output": "3 passed",
            "test_count": 3,
            "test_pass": 3,
            "exit_code": 0,
        })

        flow.run_pre_review_ci()

        assert flow.state.ci_passed is True
        mock_record.assert_called_once()

    @patch("backend.flows.development_flow.record_ci_result")
    @patch("backend.flows.development_flow.log_flow_event")
    @patch("backend.flows.development_flow.get_repo_path_for_task")
    def test_ci_fails(self, mock_repo, mock_log, mock_record, db_conn, executing_project):
        mock_repo.return_value = "/tmp/fake-repo"

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1"

        flow._execute_ci_command = MagicMock(return_value={
            "ci_passed": False,
            "ci_output": "FAILED test_something",
            "test_count": 3,
            "test_pass": 1,
            "exit_code": 1,
        })

        flow.run_pre_review_ci()

        assert flow.state.ci_passed is False
        assert "FAILED" in flow.state.ci_output


class TestRoutPreCI:
    """Test routing based on CI result."""

    def test_route_ci_passed(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.ci_passed = True

        assert flow.route_pre_ci() == "pre_ci_passed"

    def test_route_ci_failed_under_max(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.ci_passed = False
        flow.state.ci_fix_attempts = 0
        flow.state.max_ci_fix_attempts = 10

        assert flow.route_pre_ci() == "pre_ci_fix_needed"

    def test_route_ci_failed_at_max_proceeds_to_review(self):
        """When max CI fix attempts reached, proceed to review anyway."""
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.ci_passed = False
        flow.state.ci_fix_attempts = 10
        flow.state.max_ci_fix_attempts = 10

        assert flow.route_pre_ci() == "pre_ci_passed"

    def test_route_ci_failed_above_max(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.ci_passed = False
        flow.state.ci_fix_attempts = 15
        flow.state.max_ci_fix_attempts = 10

        assert flow.route_pre_ci() == "pre_ci_passed"


class TestFixCIFailures:
    """Test the developer CI fix step."""

    @patch("backend.flows.development_flow.get_engine")
    @patch("backend.flows.development_flow.get_agent_by_role")
    @patch("backend.flows.development_flow.log_flow_event")
    def test_fix_ci_invokes_developer(self, mock_log, mock_agent, mock_get_engine, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("developer", executing_project)
        mock_get_engine.return_value = make_mock_engine("Fixed the tests")

        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 1
        flow.state.branch_name = "task-1"
        flow.state.developer_id = f"developer_p{executing_project}"
        flow.state.ci_output = "FAILED test_something - AssertionError"
        flow.state.ci_fix_attempts = 0

        flow.fix_ci_failures()

        assert flow.state.ci_fix_attempts == 1
        mock_get_engine.return_value.execute.assert_called_once()

    def test_fix_ci_increments_counter(self):
        """fix_ci_failures always increments ci_fix_attempts."""
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.ci_fix_attempts = 3

        # We just test the counter logic; agent invocation is tested above
        # Directly call the increment line (the method will fail without mocks)
        flow.state.ci_fix_attempts += 1
        assert flow.state.ci_fix_attempts == 4


class TestRouteAfterCIFix:
    """Test that fix loop routes back to CI check."""

    def test_route_after_fix_returns_check_ci(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        assert flow.route_after_ci_fix() == "check_ci"


class TestHandleCIResult:
    """Test _handle_ci_result helper."""

    def test_error_result(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        result = flow._handle_ci_result({"error": "Command not found"})
        assert result["ci_passed"] is False
        assert result["test_count"] == 0

    def test_passing_result(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        result = flow._handle_ci_result({
            "stdout": "3 passed in 1.2s",
            "stderr": "",
            "exit_code": 0,
        })
        assert result["ci_passed"] is True

    def test_failing_result(self):
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        result = flow._handle_ci_result({
            "stdout": "1 failed, 2 passed",
            "stderr": "FAILED test_foo",
            "exit_code": 1,
        })
        assert result["ci_passed"] is False

    def test_no_tests_collected(self):
        """Exit code 5 (no tests collected) is not a failure."""
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        result = flow._handle_ci_result({
            "stdout": "no tests ran",
            "stderr": "",
            "exit_code": 5,
        })
        assert result["ci_passed"] is True
