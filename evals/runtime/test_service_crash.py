"""Validate crash evidence against replay, lost effects and invented closure without another model call."""

from copy import deepcopy

import pytest

from evals.runtime.run_service_crash import IMMUTABLE, verify_recovery


def observations():
    """Construct explicitly synthetic verifier inputs, never a substitute for live recovery receipts."""
    before = {key: [{'synthetic': key}] for key in IMMUTABLE}
    before.update(runs=[{'id': 'original'}], dispatches=[{'attempt_id': 'original-attempt', 'status': 'reserved'}],
                  peers=[{'state': 'bound'}], unrevoked_grants=1, task_status='in_progress')
    after = deepcopy(before)
    after.update(peers=[{'state': 'closed'}], unrevoked_grants=0)
    after['dispatches'][0]['status'] = 'unknown'
    receipt = {'status': 'failed', 'task_accepted': False, 'inference_started': False}
    return before, after, receipt


@pytest.mark.parametrize('question', [False, True])
def test_preserved_effects_support_only_the_durable_recovery_outcome(question):
    """A question resumes its wait; other interrupted work remains failed without accepting the task."""
    before, after, receipt = observations()
    receipt['status'] = 'waiting_input' if question else 'failed'
    verify_recovery(before, after, receipt, question=question)


@pytest.mark.parametrize('mutation', [*IMMUTABLE, 'new_run', 'new_dispatch', 'replaced_dispatch',
                                    'settled_usage', 'live_peer', 'missing_peers', 'live_grant', 'accepted', 'false_outcome'])
def test_plausible_final_prose_cannot_hide_invalid_crash_evidence(mutation):
    """Reject independent forms of lost state, replay, false settlement and unproved closure."""
    before, after, receipt = observations()
    if mutation in IMMUTABLE:
        after[mutation] = []
    elif mutation == 'new_run':
        after['runs'].append({'id': 'unexpected'})
    elif mutation == 'new_dispatch':
        after['dispatches'].append({'attempt_id': 'unexpected'})
    elif mutation == 'replaced_dispatch':
        after['dispatches'][0]['attempt_id'] = 'replacement'
    elif mutation == 'settled_usage':
        after['dispatches'][0]['status'] = 'settled'
    elif mutation == 'live_peer':
        after['peers'][0]['state'] = 'bound'
    elif mutation == 'missing_peers':
        after['peers'] = []
    elif mutation == 'live_grant':
        after['unrevoked_grants'] = 1
    elif mutation == 'accepted':
        receipt['task_accepted'] = True
    else:
        receipt['status'] = 'needs_review'
    with pytest.raises(RuntimeError):
        verify_recovery(before, after, receipt, question=False)
