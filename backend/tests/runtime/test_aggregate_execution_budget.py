"""Session advice, durable project admission and owner explanations must agree under stale observations, competing requests and restart; no model calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import RunConflict
from backend.runtime.history import RuntimeHistory
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.tests.runtime.test_codex_session import requests, session
from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


@pytest.mark.parametrize('totals,expected,increment', [([80,20,80],80,80),([40,70,10,60],70,40)])
async def test_stale_usage_cannot_refund_session_allowance_or_inflate_step_cost(tmp_path,totals,expected,increment):
    """Real RPC cumulative observations keep their high water in the final outcome and tool-visible budget, without summing retransmissions."""
    async def respond(_request):
        """Return one host result so the real child can expose attached budget advice."""
        return {'success':True,'contentItems':[]}
    async with session(tmp_path) as native:
        result=await native.run('usage-sequence:'+json.dumps(totals),on_request=respond)
    budget=json.loads(next(r['result'] for r in requests(tmp_path) if r.get('id')=='budget-1')['contentItems'][-1]['text'])['researcher_execution_budget']
    assert result.observed_tokens==expected
    assert budget['observed']['tokens']==expected
    assert budget['remaining']['observed_tokens']==100-expected
    assert budget['delivery_advice']['largest_token_increment']==increment


async def test_stale_usage_in_later_turn_cannot_reset_session_total(tmp_path):
    """A later turn keeps the same thread cumulative accounting, independently of the fresh per-turn wall deadline."""
    async def respond(_request):
        """Allow the child to finish each controlled turn without any product side effect."""
        return {'success':True,'contentItems':[]}
    async with session(tmp_path) as native:
        await native.run('usage-sequence:[80]',on_request=respond)
        result=await native.run('usage-sequence:[20]',on_request=respond)
    assert result.observed_tokens==80


async def test_project_budget_rejection_explains_no_dispatch_without_retry_or_fallback(service_setup):
    """An unaffordable first turn preserves its request and a concrete budget reason, without claiming runtime failure or spending inference."""
    s=service_setup;native=ControlledInference(s)
    async with coordinator(s,native,project_turn_limit=2,project_token_limit=99) as service:
        run=await service.submit(s.c.spec)
        await service.wait(run.run_id)
        view=s.c.store.get(101,run.run_id)
        assert view.status=='failed' and view.issue['code']=='project_budget_exhausted',view.issue
        assert view.issue['inference_started'] is False
        assert view.issue['next_action']=='inspect_project_budget'
        assert 'proyecto' in view.issue['message'] and '100' in view.issue['message'] and '99' in view.issue['message']
        budget=view.issue['project_budget']
        assert budget['used_turns']==0 and budget['accounted_tokens']==0
        assert budget['requested_tokens']==100 and budget['token_limit']==99
        assert budget['blocked_by']==['tokens']
        await service.submit(s.c.spec)
        assert not native.prompts
        assert s.c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==0
        assert s.c.conn.execute('SELECT count(*) FROM runtime_input_snapshots').fetchone()[0]==0
        assert s.c.conn.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]==0


async def test_restart_keeps_project_allowance_and_owner_can_inspect_original_unknown_usage(service_setup):
    """A new coordinator cannot refund an earlier unmeasured turn; its blocked request has a precise durable explanation and no new inference."""
    s=service_setup;first=ControlledInference(s);first.release.set()
    async with coordinator(s,first,project_turn_limit=1,project_token_limit=200) as service:
        run=await service.submit(s.c.spec)
        await service.wait(run.run_id)
        await service.stop(101,run.run_id)
    second=ControlledInference(s)
    async with coordinator(s,second,project_turn_limit=1,project_token_limit=200) as service:
        request=replace(s.c.spec,operation_key='after-restart')
        blocked=await service.submit(request)
        await service.wait(blocked.run_id)
        view=s.c.store.get(101,blocked.run_id)
        assert view.issue['code']=='project_budget_exhausted',view.issue
        assert view.issue['project_budget']['blocked_by']==['turns']
        assert view.issue['project_budget']['used_turns']==1
        assert not second.prompts and len(first.prompts)==1
        budget=RuntimeHistory(s.c.database).budget(101)
        assert budget['used_turns']==1 and budget['accounted_tokens']==100
        assert budget['observed_tokens'] is None and budget['unmeasured_dispatches']==1
        assert budget['remaining_turns']==0


def test_concurrent_project_requests_cannot_both_reserve_the_last_turn(coordination):
    """Two SQLite connections race at the reservation boundary; exactly one consumes the final shared project slot."""
    c=coordination;leases=[]
    for task in (1001,1002):
        run=c.store.admit(replace(c.spec,task_id=task,operation_key='competing-'+str(task)))
        lease=c.store.claim(101,run.run_id,'host-a')
        c.store.bind_thread(lease,thread_id='thread-'+str(task));leases.append(lease)
    barrier=Barrier(2)
    def reserve(lease):
        """Start an independent transaction after both contenders reach the same gate."""
        store=SQLiteRunStore(c.database,clock=lambda:c.now[0]);barrier.wait(timeout=5)
        try:
            return store.reserve_inference(lease,workspace='/host/alpha',catalog_hash='a'*64,limits=ExecutionLimits(5,3,1,10,100),project_turn_limit=1,project_token_limit=100)
        except RunConflict as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(reserve,leases))
    assert outcomes.count(True)==1
    blocked=next(o for o in outcomes if isinstance(o,RunConflict))
    assert type(blocked).__name__=='ProjectBudgetExhausted'
    assert blocked.budget['blocked_by']==['turns','tokens']
    assert blocked.budget['used_turns']==1 and blocked.budget['accounted_tokens']==100
    assert RuntimeHistory(c.database).budget(101)['used_turns']==1
    assert RuntimeHistory(c.database).budget(202)['used_turns']==0


@pytest.mark.timeout(180)
async def test_owned_project_budget_exhaustion_refuses_preparation_without_a_native_turn(owned_config):
    """An unaffordable attempt cannot start a Ken/native process, send a turn, run tools or retain live grants; generation and Ken are controlled."""
    from backend.tests.runtime.test_source_repair import app_for_sources

    c=owned_config;c.settings['project_token_limit']=999
    c.path.write_text(json.dumps(c.settings))
    _app,runtime=app_for_sources()
    async with runtime:
        run=await runtime.submit(c.s.c.spec,repository_id=11)
        await runtime.wait(run.run_id)
        view=runtime.store.get(101,run.run_id)
        assert view.status=='failed' and view.issue['code']=='project_budget_exhausted',view.issue
        assert view.issue['inference_started'] is False
        assert view.issue['project_budget']['requested_tokens']==1000
        assert view.issue['project_budget']['token_limit']==999
        assert view.result is None
        for table in ('runtime_preparation_reservations','runtime_inference_dispatches','runtime_input_snapshots','runtime_result_proposals','runtime_result_acceptances','research_reports'):
            assert c.s.c.conn.execute('SELECT count(*) FROM '+table).fetchone()[0]==0
        assert c.s.c.conn.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0]==0
        assert c.s.c.conn.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]==0
        assert c.s.c.conn.execute("SELECT count(*) FROM runtime_peers WHERE kind='ken' OR init_pid IS NOT NULL").fetchone()[0]==0
        assert not list(c.s.control.glob('native-state/*/home/fixture-tool-count.json'))
        assert not list(c.s.control.glob('native-state/*/home/fixture-turn.json'))


@pytest.mark.timeout(180)
async def test_owned_activity_without_progress_stops_with_original_reservation_and_explanation(owned_config):
    """Reasoning noise from a real child cannot extend the progress deadline, erase an unknown project reservation or create an accepted result."""
    from backend.tests.runtime.test_source_repair import app_for_sources

    c=owned_config;c.settings['limits'].update(wall_seconds=5,no_progress_seconds=.15)
    c.path.write_text(json.dumps(c.settings))
    marker=c.s.workspace/'.ken/chatter-only';marker.parent.mkdir(exist_ok=True);marker.touch()
    _app,runtime=app_for_sources()
    async with runtime:
        run=await runtime.submit(c.s.c.spec,repository_id=11)
        await runtime.wait(run.run_id)
        view=runtime.store.get(101,run.run_id)
        assert view.status=='failed' and view.issue['code']=='execution_limit',view.issue
        assert view.issue['limit_kind']=='progress' and 'sin progreso' in view.issue['message']
        assert view.issue['inference_started'] is True and view.result is None
        for table in ('runtime_result_proposals','runtime_result_acceptances','research_reports'):
            assert c.s.c.conn.execute('SELECT count(*) FROM '+table).fetchone()[0]==0
        assert c.s.c.conn.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0]==0
        assert c.s.c.conn.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]==0
        receipt=json.loads(next(c.s.control.glob('native-state/*/home/fixture-chatter.json')).read_text())
        assert receipt['deltas']>=2
        budget=RuntimeHistory(c.s.c.database).budget(101)
        assert budget['used_turns']==1 and budget['accounted_tokens']==1000
        assert budget['observed_tokens'] is None and budget['unsettled_dispatches']==1
