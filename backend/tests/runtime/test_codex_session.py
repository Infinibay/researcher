"""Native execution bounds and control, through a real child protocol peer."""
import asyncio
import json
import sys
from pathlib import Path

import pytest


def session(tmp_path, **limit_overrides):
    from backend.runtime.codex_rpc import StdioRpcClient
    from backend.runtime.codex_session import CodexSession, ExecutionLimits

    limits = {'wall_seconds':1, 'no_progress_seconds':0.15, 'max_turns':2, 'max_tool_calls':3, 'max_observed_tokens':100}
    limits.update(limit_overrides)
    rpc = StdioRpcClient(
        (sys.executable, '-u', str(Path(__file__).with_name('fake_codex_server.py'))),
        cwd=tmp_path, close_timeout=0.05,
    )
    return CodexSession(rpc, workspace=tmp_path, model='test-model', limits=ExecutionLimits(**limits))


def requests(tmp_path):
    return [json.loads(line) for line in (tmp_path/'protocol.jsonl').read_text().splitlines()]


async def test_requires_chatgpt_account_before_creating_a_thread_or_spending_a_turn(tmp_path):
    from backend.runtime.codex_session import SubscriptionRequired
    (tmp_path/'api-key-account').touch()
    with pytest.raises(SubscriptionRequired):
        async with session(tmp_path):
            pass
    assert not any(r['method'].startswith(('thread/','turn/')) for r in requests(tmp_path))


async def test_normal_turn_preserves_native_identity_text_and_unknown_consumption(tmp_path):
    async with session(tmp_path) as runtime:
        result = await runtime.run('answer')
        assert result.status == 'completed'
        assert result.text == tmp_path.name
        assert result.thread_id == runtime.thread_id
        assert result.turn_id
        assert result.observed_tokens is None
    turn = next(r for r in requests(tmp_path) if r['method']=='turn/start')
    assert turn['params']['threadId'] == result.thread_id


async def test_native_failed_turn_is_not_product_success(tmp_path):
    async with session(tmp_path) as runtime:
        assert (await runtime.run('failed')).status == 'failed'


async def test_unrelated_thread_completion_cannot_complete_this_run(tmp_path):
    async with session(tmp_path) as runtime:
        assert (await runtime.run('other-thread')).text == tmp_path.name


@pytest.mark.parametrize('input_text',['hang','chatter'])
async def test_silence_or_thinking_deltas_do_not_reset_no_progress_deadline(tmp_path,input_text):
    from backend.runtime.codex_session import ExecutionLimitExceeded
    async with session(tmp_path) as runtime:
        with pytest.raises(ExecutionLimitExceeded,match='progress'):
            await runtime.run(input_text)
    assert any(r['method']=='turn/interrupt' for r in requests(tmp_path))


async def test_wall_deadline_bounds_a_turn_independently_of_progress_deadline(tmp_path):
    from backend.runtime.codex_session import ExecutionLimitExceeded
    async with session(tmp_path,wall_seconds=0.08,no_progress_seconds=1) as runtime:
        with pytest.raises(ExecutionLimitExceeded,match='wall'):
            await runtime.run('hang')


async def test_total_turn_budget_prevents_another_model_request(tmp_path):
    from backend.runtime.codex_session import ExecutionLimitExceeded
    async with session(tmp_path,max_turns=1) as runtime:
        await runtime.run('answer')
        with pytest.raises(ExecutionLimitExceeded,match='turn'):
            await runtime.run('answer')
    assert sum(r['method']=='turn/start' for r in requests(tmp_path))==1


async def test_tool_budget_counts_unique_native_items_and_interrupts_excess(tmp_path):
    from backend.runtime.codex_session import ExecutionLimitExceeded
    async with session(tmp_path,max_tool_calls=3) as runtime:
        with pytest.raises(ExecutionLimitExceeded,match='tool'):
            await runtime.run('tools')
    async with session(tmp_path,max_tool_calls=4) as runtime:
        assert (await runtime.run('tools')).tool_calls==4


