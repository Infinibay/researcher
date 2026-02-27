"""Tests for atomic review claim — prevents duplicate reviews (TOCTOU race)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.autonomy.handlers import ReviewHandler
from backend.tests.autonomy.conftest import seed_roster, seed_task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_reviewer(db_conn, task_id: int) -> str | None:
    """Return the reviewer field for a task."""
    row = db_conn.execute(
        "SELECT reviewer FROM tasks WHERE id = ?", (task_id,),
    ).fetchone()
    return row["reviewer"] if row else None


# ===========================================================================
# 1. First reviewer claims task → succeeds
# ===========================================================================


class TestClaimReviewBasic:
    def test_first_claim_succeeds(self, db_conn, executing_project):
        pid = executing_project
        agent_id = "code_reviewer_p1"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        task_id = seed_task(db_conn, pid, title="Review me", task_type="code", status="review_ready")

        result = ReviewHandler._claim_review(task_id, agent_id)

        assert result is True
        assert _get_reviewer(db_conn, task_id) == agent_id

    # ===========================================================================
    # 2. Second reviewer tries to claim same task → fails
    # ===========================================================================

    def test_second_claim_fails(self, db_conn, executing_project):
        pid = executing_project
        agent1 = "code_reviewer_1_p1"
        agent2 = "code_reviewer_2_p1"
        seed_roster(db_conn, pid, [(agent1, "code_reviewer"), (agent2, "code_reviewer")])

        task_id = seed_task(db_conn, pid, title="Review me", task_type="code", status="review_ready")

        # First claim
        assert ReviewHandler._claim_review(task_id, agent1) is True
        # Second claim
        assert ReviewHandler._claim_review(task_id, agent2) is False
        # Reviewer stays as agent1
        assert _get_reviewer(db_conn, task_id) == agent1

    # ===========================================================================
    # 3. Same reviewer reclaims (idempotent) → succeeds
    # ===========================================================================

    def test_same_reviewer_reclaim_idempotent(self, db_conn, executing_project):
        pid = executing_project
        agent_id = "code_reviewer_p1"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        task_id = seed_task(db_conn, pid, title="Review me", task_type="code", status="review_ready")

        assert ReviewHandler._claim_review(task_id, agent_id) is True
        # Reclaim by same agent — should still succeed
        assert ReviewHandler._claim_review(task_id, agent_id) is True
        assert _get_reviewer(db_conn, task_id) == agent_id

    # ===========================================================================
    # 4. Task not in review_ready → claim fails
    # ===========================================================================

    def test_claim_fails_wrong_status(self, db_conn, executing_project):
        pid = executing_project
        agent_id = "code_reviewer_p1"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        for status in ("pending", "in_progress", "done", "rejected"):
            task_id = seed_task(
                db_conn, pid, title=f"Task {status}", task_type="code", status=status,
            )
            assert ReviewHandler._claim_review(task_id, agent_id) is False

    # ===========================================================================
    # 5. After release, another reviewer can claim
    # ===========================================================================

    def test_release_allows_reclaim(self, db_conn, executing_project):
        pid = executing_project
        agent1 = "code_reviewer_1_p1"
        agent2 = "code_reviewer_2_p1"
        seed_roster(db_conn, pid, [(agent1, "code_reviewer"), (agent2, "code_reviewer")])

        task_id = seed_task(db_conn, pid, title="Review me", task_type="code", status="review_ready")

        # Agent1 claims
        assert ReviewHandler._claim_review(task_id, agent1) is True
        # Agent2 cannot claim
        assert ReviewHandler._claim_review(task_id, agent2) is False

        # Agent1 releases
        ReviewHandler._release_review(task_id, agent1)
        assert _get_reviewer(db_conn, task_id) is None

        # Agent2 can now claim
        assert ReviewHandler._claim_review(task_id, agent2) is True
        assert _get_reviewer(db_conn, task_id) == agent2


# ===========================================================================
# 6. Race simulation: two ReviewHandlers process events for same task
# ===========================================================================


class TestReviewClaimRace:
    def test_only_one_handler_proceeds(self, db_conn, executing_project):
        """Simulate two ReviewHandler.execute() calls for the same task.

        Only the first should proceed past the claim; the second should bail out.
        """
        pid = executing_project
        agent1 = "code_reviewer_1_p1"
        agent2 = "code_reviewer_2_p1"
        seed_roster(db_conn, pid, [(agent1, "code_reviewer"), (agent2, "code_reviewer")])

        task_id = seed_task(db_conn, pid, title="Race task", task_type="code", status="review_ready")

        payload = json.dumps({"task_id": task_id})

        event1 = {
            "id": 1,
            "project_id": pid,
            "agent_id": agent1,
            "event_type": "review_ready",
            "payload_json": payload,
        }
        event2 = {
            "id": 2,
            "project_id": pid,
            "agent_id": agent2,
            "event_type": "review_ready",
            "payload_json": payload,
        }

        handler = ReviewHandler()

        # Mock _run_code_review to track calls without actually running flows
        calls = []

        def mock_run_code_review(project_id, task_id, task):
            calls.append(("code_review", project_id, task_id))

        # Mock has_active_review_run and _has_recent_completed_review to not block
        with patch.object(handler, "_run_code_review", mock_run_code_review), \
             patch("backend.autonomy.handlers.ReviewHandler._has_recent_completed_review", return_value=False):
            handler.execute(event1)
            handler.execute(event2)

        # Only one should have proceeded to _run_code_review
        assert len(calls) == 1
        assert calls[0] == ("code_review", pid, task_id)
        # The winner is agent1
        assert _get_reviewer(db_conn, task_id) == agent1
