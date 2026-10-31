"""Durable native dispatch, conservative budgets and owner recovery in real SQLite."""

import json
from dataclasses import replace

import pytest

from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import RunConflict, StaleAttempt


def test_unknown_dispatch_retains_overrun_without_summing_cumulative_usage(
    coordination,
):
    c = coordination
    run, lease = reservation(c)
    reserve(c, lease)
    for cumulative in (40, 200, 10):
        c.store.note_inference_usage(lease, cumulative)
    c.store.cancel(101, run.run_id)
    c.store.retire_inference(lease, outcome="cancelled")
    row = c.conn.execute(
        "SELECT status,observed_tokens FROM runtime_inference_dispatches"
    ).fetchone()
    assert tuple(row) == ("unknown", 200)
    next_run = c.store.admit(replace(c.spec, operation_key="next"))
    next_lease = c.store.claim(101, next_run.run_id, "host-a")
    c.store.bind_thread(next_lease, thread_id="native-next")
    with pytest.raises(RunConflict, match="budget"):
        reserve(c, next_lease)


def test_dispatch_records_its_model_and_cannot_relabel_a_reserved_turn(coordination):
    c = coordination
    run, lease = reservation(c)
    options = {
        "workspace": "/host/alpha",
        "catalog_hash": "a" * 64,
        "limits": ExecutionLimits(60, 30, 1, 10, 100),
    }
    assert c.store.reserve_inference(lease, model="chosen-model-a", **options)
    assert c.store.get(101, run.run_id).model == "chosen-model-a"
    assert not c.store.reserve_inference(lease, model="chosen-model-a", **options)
    with pytest.raises(RunConflict):
        c.store.reserve_inference(lease, model="different-model-b", **options)


def reservation(c):
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "host-a")
    c.store.bind_thread(lease, thread_id="native-a")
    return run, lease


def reserve(c, lease, **kwargs):
    return c.store.reserve_inference(
        lease,
        workspace="/host/alpha",
        catalog_hash="a" * 64,
        limits=ExecutionLimits(60, 30, 1, 10, 100),
        project_turn_limit=2,
        project_token_limit=200,
        **kwargs,
    )


def test_dispatch_is_reserved_once_before_native_receipt_and_never_replayed(
    coordination,
):
    c = coordination
    run, lease = reservation(c)
    assert reserve(c, lease) is True
    assert reserve(c, lease) is False
    row = c.conn.execute("SELECT * FROM runtime_inference_dispatches").fetchone()
    assert row["attempt_id"] == lease.attempt_id
    assert row["status"] == "reserved"
    assert json.loads(row["limits_json"])["max_observed_tokens"] == 100
    assert c.store.get(101, run.run_id).turn_id is None
    with pytest.raises(RunConflict):
        c.store.reserve_inference(
            lease,
            workspace="/host/beta",
            catalog_hash="a" * 64,
            limits=ExecutionLimits(60, 30, 1, 10, 100),
        )


def test_unreported_consumption_keeps_reservation_across_reopen(coordination):
    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    run, lease = reservation(c)
    reserve(c, lease)
    c.store.settle_inference(lease, observed_tokens=None, native_status="completed")
    c.store.finish(lease, native_status="completed", summary="Draft")
    c.store.cancel(101, run.run_id)
    second = c.store.admit(replace(c.spec, operation_key="second"))
    second_lease = c.store.claim(101, second.run_id, "host-a")
    c.store.bind_thread(second_lease, thread_id="native-b")
    c.store = SQLiteRunStore(c.database, clock=lambda: c.now[0])
    with pytest.raises(RunConflict, match="budget"):
        c.store.reserve_inference(
            second_lease,
            workspace="/host/alpha",
            catalog_hash="a" * 64,
            limits=ExecutionLimits(60, 30, 1, 10, 101),
            project_turn_limit=2,
            project_token_limit=200,
        )
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 1
    )


def test_owner_recovery_fences_old_attempts_and_preserves_unknown_dispatch(
    coordination,
):
    c = coordination
    run, lease = reservation(c)
    reserve(c, lease)
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="researcher-a",
        permissions={"sources.read"},
    )
    grant = c.research.authorize(token)
    c.store.bind_grant(lease, grant.grant_id)
    assert c.store.recover_owners("host-b") == 1
    assert c.store.get(101, run.run_id).status == "reconciling"
    assert not c.store.attempt_active(lease)
    assert (
        c.conn.execute("SELECT revoked_at FROM tool_grants").fetchone()[0] is not None
    )
    assert (
        c.conn.execute("SELECT status FROM runtime_inference_dispatches").fetchone()[0]
        == "unknown"
    )
    with pytest.raises(StaleAttempt):
        reserve(c, lease)
    assert c.store.recover_owners("host-b") == 0


def test_only_owned_terminal_worker_can_retire_stopped_attempt(coordination):
    c = coordination
    run, lease = reservation(c)
    reserve(c, lease)
    c.store.cancel(101, run.run_id)
    with pytest.raises(StaleAttempt):
        c.store.retire_inference(
            replace(lease, owner_id="impostor"), outcome="cancelled"
        )
    stopped = c.store.retire_inference(lease, outcome="cancelled")
    assert stopped.status == "cancelled"
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    assert (
        c.conn.execute("SELECT status FROM runtime_inference_dispatches").fetchone()[0]
        == "unknown"
    )


def test_retirement_cannot_hide_an_owned_command_without_a_terminal_receipt(
    coordination,
):
    from backend.runtime.contracts import CommandSpec

    c = coordination
    run, lease = reservation(c)
    c.store.reserve_job(
        lease,
        operation_key="command",
        executor_id="connection",
        workspace="/host/alpha",
        spec=CommandSpec(("/bin/true",)),
    )
    c.store.cancel(101, run.run_id)
    with pytest.raises(RunConflict, match="jobs"):
        c.store.retire_inference(lease, outcome="cancelled")


@pytest.mark.parametrize(
    "field,value",
    [
        ("wall_seconds", float("nan")),
        ("no_progress_seconds", float("inf")),
        ("max_turns", True),
        ("max_tool_calls", 1.5),
    ],
)
def test_execution_limits_are_finite_and_counts_are_integers(field, value):
    values = {
        "wall_seconds": 60,
        "no_progress_seconds": 30,
        "max_turns": 1,
        "max_tool_calls": 10,
        "max_observed_tokens": 100,
    }
    with pytest.raises(ValueError):
        ExecutionLimits(**{**values, field: value})
