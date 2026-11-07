"""Owner model policy precedence, frozen attempt choices and actual native protocol validation without real inference."""

from dataclasses import replace
import asyncio
import json
import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config


def test_model_scope_precedence_revision_reset_and_project_isolation(coordination):
    """An actor inherits project/global/host explicitly; revisions reject stale writes and reset retains its revision rather than reviving an old edit."""
    from backend.runtime.model_settings import ModelSettings
    from backend.runtime.contracts import RunConflict,RunNotFound
    settings=ModelSettings(coordination.store)
    assert settings.view(101,'researcher-a',host_model='host')['effective']['model']=='host'
    global_=settings.update(expected_revision=0,model='global',reasoning_effort='medium')
    assert global_['revision']==1
    settings.update(project_id=101,expected_revision=0,model='project',reasoning_effort='high')
    actor=settings.update(project_id=101,actor_id='researcher-a',expected_revision=0,model='actor',reasoning_effort='low')
    assert settings.view(101,'researcher-a',host_model='host')['effective']['model']=='actor'
    assert settings.view(101,'other',host_model='host')['effective']['model']=='project'
    assert settings.view(202,'researcher-a',host_model='host')['effective']['model']=='global'
    with pytest.raises(RunConflict):settings.update(project_id=101,actor_id='researcher-a',expected_revision=0,model='stale',reasoning_effort='low')
    reset=settings.update(project_id=101,actor_id='researcher-a',expected_revision=actor['revision'],model=None,reasoning_effort=None)
    assert reset['revision']==2 and reset['profile'] is None
    assert settings.view(101,'researcher-a',host_model='host')['effective']['model']=='project'
    with pytest.raises(RunNotFound):settings.view(999,host_model='host')
    with pytest.raises(ValueError):settings.update(actor_id='unscoped',expected_revision=0,model='actor',reasoning_effort='low')


def test_attempt_model_selection_is_frozen_before_inference_even_after_policy_changes(service_setup):
    """Current policy changes cannot replace an original attempt's model; a later distinct attempt can select the new default."""
    from backend.runtime.model_settings import ModelSettings
    from backend.runtime.contracts import StaleAttempt
    c=service_setup.c;settings=ModelSettings(c.store)
    binding=__import__('backend.runtime.workspaces',fromlist=['WorkspaceRegistry']).WorkspaceRegistry(c.database,service_setup.root).bind(101,11)
    run=c.store.admit(c.spec,binding=binding);lease=c.store.claim(101,run.run_id,'owner')
    first=settings.freeze(lease,host_model='host',host_effort='low')
    settings.update(project_id=101,expected_revision=0,model='changed',reasoning_effort='high')
    assert settings.freeze(lease,host_model='new-host',host_effort='medium')==first
    assert first['model']=='host' and first['source']=='host' and first['attempt_id']==lease.attempt_id
    assert c.store.get(101,run.run_id).model_selection==first
    with pytest.raises(StaleAttempt):settings.freeze(replace(lease,fence=lease.fence+1),host_model='host',host_effort='low')
    assert c.conn.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0]==0
    later=c.store.admit(replace(c.spec,task_id=1002,operation_key='second-model'),binding=binding)
    second=settings.freeze(c.store.claim(101,later.run_id,'other-owner'),host_model='host',host_effort='low')
    assert second['model']=='changed' and second['source']=='project:101'


