"""Retained project record queries and operational labels, independent of retired flow classes."""

from __future__ import annotations

from backend.project_records import load_project_state, update_project_status


class TestMainProjectFlowHelpers:
    """Preserve project metadata and counts while their former executable-flow consumers are removed."""

    def test_load_project_state_existing(self, db_conn, sample_project):
        state = load_project_state(sample_project)
        assert state is not None
        assert state["name"] == "Test Project"
        assert state["status"] == "new"
        assert state["total_tasks"] == 0

    def test_load_project_state_nonexistent(self, db_conn):
        state = load_project_state(99999)
        assert state is None

    def test_load_project_with_task_counts(self, db_conn, executing_project):
        state = load_project_state(executing_project)
        assert state is not None
        assert state["status"] == "executing"
        assert state["total_tasks"] == 4
        assert state["task_counts"]["pending"] == 2
        assert state["task_counts"]["backlog"] == 1
        assert state["task_counts"]["in_progress"] == 1

    def test_update_project_status(self, db_conn, sample_project):
        update_project_status(sample_project, "planning")
        row = db_conn.execute(
            "SELECT status FROM projects WHERE id = ?", (sample_project,)
        ).fetchone()
        assert row["status"] == "planning"




