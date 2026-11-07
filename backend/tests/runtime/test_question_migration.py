"""Rebuild the run-state constraint without losing children or user schema objects."""

import sqlite3
from pathlib import Path

import pytest


def version23(database, conn, monkeypatch):
    """Build a version23 fixture without newer rebuilds changing the migration under test."""
    from backend.db import (
        migrations,
        peer_kind_migration,
        question_migration,
        wiki_migration,
    )
    from backend.tools.base.db import ensure_migrations

    conn.execute("PRAGMA foreign_keys=ON")
    ensure_migrations(database, target_version=23)
    assert (
        conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 23
    )
    conn.execute("INSERT INTO projects(id,name) VALUES(101,'Preserved')")
    conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Original','in_progress')"
    )
    conn.execute("""INSERT INTO runtime_runs(rowid,id,project_id,task_id,actor_id,context_version,
        operation_key,prompt,runtime,status,fence,current_attempt_id,created_at,updated_at)
        VALUES(73,'old-run',101,1001,'researcher',1,'request','Original request','codex','running',1,'old-attempt',10,20)""")
    conn.execute("""INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at)
        VALUES('old-attempt','old-run','old-owner',1,'running',1000,10)""")
    conn.execute("CREATE TABLE owner_audit(run_id TEXT)")
    conn.execute(
        "CREATE TRIGGER owner_trigger AFTER UPDATE ON runtime_runs BEGIN INSERT INTO owner_audit VALUES(new.id); END"
    )
    conn.execute("CREATE INDEX owner_actor_index ON runtime_runs(actor_id)")
    conn.execute("CREATE VIEW owner_run_view AS SELECT id,actor_id FROM runtime_runs")
    conn.commit()


def test_waiting_migration_preserves_children_rowids_custom_objects_and_uniqueness(
    _isolated_db, db_conn, monkeypatch
):
    from backend.db.question_migration import apply_question_schema

    version23(_isolated_db, db_conn, monkeypatch)
    before = db_conn.execute("SELECT * FROM runtime_attempts").fetchall()
    apply_question_schema(db_conn)
    assert db_conn.execute("SELECT * FROM runtime_attempts").fetchall() == before
    assert db_conn.execute("SELECT rowid FROM runtime_runs").fetchone()[0] == 73
    assert db_conn.execute("SELECT * FROM owner_run_view").fetchone()[0] == "old-run"
    assert db_conn.execute(
        "SELECT name FROM sqlite_master WHERE name='owner_actor_index'"
    ).fetchone()
    db_conn.execute("UPDATE runtime_runs SET status='waiting_input' WHERE id='old-run'")
    db_conn.commit()
    assert (
        db_conn.execute("SELECT run_id FROM owner_audit").fetchall()[0][0] == "old-run"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute("""INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,
            prompt,runtime,status,created_at,updated_at) VALUES('duplicate',101,1001,'researcher',1,'second','Other','codex','queued',20,20)""")
    db_conn.rollback()
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db_conn.execute("PRAGMA legacy_alter_table").fetchone()[0] == 0


def test_failed_waiting_rebuild_rolls_back_table_children_objects_and_marker(
    _isolated_db, db_conn, monkeypatch
):
    from backend.db.question_migration import apply_question_schema

    version23(_isolated_db, db_conn, monkeypatch)
    original = Path.read_text

    def corrupt(path, *args, **kwargs):
        data = original(path, *args, **kwargs)
        if path.name == "question_schema.sql":
            data += "\nINSERT INTO injected_migration_failure VALUES(1);\n"
        return data

    monkeypatch.setattr(Path, "read_text", corrupt)
    with pytest.raises(sqlite3.OperationalError, match="injected_migration_failure"):
        apply_question_schema(db_conn)
    assert db_conn.execute("SELECT id FROM runtime_runs").fetchone()[0] == "old-run"
    assert (
        db_conn.execute("SELECT id FROM runtime_attempts").fetchone()[0]
        == "old-attempt"
    )
    assert db_conn.execute("SELECT id FROM owner_run_view").fetchone()[0] == "old-run"
    assert (
        db_conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        == 23
    )
    assert db_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db_conn.execute("PRAGMA legacy_alter_table").fetchone()[0] == 0
    assert not db_conn.in_transaction
    assert (
        db_conn.execute(
            "SELECT name FROM sqlite_master WHERE name='runtime_runs_v24'"
        ).fetchone()
        is None
    )


def test_waiting_migration_refuses_an_existing_transaction(
    _isolated_db, db_conn, monkeypatch
):
    from backend.db.question_migration import apply_question_schema

    version23(_isolated_db, db_conn, monkeypatch)
    db_conn.execute("INSERT INTO owner_audit VALUES('uncommitted')")
    with pytest.raises(RuntimeError, match="transaction"):
        apply_question_schema(db_conn)
    assert db_conn.in_transaction
    db_conn.rollback()
    assert db_conn.execute("SELECT COUNT(*) FROM owner_audit").fetchone()[0] == 0
