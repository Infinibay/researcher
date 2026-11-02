"""Explicit result storage upgrades and lossless refusal of unsafe downgrades."""

import pytest


def test_unused_result_schema_rolls_back_and_reapplies_without_losing_tasks(
    coordination,
):
    """Only unused storage can be removed; original task data and owner tables survive."""
    from backend.db.result_migration import restore_result_schema
    from backend.tools.base.db import ensure_migrations

    c = coordination
    from backend.db.development_migration import restore_development_kinds, restore_development_workspaces

    restore_development_workspaces(c.conn)
    restore_development_kinds(c.conn)
    c.conn.execute("CREATE TABLE owner_notes(body TEXT)")
    c.conn.execute("INSERT INTO owner_notes VALUES('keep')")
    c.conn.commit()
    before = [
        tuple(row) for row in c.conn.execute("SELECT id,title FROM tasks ORDER BY id")
    ]
    restore_result_schema(c.conn)
    assert (
        c.conn.execute("SELECT 1 FROM schema_migrations WHERE version=35").fetchone()
        is None
    )
    assert c.conn.execute("SELECT body FROM owner_notes").fetchone()[0] == "keep"
    assert [
        tuple(row) for row in c.conn.execute("SELECT id,title FROM tasks ORDER BY id")
    ] == before
    restore_result_schema(c.conn)
    ensure_migrations(c.database)
    assert (
        c.conn.execute("SELECT count(*) FROM runtime_result_proposals").fetchone()[0]
        == 0
    )
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "obstacle", ["live_run", "grant", "proposal", "newer_migration"]
)
def test_result_downgrade_refuses_live_authority_or_historical_delivery(
    coordination, obstacle
):
    """A downgrade cannot erase a delivery or remove a capability while its authority remains live."""
    from backend.db.result_migration import restore_result_schema
    from backend.research.models import ResultDraft
    from backend.tests.runtime.test_result_acceptance import make_active_result

    c = coordination
    from backend.db.development_migration import restore_development_kinds, restore_development_workspaces

    restore_development_workspaces(c.conn)
    restore_development_kinds(c.conn)
    if obstacle == "newer_migration":
        c.conn.execute(
            "INSERT INTO schema_migrations(version,name) VALUES(36,'future')"
        )
        c.conn.commit()
    elif obstacle == "grant":
        c.research.issue_grant(
            project_id=101,
            task_id=1001,
            agent_id="old-writer",
            permissions={"results.propose"},
        )
    elif obstacle == "live_run":
        c.store.admit(c.spec)
    else:
        _, lease, scope, _, _, report = make_active_result(c)
        c.research.propose_result(
            scope, "deliver", ResultDraft((report,), "Result.", ("Not repeated.",))
        )
        c.store.finish(lease, native_status="completed", summary="Ready.")
    before = c.conn.execute("SELECT count(*) FROM runtime_result_proposals").fetchone()[
        0
    ]
    with pytest.raises(RuntimeError, match="rollback refused"):
        restore_result_schema(c.conn)
    assert (
        c.conn.execute("SELECT count(*) FROM runtime_result_proposals").fetchone()[0]
        == before
    )
    assert c.conn.execute("SELECT 1 FROM schema_migrations WHERE version=35").fetchone()
