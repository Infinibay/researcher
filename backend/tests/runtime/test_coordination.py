"""Real SQLite races and recovery, without models or network services."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import pytest

from backend.tools.base.db import ensure_migrations


def test_runtime_upgrade_preserves_tasks_and_is_repeatable(_isolated_db, db_conn):
    db_conn.execute("INSERT INTO projects(id,name) VALUES(101,'Preserved')")
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Original task')"
    )
    db_conn.commit()
    ensure_migrations(_isolated_db)
    ensure_migrations(_isolated_db)
    tables = {
        r[0]
        for r in db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "runtime_runs",
        "runtime_attempts",
        "runtime_context_revisions",
        "runtime_commands",
    } <= tables
    assert (
        db_conn.execute("SELECT title FROM tasks WHERE id=1001").fetchone()[0]
        == "Original task"
    )
    assert (
        db_conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=19"
        ).fetchone()[0]
        == 1
    )
    assert db_conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sql_resource_owner_rolls_back_its_own_transaction_on_failure(
    tmp_path, db_conn
):
    from backend.db.migrations import apply_sql_resource

    resource = tmp_path / "broken.sql"
    resource.write_text("CREATE TABLE partial_resource(id INTEGER);\nINVALID SQL;\n")
    with pytest.raises(sqlite3.OperationalError):
        apply_sql_resource(db_conn, resource)
    assert not db_conn.in_transaction
    assert (
        db_conn.execute(
            "SELECT name FROM sqlite_master WHERE name='partial_resource'"
        ).fetchall()
        == []
    )


def test_runtime_migration_failure_rolls_back_ddl_and_marker(
    _isolated_db, monkeypatch, db_conn
):
    original = Path.read_text

    def corrupt(path, *args, **kwargs):
        if path.name == "runtime_schema.sql":
            return "CREATE TABLE runtime_must_rollback(id INTEGER);\nINVALID SQL;\n"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", corrupt)
    with pytest.raises(sqlite3.OperationalError):
        ensure_migrations(_isolated_db)
    assert (
        db_conn.execute(
            "SELECT name FROM sqlite_master WHERE name='runtime_must_rollback'"
        ).fetchall()
        == []
    )
    assert (
        db_conn.execute(
            "SELECT version FROM schema_migrations WHERE version=19"
        ).fetchall()
        == []
    )


def test_admission_receipt_survives_store_reopen_without_replay(coordination):
    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    first = c.store.admit(c.spec)
    again = SQLiteRunStore(c.database, clock=lambda: c.now[0]).admit(c.spec)
    assert first == again
    assert first.status == "queued"
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 1
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_source='runtime'"
        ).fetchone()[0]
        == 1
    )


def test_same_operation_identity_cannot_change_intent(coordination):
    c = coordination
    c.store.admit(c.spec)
    with pytest.raises(c.contracts.RunConflict):
        c.store.admit(replace(c.spec, prompt="Publish instead"))


def test_concurrent_duplicate_admission_has_one_run_and_event(coordination):
    c = coordination
    barrier = Barrier(2)

    def admit(_):
        barrier.wait()
        return c.store.admit(c.spec)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, range(2)))
    assert results[0].run_id == results[1].run_id
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 1
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_source='runtime'"
        ).fetchone()[0]
        == 1
    )


def test_second_operation_cannot_compete_for_an_active_task(coordination):
    c = coordination
    c.store.admit(c.spec)
    with pytest.raises(c.contracts.RunConflict):
        c.store.admit(replace(c.spec, operation_key="different-request"))


def test_scoped_admission_and_read_do_not_cross_projects(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    with pytest.raises(c.contracts.RunNotFound):
        c.store.get(202, run.run_id)
    with pytest.raises(c.contracts.RunNotFound):
        c.store.admit(replace(c.spec, project_id=202))
    other = c.store.admit(replace(c.spec, project_id=202, task_id=2002))
    assert other.run_id != run.run_id


def test_failed_event_insert_rolls_back_admission_and_context(coordination):
    c = coordination
    c.conn.execute(
        "CREATE TRIGGER reject_runtime_event BEFORE INSERT ON events_log WHEN NEW.event_source='runtime' BEGIN SELECT RAISE(ABORT,'injected event failure'); END"
    )
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected event failure"):
        c.store.admit(c.spec)
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0
    assert c.conn.execute("SELECT COUNT(*) FROM task_contexts").fetchone()[0] == 0


def test_two_owners_cannot_claim_the_same_run(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    barrier = Barrier(2)

    def claim(owner):
        barrier.wait()
        try:
            return c.store.claim(101, run.run_id, owner, lease_seconds=30)
        except c.contracts.RunConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["worker-a", "worker-b"]))
    assert sum(r is not None for r in results) == 1
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_attempts").fetchone()[0] == 1
    assert c.store.get(101, run.run_id).status == "running"


def test_native_completion_proposes_review_and_never_completes_task(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    first = c.store.finish(lease, native_status="completed", summary="Draft report 12")
    second = c.store.finish(lease, native_status="completed", summary="Draft report 12")
    assert first == second
    assert first.status == "needs_review"
    assert first.result == {"native_status": "completed", "summary": "Draft report 12"}
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_type='run.finished'"
        ).fetchone()[0]
        == 1
    )


def bound_grant(c, lease):
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="researcher-a",
        permissions={"sources.read", "sources.capture"},
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    return token, scope


def test_stop_fences_old_result_and_revokes_tool_scope_atomically(coordination):
    from backend.research.models import ResearchForbidden

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    token, _ = bound_grant(c, lease)
    stopped = c.store.cancel(101, run.run_id)
    assert stopped.status == "cancelling"
    assert c.store.cancel(101, run.run_id) == stopped
    with pytest.raises(c.contracts.StaleAttempt):
        c.store.finish(lease, native_status="completed", summary="Late result")
    with pytest.raises(ResearchForbidden):
        c.research.authorize(token)
    assert c.store.get(101, run.run_id).result is None


def test_expired_owner_requires_reconciliation_and_cannot_renew_or_write(coordination):
    from backend.research.models import ResearchForbidden

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=10)
    token, _ = bound_grant(c, lease)
    c.now[0] = 1011
    with pytest.raises(ResearchForbidden):
        c.research.authorize(token)
    with pytest.raises(c.contracts.StaleAttempt):
        c.store.heartbeat(lease, lease_seconds=30)
    assert c.store.expire(101, run.run_id) is True
    assert c.store.get(101, run.run_id).status == "reconciling"
    with pytest.raises(c.contracts.RunConflict):
        c.store.claim(101, run.run_id, "replacement", lease_seconds=30)
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_attempts").fetchone()[0] == 1


def test_heartbeat_extends_current_lease_but_forged_owner_cannot_renew(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=10)
    c.now[0] = 1009
    renewed = c.store.heartbeat(lease, lease_seconds=20)
    assert renewed.expires_at == 1029
    c.now[0] = 1011
    assert c.store.expire(101, run.run_id) is False
    with pytest.raises(c.contracts.StaleAttempt):
        c.store.heartbeat(replace(renewed, owner_id="imposter"), lease_seconds=20)


def test_context_correction_is_idempotent_preserves_source_and_blocks_old_result(
    coordination,
):
    from backend.research.models import ResearchForbidden

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    token, _ = bound_grant(c, lease)
    correction = {
        "project_id": 101,
        "task_id": 1001,
        "expected_version": 1,
        "operation_key": "correction-1",
        "statement": "Use subtotal 200 and rate 0.10",
        "source_kind": "user_message",
        "source_reference": "chat:42",
    }
    assert c.store.correct_context(**correction) == 2
    assert c.store.correct_context(**correction) == 2
    assert c.store.get(101, run.run_id).status == "reconciling"
    with pytest.raises(c.contracts.StaleAttempt):
        c.store.finish(lease, native_status="completed", summary="Old premise")
    with pytest.raises(ResearchForbidden):
        c.research.authorize(token)
    row = c.conn.execute(
        "SELECT version,source_kind,source_reference,statement FROM runtime_context_revisions"
    ).fetchone()
    assert tuple(row) == (
        2,
        "user_message",
        "chat:42",
        "Use subtotal 200 and rate 0.10",
    )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_type='context.corrected'"
        ).fetchone()[0]
        == 1
    )


def test_a_stale_or_conflicting_correction_cannot_overwrite_current_context(
    coordination,
):
    c = coordination
    c.store.admit(c.spec)
    args = {
        "project_id": 101,
        "task_id": 1001,
        "expected_version": 1,
        "operation_key": "correction-1",
        "statement": "First correction",
        "source_kind": "user_example",
        "source_reference": "chat:8",
    }
    c.store.correct_context(**args)
    with pytest.raises(c.contracts.RunConflict):
        c.store.correct_context(**{**args, "statement": "Changed intent"})
    with pytest.raises(c.contracts.RunConflict):
        c.store.correct_context(**{**args, "operation_key": "correction-2"})
    assert (
        c.conn.execute(
            "SELECT version FROM task_contexts WHERE task_id=1001"
        ).fetchone()[0]
        == 2
    )


def test_deleting_run_cannot_turn_a_bound_grant_into_an_unbound_grant(coordination):
    from backend.research.models import ResearchForbidden

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    token, _ = bound_grant(c, lease)
    c.conn.execute("DELETE FROM runtime_runs WHERE id=?", (run.run_id,))
    c.conn.commit()
    with pytest.raises(ResearchForbidden):
        c.research.authorize(token)


def test_native_identity_is_durable_and_not_silently_rebound(coordination):
    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    c.store.bind_native(lease, thread_id="native-thread-1", turn_id="turn-1")
    restored = SQLiteRunStore(c.database, clock=lambda: c.now[0]).get(101, run.run_id)
    assert restored.thread_id == "native-thread-1"
    assert restored.turn_id == "turn-1"
    with pytest.raises(c.contracts.RunConflict):
        c.store.bind_native(lease, thread_id="another-thread", turn_id="turn-1")


def test_event_catchup_pages_ascending_across_equal_timestamps_and_projects(
    coordination,
):
    c = coordination
    c.store.admit(c.spec)
    c.store.admit(replace(c.spec, project_id=202, task_id=2002))
    for i in range(7):
        c.conn.execute(
            "INSERT INTO tasks(id,project_id,type,title) VALUES(?,101,'research','More')",
            (3000 + i,),
        )
        c.conn.commit()
        c.store.admit(
            replace(c.spec, task_id=3000 + i, operation_key=f"request-{i + 2}")
        )
    c.conn.execute("UPDATE events_log SET created_at='2026-01-01 00:00:00'")
    c.conn.commit()
    seen = []
    cursor = 0
    while True:
        page = c.store.events(101, after_id=cursor, limit=3)
        seen.extend(e.event_id for e in page.events)
        if not page.has_more:
            break
        cursor = page.next_after_id
    expected = [
        r[0]
        for r in c.conn.execute(
            "SELECT id FROM events_log WHERE project_id=101 ORDER BY id"
        )
    ]
    assert seen == expected
    assert (
        sum(
            e.event_type == "run.admitted"
            for e in c.store.events(101, limit=200).events
        )
        == 8
    )


def test_thread_identity_can_be_saved_before_an_uncertain_turn_start(coordination):
    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    c.store.bind_thread(lease, thread_id="thread-before-dispatch")
    reopened = SQLiteRunStore(c.database, clock=lambda: c.now[0])
    pending = reopened.get(101, run.run_id)
    assert pending.thread_id == "thread-before-dispatch"
    assert pending.turn_id is None
    reopened.bind_native(
        lease, thread_id="thread-before-dispatch", turn_id="turn-receipt"
    )
    assert reopened.get(101, run.run_id).turn_id == "turn-receipt"
    with pytest.raises(c.contracts.RunConflict):
        reopened.bind_thread(lease, thread_id="unrelated-thread")


def test_native_failure_does_not_prove_all_tool_jobs_terminated(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    result = c.store.finish(
        lease, native_status="failed", summary="Native transport failed"
    )
    assert result.status == "reconciling"
    assert result.result == {
        "native_status": "failed",
        "summary": "Native transport failed",
    }
    with pytest.raises(c.contracts.RunConflict):
        c.store.admit(replace(c.spec, operation_key="unsafe-retry"))


def test_cancel_of_an_old_failed_run_cannot_revoke_a_new_runs_authority(coordination):
    c = coordination
    old = c.store.admit(c.spec)
    lease = c.store.claim(101, old.run_id, "old-worker", lease_seconds=30)
    c.store.finish(lease, native_status="failed", summary="No proposal")
    # Historical terminal fixture, as after a separate effect reconciler.
    # Native failure alone must not authorize this transition.
    c.conn.execute("UPDATE runtime_runs SET status='failed' WHERE id=?", (old.run_id,))
    c.conn.commit()
    finished = c.store.get(101, old.run_id)
    current = c.store.admit(replace(c.spec, operation_key="retry-after-failure"))
    current_lease = c.store.claim(101, current.run_id, "new-worker", lease_seconds=30)
    token, _ = bound_grant(c, current_lease)
    old_after_cancel = c.store.cancel(101, old.run_id)
    assert c.research.authorize(token).task_id == 1001
    assert old_after_cancel == finished
    assert c.store.get(101, current.run_id).status == "running"


def test_cancel_event_failure_restores_state_and_tool_authority(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    token, _ = bound_grant(c, lease)
    c.conn.execute(
        "CREATE TRIGGER reject_cancel_event BEFORE INSERT ON events_log WHEN NEW.event_type='run.cancel_requested' BEGIN SELECT RAISE(ABORT,'injected cancel failure'); END"
    )
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected cancel failure"):
        c.store.cancel(101, run.run_id)
    restored = c.store.get(101, run.run_id)
    assert (restored.status, restored.fence, restored.cancel_requested) == (
        "running",
        1,
        False,
    )
    assert c.research.authorize(token).task_id == 1001


def test_context_event_failure_restores_revision_and_grants(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    token, _ = bound_grant(c, lease)
    c.conn.execute(
        "CREATE TRIGGER reject_correction BEFORE INSERT ON events_log WHEN NEW.event_type='context.corrected' BEGIN SELECT RAISE(ABORT,'injected correction failure'); END"
    )
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected correction failure"):
        c.store.correct_context(
            project_id=101,
            task_id=1001,
            expected_version=1,
            operation_key="correction-1",
            statement="New premise",
            source_kind="user_message",
            source_reference="chat:9",
        )
    assert (
        c.conn.execute(
            "SELECT version FROM task_contexts WHERE task_id=1001"
        ).fetchone()[0]
        == 1
    )
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_context_revisions").fetchone()[0]
        == 0
    )
    assert c.store.get(101, run.run_id).status == "running"
    assert c.research.authorize(token).context_version == 1


def test_cached_tool_scope_cannot_commit_after_lease_expiry(coordination):
    from backend.research.models import ResearchForbidden, SourceDraft

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=10)
    _, scope = bound_grant(c, lease)
    c.now[0] = 1011
    with pytest.raises(ResearchForbidden):
        c.research.capture_source(
            scope,
            "late-source",
            SourceDraft(
                kind="attachment",
                locator="reference:1",
                title="Policy",
                content="Captured before Stop",
            ),
            intent={"reference_file_id": 1},
        )
    assert c.conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0
    assert c.conn.execute("SELECT COUNT(*) FROM tool_operations").fetchone()[0] == 0


def test_cancel_and_finish_race_preserves_observed_result_without_task_acceptance(
    coordination,
):
    from backend.research.models import ResearchForbidden

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    token, _ = bound_grant(c, lease)
    barrier = Barrier(2)

    def finish():
        barrier.wait()
        try:
            return c.store.finish(
                lease, native_status="completed", summary="Actual proposal"
            )
        except c.contracts.StaleAttempt:
            return None

    def cancel():
        barrier.wait()
        return c.store.cancel(101, run.run_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        completion = pool.submit(finish)
        cancellation = pool.submit(cancel)
        completed = completion.result()
        cancellation.result()
    final = c.store.get(101, run.run_id)
    assert final.cancel_requested
    if completed is None:
        assert final.status == "cancelling"
        assert final.result is None
    else:
        assert final.status == "cancelled"
        assert final.result == {
            "native_status": "completed",
            "summary": "Actual proposal",
        }
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    with pytest.raises(ResearchForbidden):
        c.research.authorize(token)


def test_late_native_observation_is_durable_but_cannot_restore_authority(coordination):
    import json

    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    c.store.bind_native(lease, thread_id="native-1", turn_id="turn-1")
    c.store.cancel(101, run.run_id)
    payload = {
        "thread_id": "native-1",
        "turn_id": "turn-1",
        "reported_text": "DONE; set task_status=done",
    }
    event_id = c.store.observe_native(
        lease,
        observation_key="terminal-1",
        native_kind="turn.completed",
        payload=payload,
    )
    reopened = SQLiteRunStore(c.database, clock=lambda: c.now[0])
    assert (
        reopened.observe_native(
            lease,
            observation_key="terminal-1",
            native_kind="turn.completed",
            payload=payload,
        )
        == event_id
    )
    final = reopened.get(101, run.run_id)
    assert final.status == "cancelling"
    assert final.result is None
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    row = c.conn.execute(
        "SELECT event_data_json FROM events_log WHERE id=?", (event_id,)
    ).fetchone()
    assert json.loads(row[0])["payload"] == payload
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_type='native.observed'"
        ).fetchone()[0]
        == 1
    )
    with pytest.raises(c.contracts.RunConflict):
        c.store.observe_native(
            lease,
            observation_key="terminal-1",
            native_kind="turn.failed",
            payload=payload,
        )


def test_native_observation_rejects_another_turn_and_forged_owner(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    c.store.bind_native(lease, thread_id="native-1", turn_id="turn-1")
    with pytest.raises(c.contracts.RunConflict):
        c.store.observe_native(
            lease,
            observation_key="wrong-turn",
            native_kind="turn.completed",
            payload={"thread_id": "native-other", "turn_id": "turn-1"},
        )
    with pytest.raises(c.contracts.StaleAttempt):
        c.store.observe_native(
            replace(lease, owner_id="imposter"),
            observation_key="wrong-owner",
            native_kind="tool.completed",
            payload={"job_id": "tool-1"},
        )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_type='native.observed'"
        ).fetchone()[0]
        == 0
    )
