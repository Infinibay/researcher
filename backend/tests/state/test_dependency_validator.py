"""Tests for DependencyValidator in backend/state/dependency_validator.py."""

import pytest

from backend.state.dependency_validator import DependencyValidator


@pytest.fixture()
def seeded_tasks(db_conn):
    """Insert a project and tasks for dependency testing."""
    db_conn.execute(
        """INSERT INTO projects (id, name, description, status, created_at)
           VALUES (1, 'Test', 'test', 'executing', CURRENT_TIMESTAMP)"""
    )
    # Task A (id=1) — done
    db_conn.execute(
        """INSERT INTO tasks (id, project_id, title, type, status, priority, created_at)
           VALUES (1, 1, 'Task A', 'code', 'done', 1, CURRENT_TIMESTAMP)"""
    )
    # Task B (id=2) — in_progress
    db_conn.execute(
        """INSERT INTO tasks (id, project_id, title, type, status, priority, created_at)
           VALUES (2, 1, 'Task B', 'code', 'in_progress', 2, CURRENT_TIMESTAMP)"""
    )
    # Task C (id=3) — pending, depends on A and B
    db_conn.execute(
        """INSERT INTO tasks (id, project_id, title, type, status, priority, created_at)
           VALUES (3, 1, 'Task C', 'code', 'pending', 3, CURRENT_TIMESTAMP)"""
    )
    # Task D (id=4) — no dependencies
    db_conn.execute(
        """INSERT INTO tasks (id, project_id, title, type, status, priority, created_at)
           VALUES (4, 1, 'Task D', 'code', 'pending', 4, CURRENT_TIMESTAMP)"""
    )

    # Dependencies: C blocks on A and B
    db_conn.execute(
        """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
           VALUES (3, 1, 'blocks')"""
    )
    db_conn.execute(
        """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
           VALUES (3, 2, 'blocks')"""
    )
    db_conn.commit()
    return {"A": 1, "B": 2, "C": 3, "D": 4}


class TestCanStart:
    def test_can_start_no_deps(self, seeded_tasks):
        assert DependencyValidator.can_start(seeded_tasks["D"]) is True

    def test_can_start_blocking_dep_not_done(self, seeded_tasks):
        # C depends on B which is in_progress
        assert DependencyValidator.can_start(seeded_tasks["C"]) is False

    def test_can_start_blocking_dep_done(self, db_conn, seeded_tasks):
        # Mark B as done so all of C's deps are done
        db_conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (seeded_tasks["B"],))
        db_conn.commit()
        assert DependencyValidator.can_start(seeded_tasks["C"]) is True


class TestGetUnmetDependencies:
    def test_get_unmet_dependencies_empty(self, seeded_tasks):
        result = DependencyValidator.get_unmet_dependencies(seeded_tasks["D"])
        assert result == []

    def test_get_unmet_dependencies_returns_blockers(self, seeded_tasks):
        result = DependencyValidator.get_unmet_dependencies(seeded_tasks["C"])
        assert len(result) == 1  # Only B is not done (A is done)
        assert result[0]["id"] == seeded_tasks["B"]
        assert result[0]["title"] == "Task B"
        assert result[0]["status"] == "in_progress"
