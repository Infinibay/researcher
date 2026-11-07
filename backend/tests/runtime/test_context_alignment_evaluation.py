"""Protect paired communication experiments from changed context, leaked arm labels and accidental replay."""

import json
from pathlib import Path

import pytest


def test_pair_context_normalization_preserves_every_semantic_difference():
    """Only fresh run and attempt identities may differ; corrected evidence and requests remain comparable inputs."""
    from evals.context_alignment.protocol import comparable_input

    first = {'scope': {'project_id': 101, 'task_id': 1001, 'run_id': 'a', 'attempt_id': 'b'}, 'request': 'explain', 'corrections': []}
    second = json.loads(json.dumps(first))
    second['scope'].update(run_id='c', attempt_id='d')
    assert comparable_input(first) == comparable_input(second)
    second['corrections'].append({'statement': 'use litres', 'source_kind': 'user_message'})
    assert comparable_input(first) != comparable_input(second)
    assert first['scope']['run_id'] == 'a'


def test_registration_freezes_policies_cases_and_rejects_tampering(tmp_path):
    """A registered experiment cannot silently adopt later policies or changed reserved prompts."""
    from evals.context_alignment.protocol import register, load_registered

    root = tmp_path / 'study'
    register(root)
    before = load_registered(root)
    assert len(before['cases']) == 7 and before['maximum_model_turns'] == 16
    assert {row['split'] for row in before['cases']} == {'development', 'reserved'}
    with pytest.raises(FileExistsError):
        register(root)
    (root / 'candidate.txt').write_text('silently improved after seeing outcomes')
    with pytest.raises(ValueError, match='changed'):
        load_registered(root)


def test_review_packet_keeps_human_observation_unknown_and_hides_arm_identity():
    """Producing a response does not fill comprehension scores or expose baseline/candidate labels to the reviewer."""
    from evals.context_alignment.protocol import review_item

    item = review_item('profession', 'B', 'Conclusión observada.')
    assert item['response'] == 'Conclusión observada.'
    assert item['human_comprehension'] is None and item['human_effort_seconds'] is None
    assert 'baseline' not in json.dumps(item) and 'candidate' not in json.dumps(item)


@pytest.mark.parametrize('changed', ['comparable_input_sha256','catalog_hash','model_control'])
def test_pair_rejects_changed_context_catalog_or_model(changed):
    """A convenient result cannot be scored as a paired comparison after changing a controlled variable."""
    from evals.context_alignment.run import compare_pair

    row={'comparable_input_sha256':'input','catalog_hash':'tools','model_control':{'model':'fixed','reasoning_effort':'low'}}
    first={'attempts':[row]}
    second={'attempts':[dict(row,**{changed:'changed'})]}
    with pytest.raises(ValueError,match='control differs'):
        compare_pair(first,second)


async def test_existing_arm_cannot_dispatch_again(tmp_path):
    """A retained attempt, even without a completed receipt, blocks automatic replay before resource access."""
    from evals.context_alignment.run import run_arm

    (tmp_path/'profession-baseline').mkdir()
    with pytest.raises(FileExistsError,match='original receipt'):
        await run_arm(tmp_path,{}, {'id':'profession'}, 'baseline', tmp_path/'absent-assets')


def test_failed_or_unrelated_ken_reads_cannot_validate_a_pair():
    """Attempting a tool or reading unrelated source is insufficient evidence for a controlled code explanation."""
    from evals.context_alignment.run import verify_ken

    records=[{'tool':name,'response':{'success':False,'contentItems':[]}} for name in ('ken_find','ken_read')]
    with pytest.raises(RuntimeError,match='successful'):
        verify_ken(records)
    for row in records:
        row['response']['success']=True
    records[1]['response']['contentItems']=[{'type':'inputText','text':'Unrelated source'}]
    with pytest.raises(RuntimeError,match='registered source'):
        verify_ken(records)
    records[1]['response']['contentItems'][0]['text']='def timeout_seconds: def tax_amount: class CorrectionReceipt:'
    verify_ken(records)


def test_model_comparison_ignores_receipt_identity_but_preserves_scope_and_selection():
    """Independent runs cannot share receipt IDs, but changed actor, project or model settings invalidate pairing."""
    from evals.context_alignment.protocol import comparable_model

    first={'run_id':'one','attempt_id':'attempt-one','selected_at':1,'model':'fixed',
           'reasoning_effort':'low','source':'host','revision':0,'project_id':101,'actor_id':'researcher','fence':1}
    second={**first,'run_id':'two','attempt_id':'attempt-two','selected_at':2}
    assert comparable_model(first)==comparable_model(second)
    for key in ('model','reasoning_effort','source','revision','project_id','actor_id','fence'):
        assert comparable_model(first)!=comparable_model({**second,key:'changed'})
    assert first['run_id']=='one'
