"""Retain the historical failed-status database migration checks after legacy state-mutator removal."""

import sqlite3

import pytest

from backend.tools.base.db import _migrate_7_add_failed_status, get_connection




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
