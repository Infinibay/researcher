"""Reject misleading handoff observations before relying on real subscription responses."""

from copy import deepcopy
import json

import pytest

from evals.handoff_communication.run import CASES, PREFIX, register, verify_controls


def observation(case):
    """Build a controlled verifier witness; these values never count as model evidence."""
    return {'status':'observed','owned_backend_terminal':True,'admissions_sent':1,
            'attempts':[{'instructions_sha256':'policy','input':{'request':PREFIX+case['request'],'task':{'context_json':json.dumps(case['context'])}}}],
            'peers':[{'state':'closed'}],'unrevoked_grants':0,'runs':[{'status':case['expected_state']}],
            'questions':[{}] if case['expected_state']=='waiting_input' else [],'task_status':'in_progress',
            'scope_checks':{'source_files_unchanged':True,'effect_counts':{'research_reports':0,'acceptances':0}}}


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_controlled_witness_matches_only_its_original_case(case):
    """Question and explanation cases retain different required states and exact supplied context."""
    value=observation(case)
    verify_controls(value,case,'policy')
    value['attempts'][0]['input']['task']['context_json']='{}'
    with pytest.raises(ValueError,match='handoff context'):verify_controls(value,case,'policy')


@pytest.mark.parametrize('fault',['policy','open_peer','extra_turn','fake_wait','source_edit','effect'])
def test_correct_prose_cannot_hide_wrong_scope_or_missing_question(fault):
    """Reject changed authority and lifecycle evidence independently of the answer's wording."""
    case=CASES[1];value=deepcopy(observation(case))
    if fault=='policy':value['attempts'][0]['instructions_sha256']='other'
    elif fault=='open_peer':value['peers'][0]['state']='active'
    elif fault=='extra_turn':value['admissions_sent']=2
    elif fault=='fake_wait':value['questions']=[]
    elif fault=='source_edit':value['scope_checks']['source_files_unchanged']=False
    else:value['scope_checks']['effect_counts']['acceptances']=1
    with pytest.raises(ValueError):verify_controls(value,case,'policy')


def test_registration_freezes_two_cases_and_preserves_lower_operator_limits(tmp_path):
    """Preparation never sends inference, overwrites an experiment or exceeds the supplied resource limits."""
    from evals.context_alignment.protocol import load_registered

    assets=tmp_path/'assets.json';assets.write_text(json.dumps({'limits':{'max_observed_tokens':90000,'max_tool_calls':9},'project_token_limit':80000}))
    root=tmp_path/'trial';manifest=register(root,assets)
    assert manifest['maximum_model_turns']==2
    for item in manifest['cases']:
        protocol=load_registered(root/item['id'])
        assert protocol['limits']['max_observed_tokens']==80000 and protocol['limits']['max_tool_calls']==9
        assert protocol['human_comprehension'] is None and protocol['maximum_model_turns']==1
    with pytest.raises(FileExistsError):register(root,assets)
