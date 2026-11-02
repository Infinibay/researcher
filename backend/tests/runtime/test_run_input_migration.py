"""New input evidence never rewrites an old dispatch into a known one."""

import json
from dataclasses import asdict


def test_version29_dispatch_remains_unknown_after_repeatable_upgrade(
    _isolated_db, db_conn, monkeypatch
):
    """Retain unknown input on a version29 dispatch across repeatable upgrades."""
    from backend.db import migrations, peer_kind_migration, wiki_migration
    from backend.runtime.codex_session import ExecutionLimits
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
                if path.name in ("run_input_schema.sql", "native_state_schema.sql", "review_schema.sql", "result_schema.sql")
                else apply(conn, path)
            ),
        )
        ensure_migrations(_isolated_db)
    assert (
        db_conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        == 29
    )
    db_conn.executescript("""
      INSERT INTO projects(id,name) VALUES(101,'History');
      INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Earlier');
      INSERT INTO runtime_runs(rowid,id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,current_attempt_id,created_at,updated_at)
      VALUES(37,'old',101,1001,'researcher',1,'old','Original request','codex','reconciling','attempt-old',1,1);
      INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES('attempt-old','old','original',1,'reconciling',10,1);
    """)
    db_conn.execute(
        "INSERT INTO runtime_inference_dispatches(attempt_id,project_id,workspace,catalog_hash,runtime_version,limits_json,model,token_ceiling,status,created_at) VALUES('attempt-old',101,'/original',?,'old',?,'original-model',100,'unknown',1)",
        ("a" * 64, json.dumps(asdict(ExecutionLimits(60, 30, 1, 10, 100)))),
    )
    db_conn.commit()
    before = db_conn.execute(
        "SELECT rowid,* FROM runtime_inference_dispatches"
    ).fetchall()
    ensure_migrations(_isolated_db)
    ensure_migrations(_isolated_db)
    assert (
        db_conn.execute("SELECT rowid,* FROM runtime_inference_dispatches").fetchall()
        == before
    )
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []
    record = SQLiteRunStore(_isolated_db).input_record(101, "old")
    assert record == {
        "available": False,
        "attempt_id": "attempt-old",
        "reason": "no_record",
    }
    assert (
        db_conn.execute("SELECT COUNT(*) FROM runtime_input_snapshots").fetchone()[0]
        == 0
    )
