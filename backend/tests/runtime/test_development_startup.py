"""Normal startup upgrades development storage without enabling development execution."""

import sqlite3
from pathlib import Path

import pytest


def version35(database, conn, monkeypatch):
    """Build a historical database through the actual migrator while withholding only the new resources."""
    from backend.db import migrations
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource
    with monkeypatch.context() as patch:
        patch.setattr(
            migrations,
            "apply_sql_resource",
            lambda conn, path: (
                None
                if path.name
                in ("development_schema.sql", "development_workspace_schema.sql")
                else apply(conn, path)
            ),
        )
        ensure_migrations(database)
    assert (
        conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 35
    )


def test_repeatable_upgrade_preserves_original_research_and_owner_data(
    _isolated_db, db_conn, monkeypatch
):
    """Upgrade actual historical rows and child references without inventing preparation evidence."""
    from backend.tools.base.db import ensure_migrations

    version35(_isolated_db, db_conn, monkeypatch)
    db_conn.executescript("""INSERT INTO projects(id,name) VALUES(101,'History');
      INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Original','in_progress');
      INSERT INTO runtime_runs(rowid,id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,fence,current_attempt_id,created_at,updated_at)
      VALUES(73,'old',101,1001,'researcher',1,'old','Original request','codex','reconciling',1,'old-attempt',1,1);
      INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES('old-attempt','old','original',1,'reconciling',10,1);
      CREATE TABLE owner_notes(body TEXT);INSERT INTO owner_notes VALUES('Keep this');
      CREATE INDEX owner_actor_index ON runtime_runs(actor_id);
      CREATE VIEW owner_run_view AS SELECT id,actor_id FROM runtime_runs;""")
    before = dict(db_conn.execute("SELECT rowid,* FROM runtime_runs").fetchone())
    attempts = db_conn.execute("SELECT * FROM runtime_attempts").fetchall()
    ensure_migrations(_isolated_db)
    ensure_migrations(_isolated_db)
    assert (
        dict(db_conn.execute("SELECT rowid,* FROM runtime_runs").fetchone()) == before
    )
    assert db_conn.execute("SELECT * FROM runtime_attempts").fetchall() == attempts
    assert db_conn.execute("SELECT body FROM owner_notes").fetchone()[0] == "Keep this"
    assert db_conn.execute("SELECT id FROM owner_run_view").fetchone()[0] == "old"
    assert (
        db_conn.execute(
            "SELECT count(*) FROM runtime_development_workspaces"
        ).fetchone()[0]
        == 0
    )
    assert (
        db_conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
        == 37
    )
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "resource,marker",
    [("development_schema.sql", 36), ("development_workspace_schema.sql", 37)],
)
def test_failed_upgrade_leaves_only_committed_prior_migrations(
    _isolated_db, db_conn, monkeypatch, resource, marker
):
    """An invalid new SQL tail cannot publish a partial index, column, table or migration marker."""
    from backend.tools.base.db import ensure_migrations

    version35(_isolated_db, db_conn, monkeypatch)
    read = Path.read_text
    with monkeypatch.context() as patch:
        patch.setattr(
            Path,
            "read_text",
            lambda path, *args, **kwargs: (
                read(path, *args, **kwargs)
                + ("\nINVALID SQL;\n" if path.name == resource else "")
            ),
        )
        with pytest.raises(sqlite3.OperationalError):
            ensure_migrations(_isolated_db)
    assert (
        db_conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=?", (marker,)
        ).fetchone()
        is None
    )
    assert db_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='idx_runtime_active_task'"
    ).fetchone()
    assert "next_execution_kind" not in {
        row[1] for row in db_conn.execute("PRAGMA table_info(runtime_runs)")
    }
    assert (
        db_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='runtime_development_workspaces'"
        ).fetchone()
        is None
    )
    ensure_migrations(_isolated_db)
    assert (
        db_conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
        == 37
    )
