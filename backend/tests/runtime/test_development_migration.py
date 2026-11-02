"""Prepare four native execution kinds without losing existing runs, attempts or owner schema."""

import sqlite3
from pathlib import Path

import pytest

from backend.db.migrations import apply_sql_resource

RESOURCE = Path(__file__).resolve().parents[2] / "db/development_schema.sql"


def version35(c):
    """Remove only unused newer structures so each test genuinely starts from the historical constraint."""
    from backend.db.development_migration import (
        restore_code_candidates,
        restore_development_kinds,
        restore_development_workspaces,
    )

    restore_code_candidates(c.conn)
    restore_development_workspaces(c.conn)
    restore_development_kinds(c.conn)
    return c


def insert_kind(c, run_id, kind):
    """Create schema-only fixture roots; this does not claim that a native actor was admitted."""
    c.conn.execute(
        """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,
        prompt,runtime,status,created_at,updated_at,execution_kind)
        VALUES(?,101,1001,'schema-fixture',1,?,'Schema fixture','codex','queued',1000,1000,?)""",
        (run_id, run_id, kind),
    )


def test_expansion_preserves_existing_attempt_references_and_owner_objects(
    coordination,
):
    """The kind expansion keeps primary identities and foreign keys instead of renaming the runs table."""
    c = version35(coordination)
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "schema-owner")
    c.conn.execute("CREATE TABLE owner_notes(body TEXT)")
    c.conn.execute("INSERT INTO owner_notes VALUES('Keep this data')")
    c.conn.commit()
    before = dict(
        c.conn.execute(
            "SELECT * FROM runtime_runs WHERE id=?", (run.run_id,)
        ).fetchone()
    )
    attempts = [tuple(row) for row in c.conn.execute("SELECT * FROM runtime_attempts")]
    apply_sql_resource(c.conn, RESOURCE)
    assert (
        dict(
            c.conn.execute(
                "SELECT * FROM runtime_runs WHERE id=?", (run.run_id,)
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
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert c.store.get(101, run.run_id).attempt_id == lease.attempt_id


@pytest.mark.parametrize("kind", ["development", "code_review"])
def test_expanded_kind_is_persisted_explicitly_without_inference_from_role_name(
    coordination, kind
):
    """Development/review identity is actual stored data; this is schema evidence, not a writable runtime proof."""
    c = version35(coordination)
    apply_sql_resource(c.conn, RESOURCE)
    insert_kind(c, "new-kind", kind)
    c.conn.commit()
    assert c.store.get(101, "new-kind").execution_kind == kind
    with pytest.raises(sqlite3.IntegrityError):
        insert_kind(c, "unknown-kind", "invented-role")
    c.conn.rollback()


def test_execution_slots_allow_one_author_and_one_independent_review_only(coordination):
    """Two different author kinds cannot race for the same task, nor can two review kinds."""
    c = version35(coordination)
    c.store.admit(c.spec)
    apply_sql_resource(c.conn, RESOURCE)
    with pytest.raises(sqlite3.IntegrityError):
        insert_kind(c, "second-author", "development")
    c.conn.rollback()
    insert_kind(c, "one-review", "code_review")
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        insert_kind(c, "second-review", "finding_review")
    c.conn.rollback()
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 2
