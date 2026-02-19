"""Tests for CompletionDetector in backend/state/completion.py."""

from unittest.mock import MagicMock

import pytest

from backend.state.completion import CompletionDetector, CompletionState


@pytest.fixture()
def project_with_epics(db_conn):
    """Insert a project with epics and return the project id."""
    db_conn.execute(
        """INSERT INTO projects (id, name, description, status, created_at)
           VALUES (1, 'Test', 'test', 'executing', CURRENT_TIMESTAMP)"""
    )
    db_conn.execute(
        """INSERT INTO epics (id, project_id, title, status, priority, created_at)
           VALUES (1, 1, 'Epic 1', 'open', 1, CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    return 1


class TestDetect:
    def test_active_when_dev_tasks_in_progress(self, db_conn, project_with_epics):
        db_conn.execute(
            """INSERT INTO tasks (project_id, title, type, status, priority, created_at)
               VALUES (1, 'Code task', 'code', 'in_progress', 1, CURRENT_TIMESTAMP)"""
        )
        db_conn.commit()

        result = CompletionDetector.detect(project_with_epics)
        assert result == CompletionState.ACTIVE

    def test_waiting_for_research_when_only_research_in_progress(self, db_conn, project_with_epics):
        db_conn.execute(
            """INSERT INTO tasks (project_id, title, type, status, priority, created_at)
               VALUES (1, 'Research task', 'research', 'in_progress', 1, CURRENT_TIMESTAMP)"""
        )
        db_conn.commit()

        result = CompletionDetector.detect(project_with_epics)
        assert result == CompletionState.WAITING_FOR_RESEARCH

    def test_idle_objectives_met_when_all_epics_completed(self, db_conn, project_with_epics):
        db_conn.execute("UPDATE epics SET status = 'completed' WHERE project_id = 1")
        db_conn.commit()

        result = CompletionDetector.detect(project_with_epics)
        assert result == CompletionState.IDLE_OBJECTIVES_MET

    def test_idle_objectives_pending_when_epics_open(self, db_conn, project_with_epics):
        # Epics are open, no tasks in progress
        result = CompletionDetector.detect(project_with_epics)
        assert result == CompletionState.IDLE_OBJECTIVES_PENDING


class TestNotifyUserIfIdle:
    def test_notify_called_for_idle_objectives_met(self, db_conn, project_with_epics):
        db_conn.execute("UPDATE epics SET status = 'completed' WHERE project_id = 1")
        db_conn.commit()

        notifier = MagicMock()
        CompletionDetector.notify_user_if_idle(project_with_epics, notifier)

        notifier.notify_user.assert_called_once()
        call_kwargs = notifier.notify_user.call_args
        assert call_kwargs.kwargs["project_id"] == project_with_epics
        assert "finalize" in call_kwargs.kwargs["message"].lower()

    def test_notify_called_for_idle_objectives_pending(self, db_conn, project_with_epics):
        notifier = MagicMock()
        CompletionDetector.notify_user_if_idle(project_with_epics, notifier)

        notifier.notify_user.assert_called_once()
        call_kwargs = notifier.notify_user.call_args
        assert "brainstorming" in call_kwargs.kwargs["message"].lower()

    def test_notify_called_for_waiting_for_research(self, db_conn, project_with_epics):
        db_conn.execute(
            """INSERT INTO tasks (project_id, title, type, status, priority, created_at)
               VALUES (1, 'Research task', 'research', 'in_progress', 1, CURRENT_TIMESTAMP)"""
        )
        db_conn.commit()

        notifier = MagicMock()
        CompletionDetector.notify_user_if_idle(project_with_epics, notifier)

        notifier.notify_user.assert_called_once()
        call_kwargs = notifier.notify_user.call_args
        assert "research" in call_kwargs.kwargs["message"].lower()

    def test_notify_not_called_when_active(self, db_conn, project_with_epics):
        db_conn.execute(
            """INSERT INTO tasks (project_id, title, type, status, priority, created_at)
               VALUES (1, 'Code task', 'code', 'in_progress', 1, CURRENT_TIMESTAMP)"""
        )
        db_conn.commit()

        notifier = MagicMock()
        CompletionDetector.notify_user_if_idle(project_with_epics, notifier)

        notifier.notify_user.assert_not_called()
