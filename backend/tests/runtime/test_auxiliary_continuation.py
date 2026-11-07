"""Explicit continuation preserves prior unknown use and excludes live original calculations."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from backend.runtime.auxiliary_budget import AuxiliaryBudget, AuxiliaryBudgetExceeded, AuxiliaryWorkUncertain
from backend.runtime.auxiliary_recovery import AuxiliaryRecovery
from backend.runtime.contracts import RunConflict, RunNotFound
from backend.tests.runtime.test_auxiliary_budget import calculation
from backend.tests.runtime.test_workspace_delivery import owner_client, workspace_app as workspace_app


def failed(budget):
    """Leave an original callback closed but without a result or measured CPU."""
    def lose():
        """Model result loss after the callback has ended."""
        raise OSError('lost')
    with pytest.raises(OSError):calculation(budget,execute=lose)


def decide(recovery, operation, key='continue-1'):
    """Authorize only the selected original calculation, never its surrounding native attempt."""
    return recovery.authorize(101,operation_key=key,source_operation_id=operation,reason='Repeat the interrupted search')


def test_closed_failure_has_one_explicit_successor_and_original_receipt(coordination):
    """A receipt survives lost responses and later work without refunding or granting another retry."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);failed(budget)
    recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
    assert row['diagnosis']['can_continue'] is True
    with pytest.raises(AuxiliaryWorkUncertain):calculation(budget)
    receipt=decide(recovery,row['operation_id'])
    assert budget.summary()['used_operations']==1 and receipt['work_started'] is False
    assert decide(recovery,row['operation_id'])==receipt
    assert recovery.receipt(101,'continue-1')==receipt
    assert calculation(budget)==calculation(budget)
    assert budget.summary()['used_operations']==2 and budget.summary()['accounted_cpu_ms']==3025
    assert decide(recovery,row['operation_id'])==receipt
    with pytest.raises(RunConflict):decide(recovery,row['operation_id'],'different')
    with pytest.raises(RunNotFound):recovery.receipt(202,'continue-1')
    assert recovery.list(202)['items']==[]


def test_live_owner_and_unfinished_callback_cannot_be_repeated(coordination):
    """Elapsed time or a reserved row never implies that an actual original owner has ended."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);entered=Event();release=Event()
    def busy():
        """Hold the actual owner while another SQLite connection inspects it."""
        entered.set();assert release.wait(5);return b'{}'
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(calculation,budget,execute=busy)
        try:
            assert entered.wait(5)
            recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
            assert row['diagnosis']['code']=='running'
            with pytest.raises(RunConflict):decide(recovery,row['operation_id'])
        finally:release.set();pending.result(timeout=5)
    assert recovery.list(101)['items'][0]['diagnosis']['code']=='complete'


def test_real_owner_death_allows_new_calculation_without_erasing_pending_hold(coordination):
    """A real terminated original process can be replaced only after an explicit owner decision."""
    c=coordination
    code="""import os,sys
from backend.runtime.auxiliary_budget import AuxiliaryBudget
AuxiliaryBudget(sys.argv[1],101).execute(b'one',kind='semantic',fingerprint='a'*64,cpu_ceiling_ms=3000,execute=lambda:os._exit(73))
"""
    assert subprocess.run([sys.executable,'-c',code,str(c.database)],check=False,timeout=10).returncode==73
    recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
    assert row['status']=='reserved' and row['diagnosis']['can_continue']
    decide(recovery,row['operation_id'])
    budget=AuxiliaryBudget(c.database,101);calculation(budget)
    assert budget.summary()['accounted_cpu_ms']==3025 and budget.summary()['pending_operations']==1


def test_permission_does_not_override_budget_or_allow_two_successors(coordination):
    """Two owner decisions compete for one successor; execution still needs newly available project capacity."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);failed(budget)
    recovery=AuxiliaryRecovery(c.store);operation=recovery.list(101)['items'][0]['operation_id'];gate=Barrier(2)
    def compete(key):
        """Race independent owner transactions over the same immutable original identity."""
        gate.wait(timeout=5)
        try:return decide(AuxiliaryRecovery(c.store),operation,key)
        except RunConflict:return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,['first','second']))
    assert results.count('blocked')==1
    c.conn.execute('UPDATE runtime_auxiliary_policies SET operation_limit=1 WHERE project_id=101');c.conn.commit()
    with pytest.raises(AuxiliaryBudgetExceeded):calculation(budget)
    assert budget.summary()['used_operations']==1
    c.conn.execute('UPDATE runtime_auxiliary_policies SET operation_limit=2 WHERE project_id=101');c.conn.commit()
    calculation(budget)
    assert budget.summary()['used_operations']==2


