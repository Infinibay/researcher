"""Tests for DevelopmentFlow."""

from __future__ import annotations

import pytest

from backend.flows.helpers import (
    check_task_dependencies,
    get_task_by_id,
)
from backend.flows.helpers.db_helpers import promote_unblocked_dependents
from backend.flows.state_models import DevelopmentState, ReviewStatus


class TestDevelopmentFlowHelpers:
    """Test helper functions used by DevelopmentFlow."""

    def test_get_task_by_id(self, db_conn, executing_project):
        task = get_task_by_id(1)
        assert task is not None
        assert task["title"] == "Implement feature A"
        assert task["type"] == "code"

    def test_get_task_by_id_nonexistent(self, db_conn):
        task = get_task_by_id(99999)
        assert task is None

    def test_check_dependencies_no_deps(self, db_conn, executing_project):
        result = check_task_dependencies(1)
        assert result is True

    def test_check_dependencies_with_blocking(self, db_conn, executing_project):
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.commit()
        result = check_task_dependencies(3)
        assert result is False

    def test_check_dependencies_resolved(self, db_conn, executing_project):
        db_conn.execute(
            """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
               VALUES (3, 1, 'blocks')"""
        )
        db_conn.commit()
        # Existing completed dependency is historical data, not a new approval.
        db_conn.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(99,?,'code','Historic completed dependency','done')", (executing_project,))
        db_conn.execute("UPDATE task_dependencies SET depends_on_task_id=99 WHERE task_id=3")
        db_conn.commit()
        result = check_task_dependencies(3)
        assert result is True


class TestDevelopmentState:
    """Test DevelopmentState model."""

    def test_default_state(self):
        state = DevelopmentState()
        assert state.task_id == 0
        assert state.branch_name == ""
        assert state.review_status == ReviewStatus.PENDING

    def test_state_with_values(self):
        state = DevelopmentState(
            project_id=1,
            task_id=42,
            branch_name="task-42-feature",
            developer_id="dev_p1",
        )
        assert state.task_id == 42
        assert state.branch_name == "task-42-feature"

    def test_no_checkin_fields(self):
        """Verify checkin_thread_id and checkin_approved were removed."""
        state = DevelopmentState()
        assert not hasattr(state, "checkin_thread_id")
        assert not hasattr(state, "checkin_approved")


class TestHistoricalDependencyPromotion:
    """Promotion can inspect historical completion but cannot create completion proof."""

    @pytest.mark.parametrize("other_pending", [False, True])
    def test_historical_dependency_promotion(self, db_conn, executing_project, other_pending):
        """All historical prerequisites must be done; promotion only makes work pending and is idempotent."""
        db_conn.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(99,?,'code','Historical completed task','done')", (executing_project,))
        db_conn.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(3,99,'blocks')")
        if other_pending:
            db_conn.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(3,2,'blocks')")
        db_conn.commit()
        promote_unblocked_dependents(99)
        assert db_conn.execute("SELECT status FROM tasks WHERE id=3").fetchone()[0] == ("backlog" if other_pending else "pending")
        assert promote_unblocked_dependents(99) == []
