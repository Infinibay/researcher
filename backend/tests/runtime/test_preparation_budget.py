"""Admission must precede runtime preparation and retain one durable hold across failure and dispatch; no model calls."""

from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import RunConflict
from backend.runtime.history import RuntimeHistory
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator

LIMITS = ExecutionLimits(5, 3, 1, 10, 100)


class PreparationProbe(ControlledInference):
    """Observe attempted startup before the existing controlled native factory does any work."""

    def __init__(self, setup, *, fail=False):
        """Select startup failure without changing the host admission implementation."""
        super().__init__(setup)
        self.opened = 0
        self.fail = fail

    @asynccontextmanager
    async def open(self, **kwargs):
        """Count preparation and optionally fail before a native session is available."""
        self.opened += 1
        if self.fail:
            raise RuntimeError('Controlled preparation failure')
        async with super().open(**kwargs) as session:
            yield session


async def test_exhausted_project_never_enters_runtime_preparation(service_setup):
    """An unaffordable request is refused before Ken/native startup, not merely before turn/start."""
    s = service_setup
    native = PreparationProbe(s)
    async with coordinator(s, native, project_token_limit=99) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        assert native.opened == 0
        view = s.c.store.get(101, run.run_id)
        assert view.status == 'failed' and view.issue['code'] == 'project_budget_exhausted'
        assert RuntimeHistory(s.c.database).budget(101)['used_turns'] == 0


async def test_failed_preparation_retains_capacity_and_blocks_another_task_after_restart(service_setup):
    """Startup failure cannot obtain unlimited free retries through a fresh coordinator or task."""
    s = service_setup
    first = PreparationProbe(s, fail=True)
    async with coordinator(s, first, project_turn_limit=1) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
    assert first.opened == 1
    attempt = RuntimeHistory(s.c.database).attempts(101, run.run_id)['items'][0]
    assert attempt['preparation_token_ceiling'] == 100 and attempt['dispatch_status'] is None
    budget = RuntimeHistory(s.c.database).budget(101)
    assert budget['used_turns'] == 1 and budget['preparation_only'] == 1
    assert budget['observed_tokens'] is None and budget['held_tokens'] == 100
    assert budget['unmeasured_dispatches'] == 0
    second = PreparationProbe(s, fail=True)
    async with coordinator(s, second, project_turn_limit=1) as service:
        run = await service.submit(replace(s.c.spec, task_id=1002, operation_key='new-task'))
        await service.wait(run.run_id)
    assert second.opened == 0


async def test_preparation_and_dispatch_count_as_one_request(service_setup):
    """The final frozen input consumes its existing hold, including when it used the last slot."""
    s = service_setup
    native = PreparationProbe(s)
    native.release.set()
    async with coordinator(s, native, project_turn_limit=1, project_token_limit=100) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        assert len(native.prompts) == 1
        assert s.c.store.input_record(101, run.run_id)['available']
    budget = RuntimeHistory(s.c.database).budget(101)
    assert budget['used_turns'] == 1 and budget['preparation_only'] == 0
    assert budget['accounted_tokens'] == 100 and budget['unmeasured_dispatches'] == 1


def test_two_connections_cannot_prepare_against_the_same_last_slot(coordination):
    """Independent connections serialize admission before either is allowed to create a native peer."""
    c = coordination
    leases = []
    for task in (1001, 1002):
        run = c.store.admit(replace(c.spec, task_id=task, operation_key=str(task)))
        leases.append(c.store.claim(101, run.run_id, 'host-a'))
    barrier = Barrier(2)

    def reserve(lease):
        """Race independent storage owners at the durable preparation boundary."""
        store = SQLiteRunStore(c.database, clock=lambda: c.now[0])
        barrier.wait(timeout=5)
        try:
            return store.reserve_preparation(lease, limits=LIMITS, project_turn_limit=1, project_token_limit=100)
        except RunConflict as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, leases))
    assert results.count(True) == 1
    assert type(next(item for item in results if isinstance(item, RunConflict))).__name__ == 'ProjectBudgetExhausted'
    assert RuntimeHistory(c.database).budget(101)['preparation_only'] == 1


