"""Old queued receipts remain history; migration never invents their workspace."""

import json
from dataclasses import asdict


def test_version27_receipt_survives_without_an_inferred_binding(
    _isolated_db, db_conn, monkeypatch
):
    """A version27 receipt stays historical after upgrades without inventing admission evidence."""
    from backend.db import migrations, peer_kind_migration, wiki_migration
    from backend.runtime.contracts import RunSpec
    from backend.runtime.sqlite_runs import SQLiteRunStore, _digest
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
                    "admission_schema.sql",
                    "task_inputs_schema.sql",
                    "run_input_schema.sql",
                    "native_state_schema.sql",
                    "review_schema.sql",
                    "result_schema.sql",
                    "development_schema.sql",
                    "development_workspace_schema.sql",
                    "code_candidate_schema.sql",
                )
                else apply(conn, path)
            ),
        )
        ensure_migrations(_isolated_db)
    assert (
        db_conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        == 27
    )
    spec = RunSpec(101, 1001, "owner", 1, "request", "Old", "codex")
    db_conn.executescript("""
      INSERT INTO projects(id,name) VALUES(101,'Historical');
      INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Old');
      INSERT INTO runtime_runs(rowid,id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at)
      VALUES(73,'old',101,1001,'owner',1,'request','Old','codex','queued',1,1);
    """)
    db_conn.execute(
        "INSERT INTO runtime_commands(project_id,task_id,operation_key,request_hash,result_json,created_at) VALUES(101,1001,?,?,?,1)",
        (
            spec.operation_key,
            _digest({"kind": "admit", **asdict(spec)}),
            json.dumps({"run_id": "old"}),
        ),
    )
    db_conn.commit()
    columns = [r[1] for r in db_conn.execute("PRAGMA table_info(runtime_runs)")]
    query = "SELECT rowid," + ",".join(columns) + " FROM runtime_runs"
    before = db_conn.execute(query).fetchall()
    ensure_migrations(_isolated_db)
    ensure_migrations(_isolated_db)
    assert db_conn.execute(query).fetchall() == before
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []
    store = SQLiteRunStore(_isolated_db)
    old = store.admission_receipt(spec, repository_id=11)
    assert old.run_id == "old" and old.repository_id is None and old.issue is None
    assert store.workspace_binding(101, "old") is None
    assert (
        db_conn.execute("SELECT COUNT(*) FROM runtime_workspace_bindings").fetchone()[0]
        == 0
    )
