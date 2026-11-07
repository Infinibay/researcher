"""Reject misleading functional-evaluation receipts without replaying a live model turn."""

from copy import deepcopy

import pytest

from evals.communication_flow.run import FIXTURE, PREFIX, SCENARIOS, verify_observations


def receipt():
    """Build a synthetic verifier input, explicitly separate from real product observations."""
    return {
        'unrevoked_grants': 0, 'peers': [{'state': 'closed'}],
        'tools': [{'tool': 'ken_find', 'arguments': {}, 'response': {'success': True}},
                  {'tool': 'ken_read', 'arguments': {'path': 'evidence.py'},
                   'response': {'success': True, 'contentItems': [{'text': FIXTURE}]}}],
        'attempts': [{'instructions_sha256': 'policy'}, {'instructions_sha256': 'policy',
            'input': {'context_version': 2, 'request_history': {'requests': [{
                'content': PREFIX + SCENARIOS['question_answer']['request'],
                'current_authorization': False, 'source_context_version': 1}]}}}],
    }


def test_complete_registered_source_is_checked_without_an_inference_call():
    """Validate existing observations and reject symbols copied from an unrelated earlier fixture."""
    value = receipt()
    verify_observations(value, SCENARIOS['question_answer'], 'policy')
    value['tools'][1]['response']['contentItems'] = [{'text': 'timeout_seconds tax_amount CorrectionReceipt'}]
    with pytest.raises(RuntimeError, match='registered communication source'):
        verify_observations(value, SCENARIOS['question_answer'], 'policy')


@pytest.mark.parametrize('mutation', ['active_peer', 'wrong_policy', 'current_authority', 'old_context'])
def test_semantically_invalid_receipts_cannot_pass_from_a_correct_answer(mutation):
    """Matching prose or source is insufficient when closure, policy or context provenance is wrong."""
    value = deepcopy(receipt())
    if mutation == 'active_peer':
        value['peers'][0]['state'] = 'active'
    elif mutation == 'wrong_policy':
        value['attempts'][1]['instructions_sha256'] = 'different'
    elif mutation == 'current_authority':
        value['attempts'][1]['input']['request_history']['requests'][0]['current_authorization'] = True
    else:
        value['attempts'][1]['input']['context_version'] = 1
    with pytest.raises(RuntimeError):
        verify_observations(value, SCENARIOS['question_answer'], 'policy')