def test_missing_identity_never_claims_closure(coordination):
    """Legacy rows require separate verified recovery, not elapsed-time guesses."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);failed(budget)
    recovery=AuxiliaryRecovery(c.store);operation=recovery.list(101)['items'][0]['operation_id']
    c.conn.execute('DELETE FROM runtime_auxiliary_executions');c.conn.commit()
    assert recovery.list(101)['items'][0]['diagnosis']['code']=='identity_unavailable'
    with pytest.raises(RunConflict):decide(recovery,operation)


def test_changed_observer_and_permission_failure_are_unknown(monkeypatch):
    """A different kernel or inaccessible original process is never classified as absent."""
    from backend.runtime import auxiliary_execution as execution

    original=execution.process_identity(os.getpid())
    assert execution.process_state(original)=='alive'
    assert execution.process_state({**original,'boot_id':'another-kernel'})=='unknown'
    assert execution.process_state({**original,'observer_namespace':-1})=='unknown'
    def denied(_pid):
        """Represent permission failure without pretending that the process disappeared."""
        raise PermissionError('unreadable process')
    monkeypatch.setattr(execution,'_pidfd',denied)
    assert execution.process_state(original)=='unknown'


def test_new_permission_still_requires_current_native_grant(coordination):
    """Owner continuation cannot restore a withdrawn native capability or create an additional native attempt."""
    from backend.tests.runtime.test_inference_journal import reservation
    from backend.research.models import ResearchForbidden

    c=coordination;_,lease=reservation(c)
    token=c.research.issue_grant(project_id=101,task_id=1001,agent_id='researcher-a',permissions={'sources.read'})
    scope=c.research.authorize(token);c.store.bind_grant(lease,scope.grant_id)
    budget=AuxiliaryBudget(c.database,101,research=c.research,scope=scope);failed(budget)
    recovery=AuxiliaryRecovery(c.store);decide(recovery,recovery.list(101)['items'][0]['operation_id'])
    c.research.revoke_grant(scope.grant_id)
    with pytest.raises(ResearchForbidden):calculation(budget)
    assert AuxiliaryBudget(c.database,101).summary()['used_operations']==1
    assert c.conn.execute('SELECT count(*) FROM runtime_attempts').fetchone()[0]==1


def test_unused_inverse_and_used_history_guard(coordination):
    """Empty latest metadata can reverse, but recorded execution cannot be erased through a downgrade."""
    from backend.db.auxiliary_continuation_migration import restore_auxiliary_continuation_schema
    from backend.tools.base.db import ensure_migrations

    c=coordination;restore_auxiliary_continuation_schema(c.conn)
    assert c.conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==61
    ensure_migrations(c.database);failed(AuxiliaryBudget(c.database,101))
    with pytest.raises(RuntimeError,match='recorded'):restore_auxiliary_continuation_schema(c.conn)


async def test_owner_api_recovers_exact_receipt_and_excludes_tool_bearer(coordination,workspace_app):
    """Real owner/session/CSRF boundaries protect permission changes and project-scoped read-only recovery."""
    import httpx

    c=coordination;failed(AuxiliaryBudget(c.database,101));recovery=AuxiliaryRecovery(c.store)
    body={'operation_key':'owner-web','source_operation_id':recovery.list(101)['items'][0]['operation_id'],'reason':'Search again'}
    path='/api/projects/101/local-work'
    async with workspace_app.router.lifespan_context(workspace_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workspace_app),base_url='http://localhost') as outsider:
            assert (await outsider.post(path+'/continuations',json=body)).status_code in (401,403)
            assert (await outsider.post(path+'/continuations',json=body,headers={'Authorization':'Bearer untrusted-tool'})).status_code in (401,403)
        async with owner_client(workspace_app) as owner:
            csrf=owner.headers.pop('X-Researcher-CSRF')
            assert (await owner.post(path+'/continuations',json=body)).status_code==403
            owner.headers['X-Researcher-CSRF']=csrf
            listed=await owner.get(path);assert listed.status_code==200
            assert listed.json()['items'][0]['diagnosis']['can_continue']
            assert 'owner_json' not in listed.text and 'output_sha256' not in listed.text
            sent=await owner.post(path+'/continuations',json=body);assert sent.status_code==200,sent.text
            assert (await owner.get(path+'/continuations/owner-web')).json()==sent.json()
            assert (await owner.post(path+'/continuations',json=body)).json()==sent.json()
            assert (await owner.get('/api/projects/202/local-work/continuations/owner-web')).status_code==404
            assert (await owner.post('/api/projects/202/local-work/continuations',json=body)).status_code==404
    assert AuxiliaryBudget(c.database,101).summary()['used_operations']==1
    assert c.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0]==0


def test_actual_worker_is_bound_before_input_and_explicit_successor_reuses_new_result(coordination,tmp_path,monkeypatch):
    """Exercise real IPC, early worker exit, physical reaping and one authorized successor through the production transport."""
    from backend.research.worker_transport import exchange
    from backend.research.parser_process import ParserLimits
    from backend.research.models import SourceUnavailable
    from backend.runtime.auxiliary_execution import LocalExecution, process_state

    c=coordination;marker=tmp_path/'input-received';worker=tmp_path/'trusted_test_worker.py'
    worker.write_text(f'''import json,sys
from pathlib import Path
data=sys.stdin.buffer.read()
marker=Path({str(marker)!r})
if not marker.exists():
 marker.write_bytes(data)
 raise SystemExit(73)
print(json.dumps({{"ok":True,"execution":{{"cpu_used_seconds":0.01}}}}))
''')
    original_bind=LocalExecution.bind;bound=[]
    def bind_before_input(self,pid):
        """Verify durable registration occurs before the first worker can observe a single input byte."""
        original_bind(self,pid)
        row=c.conn.execute('SELECT phase,worker_json FROM runtime_auxiliary_executions WHERE operation_id=?',(self.operation_id,)).fetchone()
        assert row['phase']=='worker' and json.loads(row['worker_json'])['pid']==pid
        if not bound:assert not marker.exists()
        bound.append(pid)
    monkeypatch.setattr(LocalExecution,'bind',bind_before_input)
    budget=AuxiliaryBudget(c.database,101)
    def invoke():
        """Use unchanged producer bytes and input so only the owner's permission can authorize another worker."""
        with budget.bound():return exchange(b'one',worker=worker,options={'wall_seconds':3},limits=ParserLimits(cpu_seconds=2),cancelled=Event(),label='JSON')
    with pytest.raises(SourceUnavailable):invoke()
    recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
    assert row['diagnosis']['can_continue'] and row['status']=='unknown'
    record=c.conn.execute('SELECT * FROM runtime_auxiliary_executions').fetchone()
    assert record['phase']=='closed' and process_state(json.loads(record['worker_json']))=='closed'
    with pytest.raises(AuxiliaryWorkUncertain):invoke()
    decide(recovery,row['operation_id'])
    result=json.loads(invoke());assert result['ok'] and result['local_accounting']['reused'] is False
    again=json.loads(invoke());assert again['local_accounting']['reused'] is True
    assert len(bound)==2 and bound[0]!=bound[1]
    assert budget.summary()['accounted_cpu_ms']==3010