async def test_observed_token_budget_interrupts_instead_of_retrying_a_provider(tmp_path):
    from backend.runtime.codex_session import ExecutionLimitExceeded
    async with session(tmp_path) as runtime:
        with pytest.raises(ExecutionLimitExceeded,match='token'):
            await runtime.run('tokens')
    assert sum(r['method']=='turn/start' for r in requests(tmp_path))==1


async def test_human_cancel_is_sent_to_the_owned_active_turn(tmp_path):
    started=asyncio.Event()
    async with session(tmp_path,no_progress_seconds=1) as runtime:
        run=asyncio.create_task(runtime.run('hang',on_event=lambda _:started.set()))
        await asyncio.wait_for(started.wait(),1)
        await runtime.cancel()
        assert (await run).status=='interrupted'
    interrupt=next(r for r in requests(tmp_path) if r['method']=='turn/interrupt')
    assert interrupt['params']['threadId']==runtime.thread_id
    assert interrupt['params']['turnId']


async def test_correction_is_correlated_with_expected_turn_without_starting_another(tmp_path):
    started=asyncio.Event()
    async with session(tmp_path,no_progress_seconds=1) as runtime:
        run=asyncio.create_task(runtime.run('steer',on_event=lambda _:started.set()))
        await asyncio.wait_for(started.wait(),1)
        receipt=await runtime.steer('Correction: use HALF_UP')
        result=await run
        assert receipt['turnId']==result.turn_id
    records=requests(tmp_path)
    steer=next(r for r in records if r['method']=='turn/steer')
    assert steer['params']['expectedTurnId']==result.turn_id
    assert sum(r['method']=='turn/start' for r in records)==1


async def test_resume_uses_native_thread_identity_without_replaying_the_original_request(tmp_path):
    async with session(tmp_path) as runtime:
        await runtime.run('answer')
        thread_id=runtime.thread_id
    candidate=session(tmp_path)
    candidate.resume_thread_id=thread_id
    async with candidate:
        await candidate.run('answer')
    records=requests(tmp_path)
    assert sum(r['method']=='thread/start' for r in records)==1
    assert sum(r['method']=='thread/resume' for r in records)==1
    assert sum(r['method']=='turn/start' for r in records)==2


async def test_concurrent_run_is_rejected_before_dispatching_a_second_turn(tmp_path):
    started=asyncio.Event()
    async with session(tmp_path,no_progress_seconds=1) as runtime:
        run=asyncio.create_task(runtime.run('hang',on_event=lambda _:started.set()))
        await asyncio.wait_for(started.wait(),1)
        with pytest.raises(RuntimeError,match='active'):
            await runtime.run('answer')
        await runtime.cancel();await run
    assert sum(r['method']=='turn/start' for r in requests(tmp_path))==1


async def test_unhandled_approval_pauses_by_interrupting_without_granting_permission(tmp_path):
    from backend.runtime.codex_session import NativeInputRequired
    async with session(tmp_path) as runtime:
        with pytest.raises(NativeInputRequired) as error:
            await runtime.run('approval')
        assert error.value.request['id']=='approval-1'
    records=requests(tmp_path)
    assert any(r['method']=='turn/interrupt' for r in records)
    assert not any(r.get('id')=='approval-1' and 'result' in r for r in records)


async def test_explicit_host_decision_answers_native_request_by_its_id(tmp_path):
    received=[]
    async def decide(request):
        received.append(request)
        return {'decision':'decline'}
    async with session(tmp_path) as runtime:
        result=await runtime.run('approval',on_request=decide)
        assert result.status=='completed'
    assert received[0]['id']=='approval-1'
    response=next(r for r in requests(tmp_path) if r.get('id')=='approval-1')
    assert response=={'id':'approval-1','result':{'decision':'decline'}}


async def test_pending_host_decision_cannot_outlive_the_execution_deadline(tmp_path):
    from backend.runtime.codex_session import ExecutionLimitExceeded
    async def decide(request):
        await asyncio.Event().wait()
    async with session(tmp_path,wall_seconds=0.08,no_progress_seconds=1) as runtime:
        with pytest.raises(ExecutionLimitExceeded,match='wall'):
            await runtime.run('approval',on_request=decide)
    assert any(r['method']=='turn/interrupt' for r in requests(tmp_path))


