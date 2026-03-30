"""Tests for new features in backend.engine.loop_models."""

import pytest

from backend.engine.loop_models import (
    ActionRecord,
    LoopPlan,
    LoopState,
    MAX_CACHE_CONTENT_SIZE,
    MAX_OPENED_FILES,
    OPENED_FILE_TTL,
    OpenedFile,
    PlanStep,
    StepOperation,
    StepResult,
)


class TestOpenedFile:
    def test_creation_defaults(self):
        f = OpenedFile(path="/tmp/a.py", content="hello")
        assert f.path == "/tmp/a.py"
        assert f.content == "hello"
        assert f.ttl == 8
        assert f.pinned is False

    def test_tick_decrements_ttl(self):
        f = OpenedFile(path="/tmp/a.py", content="x", ttl=5)
        f.tick()
        assert f.ttl == 4
        f.tick(3)
        assert f.ttl == 1

    def test_tick_clamps_to_zero(self):
        f = OpenedFile(path="/tmp/a.py", content="x", ttl=2)
        f.tick(10)
        assert f.ttl == 0

    def test_expired_when_ttl_zero(self):
        f = OpenedFile(path="/tmp/a.py", content="x", ttl=0)
        assert f.expired is True

    def test_not_expired_when_ttl_positive(self):
        f = OpenedFile(path="/tmp/a.py", content="x", ttl=1)
        assert f.expired is False

    def test_pinned_never_expires(self):
        f = OpenedFile(path="/tmp/a.py", content="x", ttl=0, pinned=True)
        assert f.expired is False

    def test_pinned_tick_is_noop(self):
        f = OpenedFile(path="/tmp/a.py", content="x", ttl=5, pinned=True)
        f.tick(100)
        assert f.ttl == 5


class TestLoopStateCacheFile:
    def test_basic_cache(self):
        state = LoopState()
        state.cache_file("/tmp/a.py", "content")
        assert "/tmp/a.py" in state.opened_files
        assert state.opened_files["/tmp/a.py"].content == "content"
        assert state.opened_files["/tmp/a.py"].ttl == OPENED_FILE_TTL

    def test_max_size_rejection(self):
        state = LoopState()
        large_content = "x" * (MAX_CACHE_CONTENT_SIZE + 1)
        state.cache_file("/tmp/big.py", large_content)
        assert "/tmp/big.py" not in state.opened_files

    def test_lru_eviction(self):
        state = LoopState()
        # Fill to max
        for i in range(MAX_OPENED_FILES):
            state.cache_file(f"/tmp/f{i}.py", f"c{i}")
        assert len(state.opened_files) == MAX_OPENED_FILES

        # Set one file to have lowest TTL (will be evicted)
        state.opened_files["/tmp/f0.py"].ttl = 1

        # Add one more -> should evict /tmp/f0.py
        state.cache_file("/tmp/extra.py", "extra")
        assert "/tmp/extra.py" in state.opened_files
        assert "/tmp/f0.py" not in state.opened_files
        assert len(state.opened_files) == MAX_OPENED_FILES

    def test_pinned_files_not_evicted(self):
        state = LoopState()
        # Fill with pinned files
        for i in range(MAX_OPENED_FILES):
            state.cache_file(f"/tmp/p{i}.py", f"c{i}", pinned=True)

        # Add one more (also pinned) -> all pinned, cannot evict, stays over limit
        state.cache_file("/tmp/extra.py", "extra", pinned=True)
        assert len(state.opened_files) == MAX_OPENED_FILES + 1


class TestLoopStateRefreshFile:
    def test_refresh_marks_pinned(self):
        state = LoopState()
        state.cache_file("/tmp/a.py", "old")
        assert state.opened_files["/tmp/a.py"].pinned is False

        state.refresh_file("/tmp/a.py", "new")
        assert state.opened_files["/tmp/a.py"].content == "new"
        assert state.opened_files["/tmp/a.py"].pinned is True
        assert state.opened_files["/tmp/a.py"].ttl == OPENED_FILE_TTL

    def test_refresh_new_file(self):
        state = LoopState()
        state.refresh_file("/tmp/new.py", "content")
        assert "/tmp/new.py" in state.opened_files
        assert state.opened_files["/tmp/new.py"].pinned is True

    def test_refresh_oversized_removes(self):
        state = LoopState()
        state.cache_file("/tmp/a.py", "small")
        state.refresh_file("/tmp/a.py", "x" * (MAX_CACHE_CONTENT_SIZE + 1))
        assert "/tmp/a.py" not in state.opened_files