async def test_native_catalog_checks_requested_model_and_effort_without_sending_a_turn():
    """Actual protocol catalog pages determine eligibility; unsupported pairs fail rather than silently replacing model or effort."""
    from backend.runtime.model_settings import validate_native_model,ModelUnavailable
    class Catalog:
        """Expose only the real RPC request shape required to test catalog pagination and refusal."""
        def __init__(self):
            """Record every catalog request so no thread or turn can be mistaken for validation."""
            self.requests=[]
        async def request(self,method,params):
            """Return two account-catalog pages, with supported effort supplied only by their entries."""
            self.requests.append((method,params));assert method=='model/list'
            return {'data':[{'model':'selected' if params.get('cursor') else 'other','displayName':'Available','supportedReasoningEfforts':[{'reasoningEffort':'medium'}]}],'nextCursor':None if params.get('cursor') else 'next'}
    rpc=Catalog();observed={}
    await validate_native_model(rpc,{'model':'selected','reasoning_effort':'medium'},observed)
    assert len(rpc.requests)==2 and observed['models'][1]['model']=='selected'
    with pytest.raises(ModelUnavailable):await validate_native_model(rpc,{'model':'missing','reasoning_effort':'medium'},{})
    with pytest.raises(ModelUnavailable):await validate_native_model(rpc,{'model':'selected','reasoning_effort':'high'},{})


async def test_codex_session_sends_selected_reasoning_effort_instead_of_fixed_low(tmp_path):
    """The actual child protocol receives the selected effort on turn/start; subscription checks still run before dispatch."""
    from backend.tests.runtime.test_codex_session import session,requests
    native=session(tmp_path);native.reasoning_effort='high'
    async with native:
        await native.run('complete')
    assert next(r for r in requests(tmp_path) if r['method']=='turn/start')['params']['effort']=='high'


async def test_owner_configuration_changes_future_choices_without_retargeting_actual_native_attempt(owned_config,monkeypatch):
    """Actual owner API, SQLite, broker/Ken and child protocol preserve a selected pair while the owner changes future project policy."""
    from backend.runtime import model_settings
    from backend.tests.runtime.test_source_repair import app_for_sources
    from backend.tests.runtime.test_workspace_delivery import owner_client
    c=owned_config;app,runtime=app_for_sources();entered=asyncio.Event();release=asyncio.Event();original=model_settings.validate_native_model
    async def held(rpc,selected,cache):
        """Hold the actual native catalog check after durable selection, without fabricating its account response or thread receipt."""
        entered.set();await release.wait();return await original(rpc,selected,cache)
    monkeypatch.setattr(model_settings,'validate_native_model',held)
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        base='/api/model-settings';first=(await owner.get(base)).json();assert first['effective']['model']=='controlled-only' and first['catalog'] is None
        saved=await owner.put(base,json={'project_id':101,'actor_id':None,'expected_revision':0,'model':'controlled-alt','reasoning_effort':'high'});assert saved.status_code==200,saved.text
        run=await runtime.submit(c.s.c.spec,repository_id=11)
        try:
            await asyncio.wait_for(entered.wait(),15)
            changed=await owner.put(base,json={'project_id':101,'actor_id':None,'expected_revision':1,'model':'controlled-only','reasoning_effort':'low'});assert changed.status_code==200,changed.text
        finally:release.set()
        await runtime.wait(run.run_id);view=runtime.store.get(101,run.run_id)
        assert view.status=='needs_review',view
        assert view.model=='controlled-alt' and view.model_selection['reasoning_effort']=='high' and view.model_selection['revision']==1
        thread=json.loads(next(c.s.control.glob('native-state/*/home/fixture-thread.json')).read_text());turn=json.loads(next(c.s.control.glob('native-state/*/home/fixture-turn.json')).read_text())
        assert thread['model']=='controlled-alt' and turn['effort']=='high'
        actual=(await owner.get(base,params={'project_id':101})).json();assert actual['effective']['model']=='controlled-only' and len(actual['catalog']['models'])==2
        assert (await owner.put(base,json={'project_id':101,'expected_revision':1,'model':'controlled-alt','reasoning_effort':'high'})).status_code==409
        assert (await owner.put(base,json={'expected_revision':0,'model':'controlled-only','reasoning_effort':'low','api_key':'not-allowed'})).status_code==422


