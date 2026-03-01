"""Tests for TaskStateMachine in backend/state/machine.py."""

import pytest

from backend.state.machine import (
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
    TaskStateMachine,
)


class TestCanTransition:
    """Verify every valid edge returns True and invalid edges return False."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (src, tgt)
            for src, targets in VALID_TRANSITIONS.items()
            for tgt in targets
        ],
    )
    def test_can_transition_valid(self, current, target):
        assert TaskStateMachine.can_transition(current, target) is True

    @pytest.mark.parametrize(
        "current,target",
        [
            ("backlog", "done"),
            ("backlog", "in_progress"),
            ("backlog", "review_ready"),
            ("backlog", "failed"),
            ("pending", "done"),
            ("pending", "backlog"),
            ("in_progress", "done"),
            ("in_progress", "pending"),
            ("done", "pending"),
            ("done", "backlog"),
            ("done", "failed"),
            ("cancelled", "backlog"),
            ("cancelled", "failed"),
            ("failed", "in_progress"),
            ("failed", "done"),
        ],
    )
    def test_can_transition_invalid(self, current, target):
        assert TaskStateMachine.can_transition(current, target) is False


class TestValidateTransition:
    def test_validate_transition_raises_on_invalid_move(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            TaskStateMachine.validate_transition("done", "pending")

    def test_validate_transition_raises_on_unknown_target(self):
        with pytest.raises(ValueError, match="Invalid status"):
            TaskStateMachine.validate_transition("backlog", "nonexistent_status")

    def test_validate_transition_succeeds_for_valid(self):
        # Should not raise
        TaskStateMachine.validate_transition("backlog", "pending")


class TestIsTerminal:
    @pytest.mark.parametrize("status", ["done", "cancelled", "failed"])
    def test_terminal_statuses(self, status):
        assert TaskStateMachine.is_terminal(status) is True

    @pytest.mark.parametrize("status", ["backlog", "pending", "in_progress", "review_ready", "rejected", "blocked"])
    def test_non_terminal_statuses(self, status):
        assert TaskStateMachine.is_terminal(status) is False


class TestGetAllowedTransitions:
    def test_backlog_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("backlog") == {"pending", "cancelled"}

    def test_pending_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("pending") == {"in_progress", "failed", "cancelled"}

    def test_in_progress_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("in_progress") == {"review_ready", "failed", "cancelled"}

    def test_review_ready_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("review_ready") == {"done", "rejected", "failed", "cancelled"}

    def test_rejected_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("rejected") == {"in_progress", "failed", "cancelled"}

    def test_done_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("done") == set()

    def test_cancelled_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("cancelled") == set()

    def test_failed_transitions(self):
        assert TaskStateMachine.get_allowed_transitions("failed") == {"pending", "cancelled"}

    def test_unknown_status_returns_empty(self):
        assert TaskStateMachine.get_allowed_transitions("imaginary") == set()
