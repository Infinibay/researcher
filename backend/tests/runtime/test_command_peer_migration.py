"""Version 26 command history is preserved; ownership is never inferred."""

import sqlite3

import pytest


def test_migration_preserves_unowned_history_and_refuses_retrospective_binding(
    _isolated_db, db_conn, monkeypatch
):
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
                in (
                    "command_peer_schema.sql",
                    "admission_schema.sql",
                    "task_inputs_schema.sql",
                    "run_input_schema.sql",
                )
                else apply(conn, path)
            ),
        )
        ensure_migrations(_isolated_db)
    db_conn.executescript("""
        INSERT INTO projects(id,name) VALUES(101,'Historical');
        INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Old');
        INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,fence,current_attempt_id,created_at,updated_at)
        VALUES('r',101,1001,'owner',1,'old','Old','codex','reconciling',2,'a',1,1);
        INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES('a','r','old',1,'reconciling',1,1);
        INSERT INTO runtime_jobs(rowid,id,run_id,attempt_id,executor_id,operation_key,request_hash,argv_json,cwd,workspace,timeout_seconds,output_bytes,status,stdout,created_at)
        VALUES(73,'j','r','a','old','old','old','["/bin/false"]','.','/old',2,100,'unknown',X'006162',1);
    """)
    columns = [row[1] for row in db_conn.execute("PRAGMA table_info(runtime_jobs)")]
    select = "SELECT rowid," + ",".join(columns) + " FROM runtime_jobs"
    before = db_conn.execute(select).fetchall()
    ensure_migrations(_isolated_db)
    ensure_migrations(_isolated_db)
    assert db_conn.execute(select).fetchall() == before
    assert db_conn.execute("SELECT peer_id FROM runtime_jobs").fetchone()[0] is None
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db_conn.execute("UPDATE runtime_jobs SET peer_id='invented' WHERE id='j'")
