"""Owner budget revisions preserve cumulative work and never dispatch; actual SQLite races, rollback and migration exercise the shared admission boundary."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import RunConflict, RunNotFound
from backend.runtime.history import RuntimeHistory
from backend.runtime.project_budget import ProjectBudgetPolicies
from backend.tests.runtime.test_inference_journal import reservation, reserve
from backend.tests.runtime.test_workspace_delivery import owner_client, workspace_app as workspace_app
from backend.tests.runtime.test_owned_factory import owned_config as owned_config


def change(c, key='budget-1', revision=0, turns=3, tokens=300):
    """Submit one explicit total-limit decision without touching the execution service."""
    return ProjectBudgetPolicies(c.store).update(101,operation_key=key,expected_revision=revision,turn_limit=turns,token_limit=tokens,reason='Owner chose more room for research.')


def test_owner_change_replays_original_receipt_and_preserves_usage(coordination):
    """A lost response can be recovered after a later policy change; neither replay nor a decrease refunds prior unknown consumption."""
    c=coordination;run,lease=reservation(c);reserve(c,lease)
    c.store.note_inference_usage(lease,40)
    before=[tuple(r) for r in c.conn.execute('SELECT * FROM runtime_inference_dispatches')]
    receipt=change(c)
    assert receipt['revision']==1 and receipt['previous_policy']=={'turn_limit':2,'token_limit':200,'revision':0}
    assert receipt['usage_at_decision']['accounted_tokens']==100
    assert receipt['inference_started'] is False
    assert change(c)==receipt
    lowered=change(c,key='lower',revision=1,turns=1,tokens=25)
    assert lowered['revision']==2
    assert change(c)==receipt
    assert ProjectBudgetPolicies(c.store).receipt(101,'budget-1')==receipt
    budget=RuntimeHistory(c.database).budget(101)
    assert budget['remaining_tokens']==0 and budget['overrun_tokens']==75
    assert budget['policy']=={'turn_limit':1,'token_limit':25,'revision':2}
    assert [tuple(r) for r in c.conn.execute('SELECT * FROM runtime_inference_dispatches')]==before
    assert c.store.attempt_active(lease)
    assert c.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0]==1


def test_explicit_policy_governs_next_admission_without_restarting_prior_attempt(coordination):
    """An owner revision supersedes host seeding values while old intent, consumption and attempt limits stay frozen."""
    c=coordination;run,lease=reservation(c);reserve(c,lease)
    c.store.cancel(101,run.run_id);c.store.retire_inference(lease,outcome='cancelled')
    change(c,turns=3,tokens=300)
    new=c.store.admit(replace(c.spec,operation_key='next'));second=c.store.claim(101,new.run_id,'host-a');c.store.bind_thread(second,thread_id='next-thread')
    assert reserve(c,second)
    assert RuntimeHistory(c.database).budget(101)['policy']['turn_limit']==3
    assert c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==2
    assert c.store.get(101,run.run_id).status=='cancelled'


def test_creation_before_first_turn_and_scope_and_stale_rejection(coordination):
    """The owner can set a new project budget without runtime setup; foreign receipt lookup and stale or changed intents cannot mutate it."""
    c=coordination;receipt=change(c)
    assert receipt['previous_policy'] is None
    assert c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==0
    with pytest.raises(RunConflict):change(c,tokens=400)
    with pytest.raises(RunConflict):change(c,key='stale')
    with pytest.raises(RunNotFound):ProjectBudgetPolicies(c.store).receipt(202,'budget-1')
    with pytest.raises(RunNotFound):ProjectBudgetPolicies(c.store).update(999,operation_key='missing',expected_revision=0,turn_limit=1,token_limit=1)
    assert RuntimeHistory(c.database).budget(202)['policy'] is None


@pytest.mark.parametrize('field,value',[('turn_limit',True),('token_limit',0),('token_limit',9007199254740992),('expected_revision',-1),('expected_revision',False)])
def test_invalid_policy_cannot_change_storage(coordination,field,value):
    """Reject lossy browser integers and ambiguous policy/revision values before any mutation."""
    c=coordination;body=dict(operation_key='invalid',expected_revision=0,turn_limit=3,token_limit=300)
    body[field]=value
    with pytest.raises(ValueError):ProjectBudgetPolicies(c.store).update(101,**body)
    assert RuntimeHistory(c.database).budget(101)['policy'] is None


def test_two_editors_cannot_overwrite_the_same_revision(coordination):
    """Independent write transactions compare the original revision under the same SQLite lock."""
    c=coordination;gate=Barrier(2)
    def edit(index):
        """Race two distinct decisions after both editors have read revision0."""
        gate.wait(timeout=5)
        try:return change(c,key='edit-'+str(index),tokens=300+index)
        except RunConflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,[1,2]))
    assert sum(r is not None for r in results)==1
    assert c.conn.execute('SELECT count(*) FROM runtime_project_budget_changes').fetchone()[0]==1
    assert RuntimeHistory(c.database).budget(101)['policy']['revision']==1


def test_process_loss_before_commit_retains_original_policy_and_allows_exact_retry(coordination):
    """Abrupt exit after policy and receipt writes, before commit, cannot leave a half-saved owner decision."""
    c=coordination;change(c)
    code='''import os,sys
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.runtime.project_budget import ProjectBudgetPolicies
store=SQLiteRunStore(sys.argv[1]);store._event=lambda *a,**k:os._exit(73)
ProjectBudgetPolicies(store).update(101,operation_key='crash',expected_revision=1,turn_limit=5,token_limit=500)
'''
    result=subprocess.run([sys.executable,'-c',code,str(c.database)],timeout=10,check=False)
    assert result.returncode==73
    assert RuntimeHistory(c.database).budget(101)['policy']['revision']==1
    with pytest.raises(RunNotFound):ProjectBudgetPolicies(c.store).receipt(101,'crash')
    retried=ProjectBudgetPolicies(c.store).update(101,operation_key='crash',expected_revision=1,turn_limit=5,token_limit=500)
    assert retried['revision']==2


def test_upgrade_preserves_old_policy_and_unused_inverse_preserves_it(_isolated_db,db_conn):
    """Migration60 adds revision0 without inventing owner decisions; an unused inverse restores59 and refuses used owner history."""
    from backend.db.project_budget_migration import restore_project_budget_schema
    from backend.db.auxiliary_budget_migration import restore_auxiliary_budget_schema
    from backend.db.auxiliary_continuation_migration import restore_auxiliary_continuation_schema
    from backend.tools.base.db import ensure_migrations
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from types import SimpleNamespace
    ensure_migrations(_isolated_db,target_version=59)
    c=SimpleNamespace(database=_isolated_db,conn=db_conn,store=SQLiteRunStore(_isolated_db))
    c.conn.execute("INSERT INTO projects(id,name) VALUES(101,'Historical')")
    c.conn.execute('INSERT INTO runtime_project_budgets VALUES(101,2,200)');c.conn.commit()
    ensure_migrations(c.database);ensure_migrations(c.database)
    assert RuntimeHistory(c.database).budget(101)['policy']=={'turn_limit':2,'token_limit':200,'revision':0}
    assert c.conn.execute('SELECT count(*) FROM runtime_project_budget_changes').fetchone()[0]==0
    restore_auxiliary_continuation_schema(c.conn)
    restore_auxiliary_budget_schema(c.conn)
    restore_project_budget_schema(c.conn)
    assert tuple(c.conn.execute('SELECT * FROM runtime_project_budgets').fetchone())==(101,2,200)
    ensure_migrations(c.database);change(c)
    restore_auxiliary_continuation_schema(c.conn)
    restore_auxiliary_budget_schema(c.conn)
    with pytest.raises(RuntimeError,match='history'):restore_project_budget_schema(c.conn)


async def test_budget_api_requires_owner_and_csrf_and_can_recover_without_runtime(coordination,workspace_app):
    """Authenticated owner changes and read-only receipts work while runtime is absent; tool bearer/no-session/CSRF failures cannot mutate policy."""
    import httpx

    path='/api/projects/101/work-budget';body=dict(operation_key='web-budget',expected_revision=0,turn_limit=4,token_limit=400,reason='Continue research',auxiliary_operation_limit=30,auxiliary_cpu_ms_limit=90000)
    async with workspace_app.router.lifespan_context(workspace_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workspace_app),base_url='http://localhost') as outsider:
            assert (await outsider.post(path,json=body)).status_code in (401,403)
            assert (await outsider.post(path,json=body,headers={'Authorization':'Bearer untrusted-tool'})).status_code in (401,403)
        async with owner_client(workspace_app) as owner:
            csrf=owner.headers.pop('X-Researcher-CSRF')
            assert (await owner.post(path,json=body)).status_code==403
            owner.headers['X-Researcher-CSRF']=csrf
            sent=await owner.post(path,json=body)
            assert sent.status_code==200,sent.text
            receipt=sent.json();assert receipt['revision']==1 and receipt['inference_started'] is False
            assert (await owner.post(path,json=body)).json()==receipt
            read=await owner.get(path+'/changes/web-budget')
            assert read.json()==receipt and read.headers['cache-control']=='no-store'
            assert (await owner.get(path)).json()['policy']['revision']==1
            assert (await owner.get(path)).json()['auxiliary']['policy']=={'operation_limit':30,'cpu_ms_limit':90000}
            assert (await owner.post(path,json={**body,'operation_key':'stale'})).status_code==409
            assert (await owner.post(path,json={**body,'operation_key':'bad','turn_limit':True})).status_code==422
            assert (await owner.get('/api/projects/202/work-budget/changes/web-budget')).status_code==404
    assert coordination.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0]==0
    assert coordination.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==0


@pytest.mark.timeout(180)
async def test_owned_explicit_budget_change_then_new_request_uses_new_capacity(owned_config):
    """The actual host sends no turn on the policy change; a separately submitted owner request uses increased capacity after the original rejection."""
    from backend.tests.runtime.test_source_repair import app_for_sources

    c=owned_config;c.settings['project_token_limit']=999;c.path.write_text(json.dumps(c.settings))
    _app,runtime=app_for_sources()
    async with runtime:
        original=await runtime.submit(c.s.c.spec,repository_id=11);await runtime.wait(original.run_id)
        assert runtime.store.get(101,original.run_id).issue['code']=='project_budget_exhausted'
        receipt=ProjectBudgetPolicies(runtime.store).update(101,operation_key='owner-extension',expected_revision=0,turn_limit=2,token_limit=2000)
        assert receipt['inference_started'] is False
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==0
        assert not list(c.s.control.glob('native-state/*/home/fixture-turn.json'))
        fresh=await runtime.submit(replace(c.s.c.spec,operation_key='new-authorized-work'),repository_id=11);await runtime.wait(fresh.run_id)
        assert runtime.store.get(101,original.run_id).status=='failed'
        assert runtime.store.get(101,fresh.run_id).status=='needs_review'
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==1
        assert RuntimeHistory(c.s.c.database).budget(101)['policy']=={'turn_limit':2,'token_limit':2000,'revision':1}
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_result_acceptances').fetchone()[0]==0
        assert c.s.c.conn.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0]==0
