"""Version 29 observes future edits without inventing historical task evidence."""

import sqlite3
from pathlib import Path

import pytest


def test_version28_migration_preserves_rows_and_only_records_future_edits(
    _isolated_db, db_conn, monkeypatch
):
    """Preserve version28 rows and record only future edits after upgrading."""
    from backend.db import migrations, peer_kind_migration, wiki_migration
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource
    with monkeypatch.context() as patch:
        patch.setattr(peer_kind_migration, "migrate_ken_peers", lambda _conn: None)
        patch.setattr(wiki_migration, "apply_wiki_schema", lambda _conn: None)
        patch.setattr(
            migrations,
            "apply_sql_resource",
            lambda conn, path: (
                None
                if path.name
                in (
                    "task_inputs_schema.sql",
                    "run_input_schema.sql",
                    "native_state_schema.sql",
                    "review_schema.sql",
                    "result_schema.sql",
                    "development_schema.sql",
                    "development_workspace_schema.sql",
                    "code_candidate_schema.sql",
                    "code_check_schema.sql",
                    "code_review_schema.sql",
                    "code_review_record_schema.sql",
                    "code_acceptance_schema.sql",
                )
                else apply(conn, path)
            ),
        )
        ensure_migrations(_isolated_db)
    assert (
        db_conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        == 28
    )
    db_conn.executescript("""
      INSERT INTO projects(id,name) VALUES(101,'History');
      INSERT INTO tasks(rowid,id,project_id,type,title,description) VALUES(73,73,101,'research','Original','Earlier input');
      INSERT INTO task_contexts(task_id,version) VALUES(73,7);
    """)
    before = db_conn.execute("SELECT rowid,* FROM tasks").fetchall()
    ensure_migrations(_isolated_db)
    ensure_migrations(_isolated_db)
    assert db_conn.execute("SELECT rowid,* FROM tasks").fetchall() == before
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []
    store = SQLiteRunStore(_isolated_db)
    snapshot = store.context_snapshot(101, 73)
    assert snapshot["context_version"] == 7 and snapshot["task_changes"] == []
    db_conn.execute("UPDATE tasks SET description='New input' WHERE id=73")
    db_conn.commit()
    snapshot = store.context_snapshot(101, 73)
    assert snapshot["context_version"] == 8
    assert snapshot["task_changes"][0]["changes"] == {
        "description": {"before": "Earlier input", "after": "New input"}
    }
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db_conn.execute("UPDATE runtime_task_input_changes SET after_json='{}'")
    db_conn.rollback()


def test_task_input_migration_failure_rolls_back_trigger_and_marker(
    _isolated_db, db_conn, monkeypatch
):
    from backend.tools.base.db import ensure_migrations

    read = Path.read_text
    with monkeypatch.context() as patch:
        patch.setattr(
            Path,
            "read_text",
            lambda path, *args, **kwargs: (
                read(path, *args, **kwargs) + "\nINVALID SQL;\n"
                if path.name == "task_inputs_schema.sql"
                else read(path, *args, **kwargs)
            ),
        )
        with pytest.raises(sqlite3.OperationalError):
            ensure_migrations(_isolated_db)
    assert (
        db_conn.execute(
            "SELECT name FROM sqlite_master WHERE name IN ('version_task_inputs','runtime_task_input_changes')"
        ).fetchall()
        == []
    )
    assert (
        db_conn.execute(
            "SELECT version FROM schema_migrations WHERE version=29"
        ).fetchall()
        == []
    )
    ensure_migrations(_isolated_db)
    assert (
        db_conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=29"
        ).fetchone()[0]
        == 1
    )
