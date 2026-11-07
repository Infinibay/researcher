"""Real child RPC requests must consume host tool allowance before effects, independent of optional or reordered native lifecycle notifications."""

import json

import pytest

from backend.runtime.codex_rpc import RpcProtocolError
from backend.runtime.codex_session import ExecutionLimitExceeded
from backend.tests.runtime.test_codex_session import requests, session


def effect_recorder(tmp_path, seen):
    """Produce an actual host callback that journals each admitted effect; the native child cannot write this callback record."""
    async def effect(request):
        """Record exactly which original tool identities reached execution before returning an ordinary tool result."""
        seen.append(request['params']['callId'])
        with (tmp_path/'host-effects.jsonl').open('a') as out:
            out.write(json.dumps(request['params'])+'\n')
        return {'success':True,'contentItems':[{'type':'inputText','text':'Effect committed.'}]}
    return effect


@pytest.mark.parametrize('scenario',['host-no-start','host-duplicate-start','host-late-start'])
async def test_host_tool_limit_precedes_fourth_effect_with_missing_or_reordered_notifications(tmp_path, scenario):
    """Three allowed real callbacks may run; the fourth request cannot reach business code regardless of notification order."""
    seen=[]
    async with session(tmp_path, max_tool_calls=3) as native:
        with pytest.raises(ExecutionLimitExceeded) as stopped:
            await native.run(scenario,on_request=effect_recorder(tmp_path,seen))
    assert stopped.value.kind=='tools'
    assert stopped.value.budget['observed']['host_tool_requests_admitted']==3
    assert seen==['call-0','call-1','call-2']
    assert len((tmp_path/'host-effects.jsonl').read_text().splitlines())==3
    assert sum(r.get('method')=='turn/start' for r in requests(tmp_path))==1
    assert native.rpc._process.returncode is not None


@pytest.mark.parametrize('scenario',['host-no-start','host-duplicate-start','host-late-start'])
async def test_notifications_and_request_share_one_observed_tool_identity(tmp_path,scenario):
    """The same callId/item.id is counted once across request, duplicate start and completed-before-start delivery."""
    seen=[]
    async with session(tmp_path,max_tool_calls=4) as native:
        result=await native.run(scenario,on_request=effect_recorder(tmp_path,seen))
    assert result.tool_calls==4 and len(seen)==4
    responses=[r['result'] for r in requests(tmp_path) if str(r.get('id','')).startswith('host-rpc-')]
    counts=[json.loads(r['contentItems'][-1]['text'])['researcher_execution_budget']['observed']['tool_starts'] for r in responses]
    assert counts==[1,2,3,4]


async def test_completed_native_tools_without_started_notifications_still_consume_allowance(tmp_path):
    """Native-owned activity is still an observation fuse, not a claim that the host can revoke already completed commands."""
    async with session(tmp_path,max_tool_calls=3) as native:
        with pytest.raises(ExecutionLimitExceeded):await native.run('completed-tools')
    async with session(tmp_path,max_tool_calls=4) as native:
        assert (await native.run('completed-tools')).tool_calls==4


async def test_reused_call_identity_cannot_dispatch_a_second_host_effect(tmp_path):
    """A second RPC with the same original tool ID and changed arguments ends the connection without replaying or inventing the first receipt."""
    seen=[]
    async with session(tmp_path,max_tool_calls=4) as native:
        with pytest.raises(RpcProtocolError):await native.run('host-duplicate-request',on_request=effect_recorder(tmp_path,seen))
    assert seen==['call-0'] and native.rpc._process.returncode is not None


@pytest.mark.parametrize('scenario',['host-no-callid','host-no-turnid'])
async def test_host_request_needs_original_call_and_turn_identity_before_effect(tmp_path,scenario):
    """Missing identity cannot merge unrelated calls into one allowance or let an uncorrelated request reach the host."""
    seen=[]
    async def effect(_request):
        """Make even an invalid-identity callback observable instead of failing within the callback."""
        seen.append('effect')
        return {'success':True,'contentItems':[]}
    async with session(tmp_path,max_tool_calls=4) as native:
        with pytest.raises(RpcProtocolError):await native.run(scenario,on_request=effect)
    assert not seen


async def test_session_allowance_spans_turns_without_merging_same_call_ids(tmp_path):
    """A new turn may reuse a call ID but cannot reset the original session's consumed allowance."""
    seen=[]
    async with session(tmp_path,max_tool_calls=7) as native:
        first=await native.run('host-no-start',on_request=effect_recorder(tmp_path,seen))
        assert first.tool_calls==4
        with pytest.raises(ExecutionLimitExceeded):await native.run('host-no-start',on_request=effect_recorder(tmp_path,seen))
    assert len(seen)==7


async def test_duplicate_completion_is_not_new_progress(tmp_path):
    """Repeating one finished native item cannot keep the no-progress deadline alive until the larger wall ceiling."""
    async with session(tmp_path,wall_seconds=1,no_progress_seconds=.1) as native:
        with pytest.raises(ExecutionLimitExceeded) as stopped:await native.run('duplicate-completions')
    assert stopped.value.kind=='progress'
    assert stopped.value.budget['observed']['tool_starts']==1


async def test_native_kind_cannot_reuse_a_host_call_identity(tmp_path):
    """A native command and a dynamic host effect cannot share one identifier to evade the combined allowance."""
    seen=[]
    async with session(tmp_path) as native:
        with pytest.raises(RpcProtocolError):await native.run('host-kind-reuse',on_request=effect_recorder(tmp_path,seen))
    assert not seen
