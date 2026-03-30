"""Tests for backend.engine.file_change_tracker.FileChangeTracker."""

import os

import pytest

from backend.engine.file_change_tracker import FileChangeTracker


@pytest.fixture
def tracker():
    return FileChangeTracker()


class TestRecord:
    def test_tracks_original_and_current(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record(path, "original", "modified")

        abs_path = os.path.abspath(path)
        assert tracker._originals[abs_path] == "original"
        assert tracker._current[abs_path] == "modified"

    def test_new_file_original_is_empty(self, tracker, tmp_path):
        path = str(tmp_path / "new.py")
        tracker.record(path, None, "new content")

        abs_path = os.path.abspath(path)
        assert tracker._originals[abs_path] == ""

    def test_multiple_edits_preserve_original(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record(path, "v1", "v2")
        tracker.record(path, "v2", "v3")

        abs_path = os.path.abspath(path)
        assert tracker._originals[abs_path] == "v1"  # first original preserved
        assert tracker._current[abs_path] == "v3"    # latest current

    def test_returns_diff(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        diff = tracker.record(path, "line1\nline2", "line1\nline3")
        assert diff is not None
        assert "line2" in diff
        assert "line3" in diff

    def test_inactive_returns_none(self, tracker, tmp_path):
        tracker.deactivate()
        result = tracker.record(str(tmp_path / "a.py"), "a", "b")
        assert result is None


class TestGetDiff:
    def test_generates_unified_diff(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record(path, "hello\nworld", "hello\nearth")
        diff = tracker.get_diff(path)
        assert diff is not None
        assert "---" in diff
        assert "+++" in diff
        assert "-world" in diff
        assert "+earth" in diff

    def test_returns_none_for_untracked(self, tracker):
        assert tracker.get_diff("/nonexistent/path.py") is None

    def test_returns_none_when_no_change(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record(path, "same", "same")
        assert tracker.get_diff(path) is None


class TestGetChangeCount:
    def test_increments(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        assert tracker.get_change_count(path) == 0
        tracker.record(path, "a", "b")
        assert tracker.get_change_count(path) == 1
        tracker.record(path, "b", "c")
        assert tracker.get_change_count(path) == 2


class TestGetAction:
    def test_created_when_original_empty(self, tracker, tmp_path):
        path = str(tmp_path / "new.py")
        tracker.record(path, None, "content")
        assert tracker.get_action(path) == "created"

    def test_modified_when_original_nonempty(self, tracker, tmp_path):
        path = str(tmp_path / "existing.py")
        tracker.record(path, "old content", "new content")
        assert tracker.get_action(path) == "modified"


class TestRecordReason:
    def test_records_and_retrieves(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record_reason(path, "Fixed the bug")
        tracker.record_reason(path, "Added error handling")
        reasons = tracker.get_reasons(path)
        assert reasons == ["Fixed the bug", "Added error handling"]

    def test_empty_for_untracked(self, tracker):
        assert tracker.get_reasons("/nonexistent.py") == []

    def test_blank_reason_ignored(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record_reason(path, "")
        tracker.record_reason(path, "   ")
        assert tracker.get_reasons(path) == []


class TestDeactivate:
    def test_stops_recording(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record(path, "a", "b")
        tracker.deactivate()
        assert tracker.active is False
        result = tracker.record(str(tmp_path / "c.py"), "x", "y")
        assert result is None
        # Only the first file was tracked
        assert len(tracker.get_all_paths()) == 1


class TestReset:
    def test_clears_all_state(self, tracker, tmp_path):
        path = str(tmp_path / "a.py")
        tracker.record(path, "a", "b")
        tracker.record_reason(path, "reason")
        tracker.deactivate()

        tracker.reset()

        assert tracker.active is True
        assert tracker.get_all_paths() == []
        assert tracker.get_change_count(path) == 0
        assert tracker.get_reasons(path) == []