class TestLoopStateTickOpenedFiles:
    def test_ages_and_removes_expired(self):
        state = LoopState()
        state.cache_file("/tmp/a.py", "a")
        state.opened_files["/tmp/a.py"].ttl = 1

        state.cache_file("/tmp/b.py", "b")
        state.opened_files["/tmp/b.py"].ttl = 10

        state.tick_opened_files(tool_calls=1)
        assert "/tmp/a.py" not in state.opened_files  # expired (ttl was 1, now 0)
        assert "/tmp/b.py" in state.opened_files

    def test_pinned_files_survive(self):
        state = LoopState()
        state.cache_file("/tmp/a.py", "a", pinned=True)
        state.opened_files["/tmp/a.py"].ttl = 0  # would expire if not pinned

        state.tick_opened_files(tool_calls=5)
        assert "/tmp/a.py" in state.opened_files


class TestActionRecord:
    def test_new_fields(self):
        record = ActionRecord(
            step_index=1,
            summary="Did stuff",
            tool_calls_count=3,
            files_to_preload=["/tmp/a.py", "/tmp/b.py"],
            changes_made="edited a.py",
            discovered_context="found config pattern",
            pending_items="need to fix tests",
            anti_patterns="repeated read of same file",
        )
        assert record.files_to_preload == ["/tmp/a.py", "/tmp/b.py"]
        assert record.changes_made == "edited a.py"
        assert record.discovered_context == "found config pattern"
        assert record.pending_items == "need to fix tests"
        assert record.anti_patterns == "repeated read of same file"

    def test_defaults(self):
        record = ActionRecord(step_index=0, summary="s")
        assert record.files_to_preload == []
        assert record.changes_made == ""
        assert record.discovered_context == ""
        assert record.pending_items == ""
        assert record.anti_patterns == ""


class TestStepResult:
    def test_explore_status(self):
        result = StepResult(summary="investigating", status="explore")
        assert result.status == "explore"

    def test_default_status(self):
        result = StepResult(summary="s")
        assert result.status == "continue"

    def test_done_with_final_answer(self):
        result = StepResult(summary="s", status="done", final_answer="all done")
        assert result.final_answer == "all done"


class TestLoopPlanApplyOperations:
    def test_preserves_done_steps(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="step 1", status="done"),
            PlanStep(index=2, description="step 2", status="pending"),
        ])

        # Try to replace done step 1
        plan.apply_operations([
            StepOperation(op="add", index=1, description="new step 1"),
        ])

        # Done step should be preserved
        step1 = next(s for s in plan.steps if s.index == 1)
        assert step1.status == "done"
        assert step1.description == "step 1"

    def test_add_replaces_pending(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="old", status="pending"),
        ])
        plan.apply_operations([
            StepOperation(op="add", index=1, description="new"),
        ])
        step1 = next(s for s in plan.steps if s.index == 1)
        assert step1.description == "new"
        assert step1.status == "pending"

    def test_remove_skips_pending(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="s1", status="pending"),
            PlanStep(index=2, description="s2", status="done"),
        ])
        plan.apply_operations([
            StepOperation(op="remove", index=1),
            StepOperation(op="remove", index=2),  # done step should not be skipped
        ])
        assert plan.steps[0].status == "skipped"
        assert plan.steps[1].status == "done"  # done is not removed

    def test_modify(self):
        plan = LoopPlan(steps=[
            PlanStep(index=1, description="old desc"),
        ])
        plan.apply_operations([
            StepOperation(op="modify", index=1, description="new desc"),
        ])
        assert plan.steps[0].description == "new desc"

    def test_steps_sorted_after_operations(self):
        plan = LoopPlan(steps=[])
        plan.apply_operations([
            StepOperation(op="add", index=3, description="third"),
            StepOperation(op="add", index=1, description="first"),
            StepOperation(op="add", index=2, description="second"),
        ])
        indices = [s.index for s in plan.steps]
        assert indices == [1, 2, 3]
