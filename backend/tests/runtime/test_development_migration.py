"""Prepare four native execution kinds without losing existing runs, attempts or owner schema."""

import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.parametrize("schema_target", [42])

from backend.db.migrations import apply_sql_resource
from backend.tests.runtime.migration_fixtures import historical_run

RESOURCE = Path(__file__).resolve().parents[2] / "db/development_schema.sql"


def version35(c):
    """Remove only unused newer structures so each test genuinely starts from the historical constraint."""
    from backend.db.development_migration import (
        restore_code_acceptances,
        restore_code_candidates,
        restore_code_checks,
        restore_code_reviews,
        restore_development_kinds,
        restore_development_workspaces,
        restore_native_code_reviews,
    )

    restore_code_acceptances(c.conn)

    restore_native_code_reviews(c.conn)
    restore_code_reviews(c.conn)
    restore_code_checks(c.conn)
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
    run_id = "historical-research"
    attempt_id = historical_run(c.conn, run_id, status="running")
    c.conn.execute("CREATE TABLE owner_notes(body TEXT)")
    c.conn.execute("INSERT INTO owner_notes VALUES('Keep this data')")
    c.conn.commit()
    before = dict(
        c.conn.execute(
            "SELECT * FROM runtime_runs WHERE id=?", (run_id,)
        ).fetchone()
    )
    attempts = [tuple(row) for row in c.conn.execute("SELECT * FROM runtime_attempts")]
    apply_sql_resource(c.conn, RESOURCE)
    assert (
        dict(
            c.conn.execute(
                "SELECT * FROM runtime_runs WHERE id=?", (run_id,)
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
    assert c.conn.execute("SELECT current_attempt_id FROM runtime_runs WHERE id=?", (run_id,)).fetchone()[0] == attempt_id


@pytest.mark.parametrize("kind", ["development", "code_review"])
def test_expanded_kind_is_persisted_explicitly_without_inference_from_role_name(
    coordination, kind
):
    """Development/review identity is actual stored data; this is schema evidence, not a writable runtime proof."""
    c = version35(coordination)
    apply_sql_resource(c.conn, RESOURCE)
    insert_kind(c, "new-kind", kind)
    c.conn.commit()
    assert c.conn.execute("SELECT execution_kind FROM runtime_runs WHERE id='new-kind'").fetchone()[0] == kind
    with pytest.raises(sqlite3.IntegrityError):
        insert_kind(c, "unknown-kind", "invented-role")
    c.conn.rollback()


def test_execution_slots_allow_one_author_and_one_independent_review_only(coordination):
    """Two different author kinds cannot race for the same task, nor can two review kinds."""
    c = version35(coordination)
    insert_kind(c, "first-author", "research")
    c.conn.commit()
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


def test_code_acceptance_inverse_preserves_reviews_and_refuses_owner_history(coordination):
    """Version42 removal preserves closed review bytes and rejects retained owner history without deleting it."""
    import sqlite3

    from backend.db.development_migration import restore_code_acceptances
    from backend.tests.runtime.migration_fixtures import historical_code_review
    from backend.tools.base.db import ensure_migrations

    c = coordination
    attempt = historical_code_review(c.conn)
    before = [tuple(row) for row in c.conn.execute("SELECT * FROM runtime_code_review_records")]
    restore_code_acceptances(c.conn)
    assert c.conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 41
    assert [tuple(row) for row in c.conn.execute("SELECT * FROM runtime_code_review_records")] == before
    with pytest.raises(sqlite3.IntegrityError, match="explicit owner acceptance"):
        c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    c.conn.rollback()
    ensure_migrations(c.database, target_version=42)
    # A retained SQL record alone must block deletion, irrespective of present eligibility.
    c.conn.execute(
        """INSERT INTO runtime_code_acceptances(project_id,task_id,run_id,attempt_id,
        review_run_id,context_version,operation_key,request_sha256,subject_sha256,
        review_sha256,receipt_json,accepted_at)
        VALUES(101,1001,'historical-author',?,'historical-review',1,'historical-owner',?,?,?,'{}',1000)""",
        (attempt, "a" * 64, "b" * 64, "c" * 64),
    )
    c.conn.commit()
    with pytest.raises(RuntimeError, match="history"):
        restore_code_acceptances(c.conn)
    assert c.conn.execute("SELECT count(*) FROM runtime_code_acceptances").fetchone()[0] == 1
    assert [tuple(row) for row in c.conn.execute("SELECT * FROM runtime_code_review_records")] == before
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert c.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

