"""Durable native command dispatch must never be retried from an uncertain receipt."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest


def setup_job(c):
    spec = c.contracts.CommandSpec(argv=("/bin/echo", "example"))
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "worker", lease_seconds=30)
    return lease, spec


def reserve(c, lease, spec, *, key="command-1", executor="peer-1"):
    return c.store.reserve_job(
        lease,
        operation_key=key,
        spec=spec,
        workspace="/fixture/alpha",
        executor_id=executor,
    )


def test_lost_dispatch_receipt_is_not_a_new_dispatch_on_another_connection(
    coordination,
):
    c = coordination
    lease, spec = setup_job(c)
    first = reserve(c, lease, spec)
    second = reserve(c, lease, spec, executor="replacement-peer")
    assert first.should_dispatch is True
    assert second.should_dispatch is False
    assert first.job.job_id == second.job.job_id
    assert second.job.executor_id == "peer-1"
    assert second.job.status == "dispatching"
    with pytest.raises(c.contracts.RunConflict):
        reserve(c, lease, replace(spec, argv=("/bin/echo", "changed")))


def test_concurrent_dispatch_has_one_durable_winner(coordination):
    c = coordination
    lease, spec = setup_job(c)
    barrier = Barrier(2)

    def run(peer):
        barrier.wait()
        return reserve(c, lease, spec, executor=peer)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ("peer-1", "peer-2")))
    assert sum(r.should_dispatch for r in results) == 1
    assert results[0].job.job_id == results[1].job.job_id


def test_uncertain_job_blocks_another_effect_until_reconciled(coordination):
    c = coordination
    lease, spec = setup_job(c)
    job = reserve(c, lease, spec).job
    c.store.finish_job(
        lease,
        job.job_id,
        executor_id="peer-1",
        exit_code=None,
        stdout=b"partial",
        stderr=b"",
        output_limited=False,
        error="RpcDisconnected",
    )
    with pytest.raises(c.contracts.RunConflict):
        reserve(c, lease, spec, key="different-effect")
    existing = reserve(c, lease, spec, executor="new-peer")
    assert existing.should_dispatch is False
    assert existing.job.status == "unknown"
    assert c.store.get(101, lease.run_id).status == "reconciling"
    assert c.store.attempt_active(lease) is False


def test_terminal_job_output_survives_reopen_and_frees_next_command(coordination):
    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    lease, spec = setup_job(c)
    job = reserve(c, lease, spec).job
    ended = c.store.finish_job(
        lease,
        job.job_id,
        executor_id="peer-1",
        exit_code=2,
        stdout=b"a\x00b",
        stderr=b"actual error",
        output_limited=False,
    )
    restored = SQLiteRunStore(c.database, clock=lambda: c.now[0]).get_job(
        101, job.job_id
    )
    assert restored == ended
    assert (restored.status, restored.exit_code, restored.stdout, restored.stderr) == (
        "exited",
        2,
        b"a\x00b",
        b"actual error",
    )
    assert reserve(c, lease, spec, key="next-command").should_dispatch is True
    assert c.store.get(101, lease.run_id).status == "running"


def test_stop_blocks_dispatch_but_preserves_late_terminal_fact(coordination):
    c = coordination
    lease, spec = setup_job(c)
    job = reserve(c, lease, spec).job
    c.store.cancel(101, lease.run_id)
    assert c.store.attempt_active(lease) is False
    with pytest.raises(c.contracts.StaleAttempt):
        reserve(c, lease, spec, key="late-command")
    cancelled = c.store.cancel_job(lease, job.job_id)
    assert cancelled.cancel_requested
    terminal = c.store.finish_job(
        lease,
        job.job_id,
        executor_id="peer-1",
        exit_code=137,
        stdout=b"effect before stop",
        stderr=b"",
        output_limited=False,
    )
    assert terminal.status == "exited"
    assert terminal.cancel_requested
    assert c.store.get(101, lease.run_id).status == "cancelling"
    assert c.store.get(101, lease.run_id).result is None


def test_job_identity_cannot_be_rebound_to_another_connection_or_project(coordination):
    c = coordination
    lease, spec = setup_job(c)
    job = reserve(c, lease, spec).job
    with pytest.raises(c.contracts.RunConflict):
        c.store.finish_job(
            lease,
            job.job_id,
            executor_id="unrelated-peer",
            exit_code=0,
            stdout=b"forged",
            stderr=b"",
            output_limited=False,
        )
    with pytest.raises(c.contracts.RunNotFound):
        c.store.get_job(202, job.job_id)
    assert c.store.get_job(101, job.job_id).status == "dispatching"


def test_missing_dispatch_event_prevents_persisting_the_dispatch_permit(coordination):
    c = coordination
    lease, spec = setup_job(c)
    c.conn.execute(
        "CREATE TRIGGER reject_job BEFORE INSERT ON events_log WHEN NEW.event_type='job.dispatching' BEGIN SELECT RAISE(ABORT,'injected job failure'); END"
    )
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected job failure"):
        reserve(c, lease, spec)
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"argv": ()},
        {"argv": ("/bin/echo", "bad\x00arg")},
        {"cwd": "../beta"},
        {"timeout_seconds": float("nan")},
        {"output_bytes": 0},
    ],
)
def test_invalid_command_never_becomes_a_dispatchable_record(coordination, changes):
    c = coordination
    with pytest.raises(ValueError):
        c.contracts.CommandSpec(**{"argv": ("/bin/echo", "safe"), **changes})
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0
