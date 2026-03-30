"""Tests for backend.engine.summarizer.SmartContextSummarizer."""

import pytest

from backend.engine.loop_models import (
    ActionRecord,
    LoopPlan,
    LoopState,
    PlanStep,
)
from backend.engine.summarizer import SmartContextSummarizer


@pytest.fixture
def summarizer():
    return SmartContextSummarizer()


def _make_state(history=None, steps=None):
    """Helper to build a LoopState with given history and plan steps."""
    state = LoopState()
    if history:
        state.history = history
    if steps:
        state.plan = LoopPlan(steps=steps)
    return state


class TestGenerateSummary:
    def test_empty_history_returns_empty(self, summarizer):
        state = _make_state()
        assert summarizer.generate_summary(state) == ""

    def test_no_plan_returns_empty(self, summarizer):
        state = _make_state(
            history=[ActionRecord(step_index=1, summary="did something")],
        )
        # plan is default empty LoopPlan -- but it exists, so check no crash
        # Actually, the code checks `not state.plan` which is falsy for empty steps
        result = summarizer.generate_summary(state)
        # An empty LoopPlan is falsy (no steps), so this should return ""
        assert result == ""


class TestAnalyzeActions:
    def test_extracts_modified_files(self, summarizer):
        history = [
            ActionRecord(step_index=1, summary="Read src/main.py and found the bug"),
            ActionRecord(step_index=2, summary="Edited src/main.py to fix the issue"),
            ActionRecord(step_index=3, summary="Wrote tests/test_main.py with new tests"),
        ]
        result = summarizer._analyze_actions(history)
        assert "src/main.py" in result["files_modified"]
        assert len(result["files_modified"]["src/main.py"]) >= 1


class TestExtractDecisions:
    def test_identifies_technical_decisions(self, summarizer):
        history = [
            ActionRecord(step_index=1, summary="Using asyncio for concurrency"),
            ActionRecord(step_index=2, summary="Replaced old_func to new_func"),
        ]
        decisions = summarizer._extract_decisions(history)
        assert len(decisions) > 0
        # At least one decision should mention asyncio or the replacement
        combined = " ".join(decisions).lower()
        assert "asyncio" in combined or "old_func" in combined or "replaced" in combined


class TestExtractErrors:
    def test_detects_error_at_index_zero(self, summarizer):
        """Error at i==0 hits the 'elif has_error' branch -> 'Error detected:'."""
        history = [
            ActionRecord(step_index=1, summary="Error: ModuleNotFoundError in imports"),
            ActionRecord(step_index=2, summary="Installed the missing package"),
        ]
        errors = summarizer._extract_errors(history)
        assert len(errors) > 0
        assert any("Error detected" in e for e in errors)

    def test_resolved_errors(self, summarizer):
        history = [
            ActionRecord(step_index=1, summary="Attempted import"),
            ActionRecord(step_index=2, summary="Error: import failed, fixed by adding dependency"),
        ]
        errors = summarizer._extract_errors(history)
        assert len(errors) > 0
        assert any("resolved" in e.lower() for e in errors)


class TestExtractPending:
    def test_extracts_pending_work(self, summarizer):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="Fix the parser", status="done"),
            PlanStep(index=2, description="Write tests", status="pending"),
            PlanStep(index=3, description="Update docs", status="active"),
        ])
        pending = summarizer._extract_pending(plan, [])
        assert "Write tests" in pending
        assert "Update docs" in pending
        assert "Fix the parser" not in pending


class TestTokenBudget:
    def test_respects_budget(self):
        summarizer = SmartContextSummarizer(max_tokens=50)
        state = _make_state(
            history=[
                ActionRecord(step_index=i, summary=f"Edited file_{i}.py with many changes")
                for i in range(20)
            ],
            steps=[
                PlanStep(index=1, description="A very long pending step " * 10, status="pending"),
            ],
        )
        result = summarizer.generate_summary(state)
        # The output should be truncated to max_tokens
        assert len(result) <= 50
