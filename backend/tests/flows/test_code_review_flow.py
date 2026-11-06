"""Tests for CodeReviewFlow."""

from __future__ import annotations

from backend.flows.helpers import get_task_by_id, increment_task_retry
from backend.flows.state_models import CodeReviewState, ReviewStatus


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


class TestCodeReviewCompatibility:
    """Historical review entry can point to the owner but cannot approve or merge work."""

    def test_old_approval_fields_do_not_change_the_task(self, db_conn, executing_project):
        """A persisted approval string remains data even when passed to the compatibility kickoff."""
        from backend.flows.code_review_flow import CodeReviewFlow

        flow = CodeReviewFlow()
        flow.state.review_status = ReviewStatus.APPROVED
        before = dict(db_conn.execute("SELECT * FROM tasks WHERE id=4").fetchone())
        hint = flow.kickoff({"project_id": executing_project, "task_id": 4})
        assert hint["event_authorizes_work"] is False
        assert dict(db_conn.execute("SELECT * FROM tasks WHERE id=4").fetchone()) == before


class TestIncrementTaskRetry:
    """Test the retry counter helper."""

    def test_increment_retry(self, db_conn, executing_project):
        task = get_task_by_id(1)
        assert task["retry_count"] == 0

        new_count = increment_task_retry(1)
        assert new_count == 1

        new_count = increment_task_retry(1)
        assert new_count == 2