def test_reserved_preparation_is_not_replayed_or_counted_twice(coordination):
    """A duplicate claim is not permission to restart preparation; converting it preserves its original limits."""
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, 'host-a')
    args = dict(limits=LIMITS, project_turn_limit=1, project_token_limit=100)
    assert c.store.reserve_preparation(lease, **args)
    assert c.store.reserve_preparation(lease, **args) is False
    c.store.bind_thread(lease, thread_id='original')
    assert c.store.reserve_inference(lease, workspace='/host/alpha', catalog_hash='a'*64, **args)
    assert c.store.reserve_inference(lease, workspace='/host/alpha', catalog_hash='a'*64, **args) is False
    assert RuntimeHistory(c.database).budget(101)['used_turns'] == 1


def test_owner_reduction_does_not_revoke_existing_preparation_and_settlement_counts_once(coordination):
    """Lower policy affects future admission; existing input keeps its ceiling and later measured settlement replaces the hold."""
    from backend.runtime.project_budget import ProjectBudgetPolicies

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, 'host-a')
    assert c.store.reserve_preparation(lease, limits=LIMITS)
    ProjectBudgetPolicies(c.store).update(101, operation_key='lower', expected_revision=0, turn_limit=1, token_limit=25)
    c.store.bind_thread(lease, thread_id='original')
    with pytest.raises(RunConflict, match='limits'):
        c.store.reserve_inference(lease, workspace='/host/alpha', catalog_hash='a'*64, limits=replace(LIMITS, max_observed_tokens=101))
    assert c.store.reserve_inference(lease, workspace='/host/alpha', catalog_hash='a'*64, limits=LIMITS)
    c.store.settle_inference(lease, observed_tokens=40, native_status='completed')
    budget = RuntimeHistory(c.database).budget(101)
    assert budget['used_turns'] == 1 and budget['accounted_tokens'] == 40
    assert budget['held_tokens'] == 0 and budget['preparation_only'] == 0
    assert budget['observed_tokens'] == 40 and budget['overrun_tokens'] == 15


def test_failed_input_freeze_retains_preparation_without_fabricating_dispatch(coordination, monkeypatch):
    """A failure inside the combined input transaction rolls back dispatch while preserving the earlier admission."""
    from backend.runtime import run_inputs

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, 'host-a')
    c.store.reserve_preparation(lease, limits=LIMITS)
    c.store.bind_thread(lease, thread_id='original')

    def fail(*args):
        """Interrupt freezing after the dispatch insert but before its transaction can commit."""
        raise RuntimeError('Controlled input failure')

    monkeypatch.setattr(run_inputs, 'freeze_input', fail)
    import hashlib
    with pytest.raises(RuntimeError, match='Controlled'):
        c.store.reserve_input(lease, workspace='/host/alpha', catalog_hash=hashlib.sha256(b'[]').hexdigest(), model='fixture', limits=LIMITS, developer_instructions='Instructions', catalog=[])
    assert c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
    budget = RuntimeHistory(c.database).budget(101)
    assert budget['used_turns'] == 1 and budget['held_tokens'] == 100 and budget['preparation_only'] == 1


def test_migration_preserves_old_dispatches_and_refuses_inverse_after_preparation(coordination):
    """Upgrade and unused inverse retain historical dispatch bytes without inventing preparation receipts."""
    from backend.db.project_check_policy_migration import restore_project_check_policy_schema
    from backend.db.preparation_budget_migration import restore_preparation_budget_schema
    from backend.tools.base.db import ensure_migrations

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, 'host-a')
    c.store.bind_thread(lease, thread_id='historical')
    c.store.reserve_inference(lease, workspace='/host/alpha', catalog_hash='a'*64, limits=LIMITS)
    original = [tuple(row) for row in c.conn.execute('SELECT * FROM runtime_inference_dispatches')]
    restore_project_check_policy_schema(c.conn);restore_preparation_budget_schema(c.conn)
    ensure_migrations(c.database)
    assert [tuple(row) for row in c.conn.execute('SELECT * FROM runtime_inference_dispatches')] == original
    budget = RuntimeHistory(c.database).budget(101)
    assert budget['used_turns'] == 1 and budget['preparation_only'] == 0
    run = c.store.admit(replace(c.spec, task_id=1002, operation_key='new'))
    lease = c.store.claim(101, run.run_id, 'host-a')
    c.store.reserve_preparation(lease, limits=LIMITS)
    with pytest.raises(RuntimeError, match='recorded'):
        restore_project_check_policy_schema(c.conn);restore_preparation_budget_schema(c.conn)
    assert RuntimeHistory(c.database).budget(101)['used_turns'] == 2