async def test_cancel_during_start_waits_for_native_identity_and_stops_the_same_turn(tmp_path):
    async with session(tmp_path,no_progress_seconds=1) as runtime:
        run=asyncio.create_task(runtime.run('delayed-start'))
        async with asyncio.timeout(1):
            while not any(r['method']=='turn/start' for r in requests(tmp_path)):
                await asyncio.sleep(0.005)
        stop=asyncio.create_task(runtime.cancel())
        await asyncio.sleep(0)
        assert not stop.done(), 'Cancel returned before it could stop the pending native turn'
        await runtime.rpc.request('test/releaseStart')
        await stop
        assert (await run).status=='interrupted'
    assert sum(r['method']=='turn/interrupt' for r in requests(tmp_path))==1


async def test_duplicate_cancel_requests_share_one_native_interruption(tmp_path):
    started=asyncio.Event()
    async with session(tmp_path,no_progress_seconds=1) as runtime:
        run=asyncio.create_task(runtime.run('hang',on_event=lambda _:started.set()))
        await asyncio.wait_for(started.wait(),1)
        await asyncio.gather(runtime.cancel(),runtime.cancel())
        assert (await run).status=='interrupted'
    assert sum(r['method']=='turn/interrupt' for r in requests(tmp_path))==1


async def test_cancel_when_start_never_returns_reaps_its_process_without_a_native_id(tmp_path):
    import os

    from backend.runtime.codex_rpc import RpcDisconnected
    async with session(tmp_path,wall_seconds=10,no_progress_seconds=10) as runtime:
        pid=(await runtime.rpc.request('test/pid'))['pid']
        run=asyncio.create_task(runtime.run('delayed-start'))
        async with asyncio.timeout(1):
            while not any(r['method']=='turn/start' for r in requests(tmp_path)):
                await asyncio.sleep(0.005)
        await asyncio.wait_for(runtime.cancel(),3)
        with pytest.raises(RpcDisconnected):
            await asyncio.wait_for(run,1)
    with pytest.raises(ProcessLookupError):
        os.kill(pid,0)


async def test_two_workspaces_use_distinct_processes_and_native_threads(tmp_path):
    alpha=tmp_path/'alpha';beta=tmp_path/'beta'
    alpha.mkdir();beta.mkdir()
    async with session(alpha) as a, session(beta) as b:
        first,second=await asyncio.gather(a.run('answer'),b.run('answer'))
        assert (first.text,second.text)==('alpha','beta')
        assert first.thread_id!=second.thread_id
        assert (await a.rpc.request('test/pid'))['pid']!=(await b.rpc.request('test/pid'))['pid']
    assert all(r.get('params',{}).get('cwd',str(alpha))!=str(beta) for r in requests(alpha))


async def test_interrupted_turn_reaps_connection_before_returning_to_the_host(tmp_path):
    import os

    from backend.runtime.codex_rpc import RpcDisconnected

    started=asyncio.Event()
    async with session(tmp_path,no_progress_seconds=1) as runtime:
        pid=(await runtime.rpc.request('test/pid'))['pid']
        run=asyncio.create_task(runtime.run('hang',on_event=lambda _:started.set()))
        await asyncio.wait_for(started.wait(),1)
        await runtime.cancel()
        assert (await run).status=='interrupted'
        with pytest.raises(ProcessLookupError):
            os.kill(pid,0)
        with pytest.raises(RpcDisconnected):
            await runtime.rpc.request('echo')


async def test_readonly_research_request_does_not_start_a_writable_native_thread(tmp_path):
    from backend.runtime.codex_session import CodexSession
    prepared=session(tmp_path)
    runtime=CodexSession(prepared.rpc,workspace=tmp_path,model='test-model',limits=prepared.limits,sandbox='read-only')
    async with runtime:
        assert (await runtime.run('answer')).status=='completed'
    thread=next(r for r in requests(tmp_path) if r['method']=='thread/start')
    assert thread['params']['sandbox']=='read-only'
    assert thread['params']['approvalPolicy']=='on-request'
