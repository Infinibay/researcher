"""Tests for backend.engine.tool_executor."""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.engine.file_change_tracker import FileChangeTracker
from backend.engine.loop_models import LoopState
from backend.engine.tool_executor import (
    FILE_CHANGE_TOOLS,
    WRITE_TOOLS,
    batch_tool_calls,
    capture_pre_content,
    execute_tool_calls_parallel,
    update_opened_files_cache,
)


def _make_tool_call(name, arguments="{}"):
    """Create a mock tool call object."""
    tc = SimpleNamespace()
    tc.function = SimpleNamespace()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


class TestBatchToolCalls:
    def test_groups_reads_together(self):
        calls = [
            _make_tool_call("read_file"),
            _make_tool_call("list_directory"),
            _make_tool_call("code_search"),
        ]
        batches = batch_tool_calls(calls)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_writes_get_own_batch(self):
        calls = [
            _make_tool_call("read_file"),
            _make_tool_call("create_file"),
            _make_tool_call("read_file"),
        ]
        batches = batch_tool_calls(calls)
        # read | write | read
        assert len(batches) == 3
        assert batches[0][0].function.name == "read_file"
        assert batches[1][0].function.name == "create_file"
        assert batches[2][0].function.name == "read_file"

    def test_consecutive_reads_before_write(self):
        calls = [
            _make_tool_call("read_file"),
            _make_tool_call("list_directory"),
            _make_tool_call("edit_file"),
        ]
        batches = batch_tool_calls(calls)
        assert len(batches) == 2  # reads together, then write
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_empty_calls(self):
        assert batch_tool_calls([]) == []

    def test_multiple_writes_sequential(self):
        calls = [
            _make_tool_call("create_file"),
            _make_tool_call("edit_file"),
        ]
        batches = batch_tool_calls(calls)
        assert len(batches) == 2  # each write gets own batch


class TestExecuteToolCallsParallel:
    def test_executes_and_returns_in_order(self):
        calls = [
            _make_tool_call("read_file", '{"path": "a.py"}'),
            _make_tool_call("list_directory", '{"path": "."}'),
        ]

        mock_dispatch = {}

        with patch("backend.engine.tool_executor.execute_tool_call") as mock_exec:
            mock_exec.side_effect = ["content of a.py", "dir listing"]
            results = execute_tool_calls_parallel(calls, mock_dispatch)

        assert len(results) == 2
        assert results[0][0].function.name == "read_file"
        assert results[0][1] == "content of a.py"
        assert results[1][0].function.name == "list_directory"
        assert results[1][1] == "dir listing"

    def test_single_call(self):
        calls = [_make_tool_call("read_file", '{"path": "a.py"}')]

        with patch("backend.engine.tool_executor.execute_tool_call") as mock_exec:
            mock_exec.return_value = "result"
            results = execute_tool_calls_parallel(calls, {})

        assert len(results) == 1
        assert results[0][1] == "result"


class TestUpdateOpenedFilesCache:
    def test_caches_read_file(self):
        state = LoopState()
        update_opened_files_cache(
            state, "read_file", '{"path": "/tmp/a.py"}', "file content",
        )
        assert "/tmp/a.py" in state.opened_files
        assert state.opened_files["/tmp/a.py"].content == "file content"

    def test_caches_create_file_pinned(self):
        state = LoopState()
        update_opened_files_cache(
            state, "create_file",
            '{"path": "/tmp/new.py", "content": "new code"}',
            "ok",
        )
        assert "/tmp/new.py" in state.opened_files
        assert state.opened_files["/tmp/new.py"].pinned is True

    def test_caches_edit_file_pinned(self, tmp_path):
        # Create a real file so _safe_read_file works
        f = tmp_path / "edited.py"
        f.write_text("after edit content")

        state = LoopState()
        update_opened_files_cache(
            state, "edit_file",
            json.dumps({"path": str(f)}),
            "ok",
        )
        assert str(f) in state.opened_files
        assert state.opened_files[str(f)].pinned is True

    def test_does_not_cache_error_result(self):
        state = LoopState()
        update_opened_files_cache(
            state, "read_file",
            '{"path": "/tmp/x.py"}',
            '{"error": "file not found"}',
        )
        assert "/tmp/x.py" not in state.opened_files


class TestCapturePreContent:
    def test_reads_file_before_mutation(self, tmp_path):
        f = tmp_path / "target.py"
        f.write_text("original content")

        tracker = FileChangeTracker()
        pre = capture_pre_content("edit_file", {"path": str(f)}, tracker)
        assert pre == "original content"

    def test_returns_none_for_non_file_tools(self):
        tracker = FileChangeTracker()
        result = capture_pre_content("read_file", {"path": "/tmp/a.py"}, tracker)
        assert result is None

    def test_returns_none_for_new_file(self, tmp_path):
        tracker = FileChangeTracker()
        result = capture_pre_content(
            "create_file",
            {"path": str(tmp_path / "nonexistent.py")},
            tracker,
        )
        assert result is None

    def test_returns_none_when_inactive(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("content")

        tracker = FileChangeTracker()
        tracker.deactivate()
        result = capture_pre_content("edit_file", {"path": str(f)}, tracker)
        assert result is None


class TestToolSets:
    def test_file_change_tools_contains_expected(self):
        expected = {"edit_file", "create_file", "replace_lines", "edit_symbol", "add_symbol", "remove_symbol"}
        assert expected.issubset(FILE_CHANGE_TOOLS)

    def test_write_tools_superset_of_file_change_tools(self):
        assert FILE_CHANGE_TOOLS.issubset(WRITE_TOOLS)

    def test_write_tools_contains_git_and_command(self):
        assert "git_commit" in WRITE_TOOLS
        assert "execute_command" in WRITE_TOOLS
