"""Verify the 'failed' status works end-to-end via update_task_status."""

import sqlite3

import pytest

from backend.flows.helpers import update_task_status, update_task_status_safe, get_task_by_id
from backend.tools.base.db import _migrate_7_add_failed_status, get_connection


class TestFailedStatus:
    """Verify failed transitions work through db_helpers."""

    def test_in_progress_to_failed(self, db_conn, executing_project):
        """Task 4 starts as in_progress — transition to failed should succeed."""
        update_task_status(4, "failed")
        task = get_task_by_id(4)
        assert task["status"] == "failed"
        assert task["completed_at"] is not None

    def test_failed_to_pending_retry(self, db_conn, executing_project):
        """Failed tasks can be retried by moving back to pending."""
        update_task_status(4, "failed")
        update_task_status(4, "pending")
        task = get_task_by_id(4)
        assert task["status"] == "pending"

    def test_backlog_to_done_rejected(self, db_conn, executing_project):
        """Skipping states is now properly rejected."""
        with pytest.raises(ValueError, match="Invalid transition"):
            update_task_status(3, "done")  # task 3 is backlog

    def test_backlog_to_failed_rejected(self, db_conn, executing_project):
        """Backlog tasks cannot directly fail (no work has started)."""
        with pytest.raises(ValueError, match="Invalid transition"):
            update_task_status(3, "failed")  # task 3 is backlog

    def test_pending_to_failed(self, db_conn, executing_project):
        """Pending tasks can fail (e.g., dependency resolution failure)."""
        update_task_status(2, "failed")  # task 2 is pending
        task = get_task_by_id(2)
        assert task["status"] == "failed"

    def test_update_task_status_safe_swallows_errors(self, db_conn, executing_project):
        """update_task_status_safe should not raise on invalid transitions."""
        update_task_status_safe(3, "done")  # backlog → done is invalid
        task = get_task_by_id(3)
        assert task["status"] == "backlog"  # unchanged

    def test_noop_same_status(self, db_conn, executing_project):
        """Setting a task to its current status is a no-op."""
        update_task_status(2, "pending")  # task 2 already pending
        task = get_task_by_id(2)
        assert task["status"] == "pending"


# SQL for a DB created *before* migration 7 (no 'failed' in CHECK).
_OLD_TASKS_SQL = """
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    epic_id INTEGER, milestone_id INTEGER, parent_task_id INTEGER,
    type TEXT NOT NULL CHECK(type IN (
        'plan','research','code','review','test',
        'design','integrate','documentation','bug_fix')),
    status TEXT NOT NULL DEFAULT 'backlog' CHECK(status IN (
        'backlog','pending','in_progress',
        'review_ready','rejected','done','cancelled')),
    title TEXT NOT NULL, description TEXT, acceptance_criteria TEXT,
    context_json TEXT, priority INTEGER DEFAULT 2,
    estimated_complexity TEXT DEFAULT 'medium',
    branch_name TEXT, assigned_to TEXT, reviewer TEXT,
    created_by TEXT NOT NULL DEFAULT 'orchestrator',
    retry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE TABLE events_log (
    id INTEGER PRIMARY KEY, project_id INTEGER,
    event_type TEXT NOT NULL, event_source TEXT NOT NULL,
    entity_type TEXT, entity_id INTEGER,
    event_data_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    title, description, acceptance_criteria,
    content=tasks, content_rowid=id);
"""


@pytest.fixture()
def old_db(tmp_path):
    """Create a DB with the old schema (no 'failed' in CHECK)."""
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT);\n"
        "CREATE TABLE epics (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id),"
        " title TEXT NOT NULL, description TEXT, status TEXT DEFAULT 'open');\n"
        "CREATE TABLE milestones (id INTEGER PRIMARY KEY, project_id INTEGER,"
        " epic_id INTEGER, title TEXT, status TEXT DEFAULT 'open');\n"
        + _OLD_TASKS_SQL
        + "\nINSERT INTO projects(id, name) VALUES (1, 'Test');"
        "\nINSERT INTO tasks(id, project_id, type, title, status, created_by)"
        " VALUES (1, 1, 'code', 'Existing task', 'in_progress', 'test');"
    )
    conn.close()
    return db_path


class TestMigration7:
    """Verify _migrate_7_add_failed_status rebuilds the table correctly."""

    def test_old_schema_rejects_failed(self, old_db):
        conn = sqlite3.connect(old_db)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE tasks SET status = 'failed' WHERE id = 1")
        conn.close()

    def test_migration_allows_failed(self, old_db):
        conn = get_connection(old_db)
        _migrate_7_add_failed_status(conn)
        conn.commit()
        conn.execute("UPDATE tasks SET status = 'failed' WHERE id = 1")
        conn.commit()
        row = conn.execute("SELECT status FROM tasks WHERE id = 1").fetchone()
        assert row["status"] == "failed"
        conn.close()

    def test_migration_preserves_data(self, old_db):
        conn = get_connection(old_db)
        _migrate_7_add_failed_status(conn)
        conn.commit()
        row = conn.execute(
            "SELECT title, type, status FROM tasks WHERE id = 1"
        ).fetchone()
        assert row["title"] == "Existing task"
        assert row["type"] == "code"
        conn.close()

    def test_migration_is_idempotent(self, old_db):
        conn = get_connection(old_db)
        _migrate_7_add_failed_status(conn)
        conn.commit()
        conn.close()
        # Run again — should be a no-op
        conn = get_connection(old_db)
        _migrate_7_add_failed_status(conn)
        conn.commit()
        row = conn.execute("SELECT title FROM tasks WHERE id = 1").fetchone()
        assert row["title"] == "Existing task"
        conn.close()

    def test_migration_recreates_indexes(self, old_db):
        conn = get_connection(old_db)
        _migrate_7_add_failed_status(conn)
        conn.commit()
        indexes = {
            row[1]
            for row in conn.execute(
                "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='tasks'"
            ).fetchall()
        }
        assert "idx_tasks_status" in indexes
        conn.close()
