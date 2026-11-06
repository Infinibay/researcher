"""Tests for DevelopmentFlow pre-review CI gate."""

from __future__ import annotations

import pytest

from backend.flows.state_models import DevelopmentState


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


class TestRetiredCIGate:
    """A compatibility hint cannot manufacture CI evidence from old state or a missing repository."""

    @pytest.mark.parametrize("ci_passed", [False, True])
    def test_old_ci_flag_stays_historical(self, db_conn, executing_project, ci_passed):
        """Both old CI values return an owner hint without changing the original task."""
        from backend.flows.development_flow import DevelopmentFlow

        flow = DevelopmentFlow()
        flow.state.ci_passed = ci_passed
        before = dict(db_conn.execute("SELECT * FROM tasks WHERE id=1").fetchone())
        hint = flow.kickoff({"project_id": executing_project, "task_id": 1})
        assert hint["inference_started_by_handoff"] is False
        assert dict(db_conn.execute("SELECT * FROM tasks WHERE id=1").fetchone()) == before