def test_dead_owner_with_live_worker_is_blocked_until_exact_worker_ends(coordination,tmp_path):
    """Killing the real host does not imply child closure; recovery observes the bound child through its pidfd."""
    import select
    import time
    from backend.runtime.peer_process import _pidfd, _signal

    c=coordination;worker=tmp_path/'waiting_worker.py'
    worker.write_text('import signal,sys,time\nsignal.alarm(10)\nsys.stdin.buffer.read()\ntime.sleep(8)\n')
    program='''import sys
from pathlib import Path
from threading import Event
from backend.runtime.auxiliary_budget import AuxiliaryBudget
from backend.research.worker_transport import exchange
from backend.research.parser_process import ParserLimits
with AuxiliaryBudget(sys.argv[1],101).bound():
 exchange(b'one',worker=Path(sys.argv[2]),options={'wall_seconds':10},limits=ParserLimits(cpu_seconds=2),cancelled=Event(),label='JSON')
'''
    parent=subprocess.Popen([sys.executable,'-c',program,str(c.database),str(worker)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    fd=None
    try:
        deadline=time.monotonic()+5;record=None
        while time.monotonic()<deadline:
            record=c.conn.execute("SELECT worker_json FROM runtime_auxiliary_executions WHERE phase='worker'").fetchone()
            if record:break
            assert parent.poll() is None;time.sleep(.01)
        assert record is not None
        fd=_pidfd(json.loads(record['worker_json'])['pid'])
        parent.kill();parent.wait(timeout=3)
        recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
        assert row['diagnosis']['code']=='running'
        with pytest.raises(RunConflict):decide(recovery,row['operation_id'])
        _signal(fd);poller=select.poll();poller.register(fd,select.POLLIN|select.POLLHUP)
        assert poller.poll(3000)
        assert recovery.list(101)['items'][0]['diagnosis']['can_continue']
        decide(recovery,row['operation_id'])
        assert AuxiliaryBudget(c.database,101).summary()['used_operations']==1
    finally:
        if fd is not None:_signal(fd);os.close(fd)
        if parent.poll() is None:parent.kill()
        parent.wait(timeout=3)


def test_crash_during_unbound_creation_remains_explicitly_uncertain(coordination):
    """A real owner exits in the Popen registration gap; no child-absence claim is fabricated."""
    c=coordination
    program='''import os,sys
from backend.runtime.auxiliary_budget import AuxiliaryBudget
from backend.runtime.auxiliary_execution import CURRENT_AUXILIARY_EXECUTION
def crash():
 CURRENT_AUXILIARY_EXECUTION.get().spawning()
 os._exit(73)
AuxiliaryBudget(sys.argv[1],101).execute(b'one',kind='semantic',fingerprint='a'*64,cpu_ceiling_ms=3000,execute=crash)
'''
    assert subprocess.run([sys.executable,'-c',program,str(c.database)],check=False,timeout=10).returncode==73
    recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
    assert row['diagnosis']['code']=='closure_unknown'
    with pytest.raises(RunConflict):decide(recovery,row['operation_id'])


def test_pagination_and_second_generation_keep_every_original(coordination):
    """A failed successor requires a new explicit decision; history retains both generations and bounded cursors."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);failed(budget)
    recovery=AuxiliaryRecovery(c.store);first=recovery.list(101)['items'][0]
    decide(recovery,first['operation_id']);failed(budget)
    page=recovery.list(101,limit=1);second=page['items'][0]
    assert page['next_before']==second['sequence'] and second['operation_id']!=first['operation_id']
    assert recovery.list(101,before=page['next_before'],limit=1)['items'][0]['operation_id']==first['operation_id']
    receipt=decide(recovery,second['operation_id'],'generation-2');assert receipt['generation']==2
    calculation(budget)
    assert budget.summary()['used_operations']==3 and budget.summary()['accounted_cpu_ms']==6025


def test_closed_worker_with_receipt_still_being_saved_cannot_be_repeated(coordination,monkeypatch):
    """An original owner can still commit its result after worker closure; continuation waits for that receipt."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);entered=Event();release=Event();finish=budget._finish
    def delayed_finish(*args):
        """Hold the real callback after closure and before its original receipt commits."""
        entered.set();assert release.wait(5);return finish(*args)
    monkeypatch.setattr(budget,'_finish',delayed_finish)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(calculation,budget)
        try:
            assert entered.wait(5)
            assert c.conn.execute('SELECT phase FROM runtime_auxiliary_executions').fetchone()[0]=='closed'
            recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
            assert row['diagnosis']['code']=='running'
            with pytest.raises(RunConflict):decide(recovery,row['operation_id'])
        finally:release.set();pending.result(timeout=5)
    assert recovery.list(101)['items'][0]['diagnosis']['code']=='complete'


@pytest.mark.parametrize('schema_target',[61])
def test_forward_upgrade_preserves_unknown_legacy_work_without_inventing_process_identity(coordination):
    """Migration62 retains old unknown CPU exactly and cannot manufacture the missing original host identity."""
    from backend.tools.base.db import ensure_migrations

    c=coordination
    c.conn.execute("INSERT INTO runtime_auxiliary_work(project_id,operation_id,kind,fingerprint,input_sha256,input_bytes,cpu_ceiling_ms,status,created_at) VALUES(101,?,'json',?, ?,10,3000,'unknown',1000)",('a'*64,'b'*64,'c'*64));c.conn.commit()
    ensure_migrations(c.database)
    recovery=AuxiliaryRecovery(c.store);row=recovery.list(101)['items'][0]
    assert row['diagnosis']['code']=='identity_unavailable'
    assert AuxiliaryBudget(c.database,101).summary()['held_cpu_ms']==3000
    with pytest.raises(RunConflict):decide(recovery,row['operation_id'])


def test_competing_requests_consume_the_same_permission_only_once(coordination):
    """Concurrent callers share the successor identity; they cannot both enter a fresh worker callback."""
    c=coordination;budget=AuxiliaryBudget(c.database,101);failed(budget)
    recovery=AuxiliaryRecovery(c.store);decide(recovery,recovery.list(101)['items'][0]['operation_id'])
    gate=Barrier(2);entered=Event();release=Event();calls=[]
    def worker():
        """Keep the only admitted successor running while its concurrent caller observes the reservation."""
        calls.append(1);entered.set();assert release.wait(5);return b'{"execution":{"cpu_used_seconds":0.01}}'
    def request():
        """Use independent store connections and the same input, version and explicit permission."""
        gate.wait(timeout=5)
        try:return calculation(AuxiliaryBudget(c.database,101),execute=worker)
        except AuxiliaryWorkUncertain:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(request) for _ in range(2)]
        try:assert entered.wait(5)
        finally:release.set()
        for future in futures:future.result(timeout=5)
    assert len(calls)==1 and budget.summary()['used_operations']==2
