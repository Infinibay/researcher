"""Unused development storage can be reversed atomically; admitted work must survive."""

from pathlib import Path

import pytest

from backend.db.migrations import apply_sql_resource


@pytest.fixture
def expanded(coordination):
    """Use actual latest startup storage, then explicitly remove unused candidate storage to test the historical inverses."""
    assert (
        coordination.conn.execute(
            "SELECT max(version) FROM schema_migrations"
        ).fetchone()[0]
        == 42
    )
    from backend.db.development_migration import (
        restore_code_acceptances,
        restore_code_candidates,
        restore_code_checks,
        restore_code_reviews,
        restore_native_code_reviews,
    )

    restore_code_acceptances(coordination.conn)

    restore_native_code_reviews(coordination.conn)
    restore_code_reviews(coordination.conn)
    restore_code_checks(coordination.conn)
    restore_code_candidates(coordination.conn)
    return coordination


def test_unused_inverse_preserves_research_rows_children_and_owner_objects(expanded):
    """Downgrade keeps original identities and schema objects and can be reapplied without loss."""
    from backend.db.development_migration import (
        restore_development_kinds,
        restore_development_workspaces,
    )

    c = expanded
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "original")
    c.store.finish(lease, native_status="completed", summary="Historical research")
    c.conn.executescript("""CREATE TABLE owner_notes(body TEXT);
      INSERT INTO owner_notes VALUES('Keep this data');
      CREATE INDEX owner_actor_index ON runtime_runs(actor_id);
      CREATE VIEW owner_run_view AS SELECT id,actor_id FROM runtime_runs;""")
    before = dict(
        c.conn.execute(
            "SELECT rowid,* FROM runtime_runs WHERE id=?", (run.run_id,)
        ).fetchone()
    )
    attempts = [tuple(row) for row in c.conn.execute("SELECT * FROM runtime_attempts")]
    restore_development_workspaces(c.conn)
    restore_development_workspaces(c.conn)
    restore_development_kinds(c.conn)
    restore_development_kinds(c.conn)
    assert (
        dict(
            c.conn.execute(
                "SELECT rowid,* FROM runtime_runs WHERE id=?", (run.run_id,)
            ).fetchone()
        )
        == before
    )
    assert [
        tuple(row) for row in c.conn.execute("SELECT * FROM runtime_attempts")
    ] == attempts
    assert (
        c.conn.execute("SELECT body FROM owner_notes").fetchone()[0] == "Keep this data"
    )
    assert c.conn.execute("SELECT id FROM owner_run_view").fetchone()[0] == run.run_id
    assert c.conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='owner_actor_index'"
    ).fetchone()
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    for name in ("development_schema.sql", "development_workspace_schema.sql"):
        apply_sql_resource(c.conn, Path(__file__).resolve().parents[2] / "db" / name)
    assert c.store.get(101, run.run_id).execution_kind == "research"


@pytest.mark.parametrize(
    "obstacle",
    ["active_run", "future_version", "new_kind_history", "preparation_history"],
)
def test_workspace_inverse_refuses_authority_and_history_without_partial_deletion(
    expanded, obstacle
):
    """Even a closed or interrupted preparation is retained evidence, not disposable empty schema."""
    from backend.db.development_migration import restore_development_workspaces

    c = expanded
    if obstacle == "future_version":
        c.conn.execute(
            "INSERT INTO schema_migrations(version,name) VALUES(38,'future')"
        )
        c.conn.commit()
    else:
        run = c.store.admit(c.spec)
        if obstacle != "active_run":
            lease = c.store.claim(101, run.run_id, "original")
            c.store.finish(lease, native_status="completed", summary="Historical")
            if obstacle == "new_kind_history":
                c.conn.execute(
                    "UPDATE runtime_runs SET execution_kind='development' WHERE id=?",
                    (run.run_id,),
                )
            else:
                c.conn.execute(
                    """INSERT INTO runtime_development_workspaces
                (attempt_id,run_id,project_id,task_id,context_version,fence,owner_id,source_json,allocation,state,created_at,updated_at)
                VALUES(?,?,101,1001,1,1,'original','{}','/synthetic/retained','reconciling',1,1)""",
                    (lease.attempt_id, run.run_id),
                )
            c.conn.commit()
    before = [
        tuple(row)
        for row in c.conn.execute("SELECT * FROM runtime_development_workspaces")
    ]
    with pytest.raises(RuntimeError, match="rollback refused"):
        restore_development_workspaces(c.conn)
    assert [
        tuple(row)
        for row in c.conn.execute("SELECT * FROM runtime_development_workspaces")
    ] == before
    assert c.conn.execute("SELECT 1 FROM schema_migrations WHERE version=37").fetchone()


def test_kind_inverse_requires_later_storage_to_be_removed_first(expanded):
    """An old downgrade cannot silently remove or reinterpret a newer schema."""
    from backend.db.development_migration import restore_development_kinds

    with pytest.raises(RuntimeError, match="rollback refused"):
        restore_development_kinds(expanded.conn)
    assert expanded.conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version=36"
    ).fetchone()


@pytest.mark.parametrize("obstacle", ["new_kind", "unclosed_peer"])
def test_kind_inverse_requires_legacy_history_and_closed_peers(expanded, obstacle):
    """Removing empty workspace storage does not authorize reinterpretation of an execution or an unclosed scope."""
    from backend.db.development_migration import (
        restore_development_kinds,
        restore_development_workspaces,
    )
    from backend.runtime.peer_registry import PeerRegistry

    c = expanded
    restore_development_workspaces(c.conn)
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "original")
    if obstacle == "unclosed_peer":
        PeerRegistry(c.store).prepare(lease, "native")
        # A copied/inconsistent DB can report a stopped root while retaining its original peer.
        c.conn.execute(
            "UPDATE runtime_runs SET status='needs_review' WHERE id=?", (run.run_id,)
        )
        c.conn.execute(
            "UPDATE runtime_attempts SET status='finished' WHERE id=?",
            (lease.attempt_id,),
        )
    else:
        c.store.finish(lease, native_status="completed", summary="Historical")
        c.conn.execute(
            "UPDATE runtime_runs SET execution_kind='code_review' WHERE id=?",
            (run.run_id,),
        )
    c.conn.commit()
    with pytest.raises(RuntimeError, match="rollback refused"):
        restore_development_kinds(c.conn)
    assert c.conn.execute("SELECT 1 FROM schema_migrations WHERE version=36").fetchone()


def test_inverse_failure_rolls_back_marker_index_and_column(expanded):
    """A source-owner index depending on the kind causes an atomic refusal, never a damaged partial downgrade."""
    import sqlite3

    from backend.db.development_migration import (
        restore_development_kinds,
        restore_development_workspaces,
    )

    c = expanded
    restore_development_workspaces(c.conn)
    c.conn.execute("CREATE INDEX owner_kind_index ON runtime_runs(execution_kind)")
    c.conn.commit()
    with pytest.raises(sqlite3.OperationalError):
        restore_development_kinds(c.conn)
    assert c.conn.execute("SELECT 1 FROM schema_migrations WHERE version=36").fetchone()
    assert c.conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='idx_runtime_active_task'"
    ).fetchone()
    assert "next_execution_kind" not in {
        row[1] for row in c.conn.execute("PRAGMA table_info(runtime_runs)")
    }
    assert c.conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='owner_kind_index'"
    ).fetchone()