async def test_unavailable_model_has_no_thread_turn_or_fallback_and_keeps_original_choice(owned_config):
    """An unavailable owner model is rejected from the actual catalog before thread/dispatch, retaining an actionable issue and the requested selection."""
    from backend.runtime.model_settings import ModelSettings
    from backend.tests.runtime.test_source_repair import app_for_sources
    c=owned_config;app,runtime=app_for_sources()
    ModelSettings(runtime.store).update(project_id=101,expected_revision=0,model='not-in-account',reasoning_effort='high')
    async with runtime:
        run=await runtime.submit(c.s.c.spec,repository_id=11);await runtime.wait(run.run_id);view=runtime.store.get(101,run.run_id)
        assert view.model_selection['model']=='not-in-account' and view.model is None
        assert view.issue['code']=='native_model_unavailable',view
        assert not list(c.s.control.glob('native-state/*/home/fixture-thread.json'))
        assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0]==0


def test_deleted_empty_project_does_not_leave_policy_for_a_recreated_project(coordination):
    """Removing an empty project clears only its future policy, so a reused numeric ID cannot inherit an unrelated old actor choice."""
    from backend.runtime.model_settings import ModelSettings
    c=coordination;settings=ModelSettings(c.store)
    with c.store._transaction(write=True) as conn:conn.execute("INSERT INTO projects(id,name) VALUES(303,'Disposable')")
    settings.update(project_id=303,actor_id='reviewer',expected_revision=0,model='old-model',reasoning_effort='high')
    with c.store._transaction(write=True) as conn:conn.execute('DELETE FROM projects WHERE id=303')
    with c.store._transaction(write=True) as conn:conn.execute("INSERT INTO projects(id,name) VALUES(303,'New project')")
    assert settings.view(303,'reviewer',host_model='host')['effective']['model']=='host'


@pytest.mark.parametrize("scope", [{}, {"project_id": 101}, {"project_id": 101, "actor_id": "reviewer"}])
def test_process_loss_after_setting_write_preserves_original_pair_and_revision(coordination, scope):
    """Kill a separate writer after its real SQL mutation but before commit; preserve the whole original pair and permit one revision-checked retry."""
    import hashlib
    from pathlib import Path
    import subprocess
    import sys
    from backend.runtime import model_settings

    settings = model_settings.ModelSettings(coordination.store)
    original = settings.update(**scope, expected_revision=0, model="original", reasoning_effort="low")
    child = r'''
"""Exit inside the real model-setting transaction without Python cleanup or a committed response."""
import hashlib, json, os, sys
from pathlib import Path
from backend.runtime import model_settings
from backend.runtime.sqlite_runs import SQLiteRunStore
settings = model_settings.ModelSettings(SQLiteRunStore(sys.argv[1]))
read = settings._setting
def checkpoint(conn, key):
    """Stop only after observing the changed row inside the uncommitted writer connection."""
    current = read(conn, key)
    if current['revision'] == 2:
        print(json.dumps({'uncommitted': current, 'source_sha256': hashlib.sha256(Path(model_settings.__file__).read_bytes()).hexdigest()}), flush=True)
        os._exit(73)
    return current
settings._setting = checkpoint
settings.update(**json.loads(sys.argv[2]), expected_revision=1, model='changed', reasoning_effort='high')
raise RuntimeError('The expected pre-commit checkpoint was not reached')
'''
    result = subprocess.run(
        [sys.executable, "-I", "-c", child, str(coordination.database), json.dumps(scope)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 73, result.stderr
    observed = json.loads(result.stdout)
    assert observed["source_sha256"] == hashlib.sha256(Path(model_settings.__file__).read_bytes()).hexdigest()
    assert observed["uncommitted"]["revision"] == 2
    assert observed["uncommitted"]["profile"] == {"model": "changed", "reasoning_effort": "high"}
    assert settings.view(**scope, host_model="host")["setting"] == original
    retried = settings.update(**scope, expected_revision=1, model="changed", reasoning_effort="high")
    assert retried["revision"] == 2 and retried["profile"] == observed["uncommitted"]["profile"]
