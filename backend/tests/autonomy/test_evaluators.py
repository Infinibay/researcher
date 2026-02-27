"""Tests for the role-specific event evaluators."""

from __future__ import annotations

import json

from backend.autonomy.evaluators import (
    DeveloperEvaluator,
    EvalContext,
    ReviewerEvaluator,
    TeamLeadEvaluator,
    get_evaluator_for_role,
)


def _make_event(event_type: str, priority: int = 50, payload: dict | None = None) -> dict:
    return {
        "id": 1,
        "agent_id": "dev_1_p1",
        "project_id": 1,
        "event_type": event_type,
        "priority": priority,
        "status": "pending",
        "payload_json": json.dumps(payload or {}),
    }


def _default_context() -> EvalContext:
    return EvalContext(
        project_status="executing",
        total_tasks=10,
        done_tasks=3,
        stuck_tasks=0,
        in_progress_tasks=2,
    )


class TestDeveloperEvaluator:
    def test_user_message_highest_priority(self):
        ev = DeveloperEvaluator()
        ctx = _default_context()
        score = ev.score(_make_event("user_message_received"), ctx)
        assert score > 0.9

    def test_task_resume_higher_than_new_task(self):
        ev = DeveloperEvaluator()
        ctx = _default_context()
        resume = ev.score(_make_event("task_resume"), ctx)
        available = ev.score(_make_event("task_available"), ctx)
        assert resume > available

    def test_pick_best_selects_highest_scored(self):
        ev = DeveloperEvaluator()
        ctx = _default_context()
        events = [
            _make_event("task_available"),
            _make_event("user_message_received"),
            _make_event("task_resume"),
        ]
        best = ev.pick_best(events, ctx)
        assert best is not None
        assert best["event_type"] == "user_message_received"

    def test_pick_best_returns_none_for_empty(self):
        ev = DeveloperEvaluator()
        assert ev.pick_best([], _default_context()) is None


class TestTeamLeadEvaluator:
    def test_stagnation_high_priority(self):
        ev = TeamLeadEvaluator()
        ctx = _default_context()
        score = ev.score(_make_event("stagnation_detected"), ctx)
        assert score > 0.8

    def test_all_tasks_done_highest_after_user_msg(self):
        ev = TeamLeadEvaluator()
        ctx = _default_context()
        all_done = ev.score(_make_event("all_tasks_done"), ctx)
        msg = ev.score(_make_event("user_message_received"), ctx)
        assert msg > all_done
        assert all_done > 0.85


class TestReviewerEvaluator:
    def test_review_ready_highest_task(self):
        ev = ReviewerEvaluator()
        ctx = _default_context()
        score = ev.score(_make_event("review_ready"), ctx)
        assert score == 0.9


def test_get_evaluator_for_role():
    ev = get_evaluator_for_role("developer")
    assert isinstance(ev, DeveloperEvaluator)

    ev = get_evaluator_for_role("team_lead")
    assert isinstance(ev, TeamLeadEvaluator)

    ev = get_evaluator_for_role("code_reviewer")
    assert isinstance(ev, ReviewerEvaluator)

    # Unknown roles fall back to DeveloperEvaluator
    ev = get_evaluator_for_role("unknown_role")
    assert isinstance(ev, DeveloperEvaluator)
