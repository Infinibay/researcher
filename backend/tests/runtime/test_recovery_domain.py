"""Recovery receipts require the host runtime's original global-domain closure, including old receipts."""

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_run_recovery import lost_attempt
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


@pytest.mark.parametrize('existing_receipt', [False, True])
async def test_recovery_cannot_report_success_while_original_domain_remains_active(service_setup, existing_receipt):
    """A prior local receipt cannot bypass a failed witnessed-domain close or authorize new inference."""
    setup = service_setup
    recovery, peers, _lease, command = lost_attempt(setup.c)
    if existing_receipt:
        recovery.reconcile(**command)
    runtime = ControlledInference(setup)
    calls = []

    def close_attempt(store, project_id, run_id, attempt_id):
        """Model a blocked physical boundary, not native inference or a successful closure."""
        calls.append((store.database, project_id, run_id, attempt_id))
        raise RunConflict('Original global domain still has an owner')

    runtime.close_attempt = close_attempt
    async with coordinator(setup, runtime) as service:
        with pytest.raises(RunConflict, match='global domain'):
            await service.reconcile(**command)
    assert calls == [(setup.c.database, 101, command['run_id'], command['attempt_id'])]
    assert not runtime.prompts


async def test_recovery_rechecks_domain_after_failure_and_preserves_original_receipt(service_setup):
    """Retry only the original recovery control after closure becomes observable; never replay work."""
    setup = service_setup
    _recovery, _peers, _lease, command = lost_attempt(setup.c)
    runtime = ControlledInference(setup)
    closed = []

    def close_attempt(store, project_id, run_id, attempt_id):
        """Expose one transient domain observation failure, then the same original identity."""
        closed.append((project_id, run_id, attempt_id))
        if len(closed) == 1:
            raise RunConflict('Original global domain still has an owner')
        return {'execution_closed': True}

    runtime.close_attempt = close_attempt
    async with coordinator(setup, runtime) as service:
        with pytest.raises(RunConflict, match='global domain'):
            await service.reconcile(**command)
        assert setup.c.store.get(101, command['run_id']).status == 'reconciling'
        result = await service.reconcile(**command)
        assert result['status'] == 'failed' and result['inference_started'] is False
        assert await service.reconcile(**command) == result
    assert len(closed) == 3 and len(set(closed)) == 1
    assert not runtime.prompts


@pytest.mark.parametrize('wrong_field', ['database_identity', 'project_id', 'task_id', 'fence'])
def test_global_recovery_refuses_mismatched_original_provenance_before_control(coordination, monkeypatch, wrong_field):
    """Synthetic journal data with another origin must never reach kernel/domain recovery."""
    from contextlib import contextmanager
    from types import SimpleNamespace

    from backend.runtime import publication_closure

    recovery, _peers, lease, _command = lost_attempt(coordination)
    grant = {'attempt_id': lease.attempt_id, 'database_identity': recovery.peers._database_identity(),
             'project_id': 101, 'task_id': 1001, 'fence': lease.fence}
    grant[wrong_field] = 'different-origin'

    @contextmanager
    def journal(**_kwargs):
        """Supply a synthetic witnessed-record shape to isolate provenance comparison."""
        yield SimpleNamespace(load=lambda: SimpleNamespace(records={'broker:grant:original': grant}))

    def forbidden_control(*_args):
        """Fail if mismatched authority reaches a physical recovery operation."""
        raise AssertionError('A different origin reached physical recovery')

    monkeypatch.setattr(publication_closure, 'WitnessedAuthorityJournal', journal)
    monkeypatch.setattr(publication_closure.PeerBroker, 'recover', forbidden_control)
    with pytest.raises(RunConflict, match='provenance'):
        publication_closure.close_original_attempt({}, coordination.store, 101, lease.run_id, lease.attempt_id)


def test_owned_runtime_exposes_the_same_exact_attempt_closure_boundary(monkeypatch):
    """Native recovery forwards original identities to the existing witnessed retirement implementation."""
    from types import SimpleNamespace

    from backend.runtime import publication_closure
    from backend.runtime.owned_runtime import OwnedCodexRuntime

    calls = []

    def close(*args):
        """Observe adapter arguments without manufacturing a kernel closure claim."""
        calls.append(args)
        return 'observed'

    monkeypatch.setattr(publication_closure, 'close_original_attempt', close)
    runtime = SimpleNamespace(authority={'fixture': 'private-original'})
    assert OwnedCodexRuntime.close_attempt(runtime, 'store', 101, 'run', 'attempt') == 'observed'
    assert calls == [(runtime.authority, 'store', 101, 'run', 'attempt')]
