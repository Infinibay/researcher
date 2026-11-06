"""Explicit owner repairs exercise retained actual Git, original process closure and preservation without native tasks or destructive retries."""

import asyncio
import json

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config
from backend.tests.runtime.test_owned_remote_transport import tls_remote as tls_remote


def app_for_sources():
    """Construct the real configured owner app for isolated source operations, without model or tool inference."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime

    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    runtime=configured_runtime(app.state.live_grants,app=app)
    app.state.runtime_service=runtime
    return app,runtime


@pytest.mark.parametrize('interruption',['before_first_git','after_init'])
async def test_explicit_repair_finishes_initial_git_and_preserves_user_files(owned_config,monkeypatch,interruption):
    """Repair completes an unborn source after real Stop, including an unused original domain, without overwriting an added file or fabricating task authority."""
    from backend.git.source_executor import SourceGitExecutor
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.tests.runtime.test_owned_source_setup import git
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;app,runtime=app_for_sources();entered=asyncio.Event();repair_entered=asyncio.Event();allow_repair=asyncio.Event();original=SourceGitExecutor.stage
    async def interrupt(self,stage):
        """Hold the real original owner before its first command or initial commit; repair uses a separately authorized fixed stage."""
        if not self.records.read(202,'repair-local').get('repair') and stage==('init' if interruption=='before_first_git' else 'commit'):
            entered.set();await asyncio.Event().wait()
        if stage=='repair':
            repair_entered.set();await allow_repair.wait()
        return await original(self,stage)
    monkeypatch.setattr(SourceGitExecutor,'stage',interrupt)
    target=c.s.root/'repair-local';body={'operation_key':'repair-local','mode':'create','name':'repair-local','path':str(target),'branch':'main'};base='/api/projects/202/source-operations/repair-local'
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base.rsplit('/',1)[0],json=body)).status_code==202
        await asyncio.wait_for(entered.wait(),10)
        first=(await owner.get(base)).json()
        assert (await owner.post(base+'/stop',json={'operation_id':first['operation_id'],'fence':first['fence']})).status_code==200
        before=runtime.sources.records.read(202,'repair-local')
        (target/'owner-notes.txt').write_text('Keep this work: 137\n')
        config=(target/'.git/config').read_bytes() if (target/'.git/config').exists() else None
        repair={'repair_key':'finish-original-setup','operation_id':first['operation_id'],'fence':first['fence']}
        response=await owner.post(base+'/repair',json=repair)
        assert response.status_code==202,response.text
        await asyncio.wait_for(repair_entered.wait(),10)
        replay=await owner.post(base+'/repair',json=repair)
        assert replay.status_code==202 and replay.json()['fence']>first['fence']
        allow_repair.set()
        await runtime.sources.wait(202,'repair-local')
        saved=(await owner.get(base)).json()
        assert saved['status']=='completed',saved
        assert saved['observation']['working_tree_clean'] is False
        assert (target/'owner-notes.txt').read_text()=='Keep this work: 137\n'
        assert git(target,'rev-list','--count','HEAD')=='1' and git(target,'ls-tree','-r','HEAD')==''
        if config is not None:assert (target/'.git/config').read_bytes()==config
        assert (await owner.post(base+'/repair',json=repair)).json()==saved
        assert (await owner.post(base+'/repair',json={**repair,'fence':repair['fence']+1})).status_code==409
        history=runtime.sources.records.read(202,'repair-local')['history']
        assert history[0]['attempt_id']==before['attempt_id'] and history[0]['closure']['domain_removed']
        if interruption=='before_first_git':
            with WitnessedAuthorityJournal(**c.settings['authority']) as journal:
                state=journal.load().records;grant=before['domain']['grant_id']
                assert 'broker:grant:'+grant not in state
                assert state['source:unused-domain:'+grant]['domain_removed'] is True
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0


@pytest.mark.parametrize('interruption',['before_clone','before_checkout','before_clone_default'])
async def test_clone_repair_keeps_changed_existing_file_and_restores_only_missing_checkout(owned_config,tls_remote,tmp_path,monkeypatch,interruption):
    """A closed original clone can hydrate missing indexed files while preserving modified existing content, index, origin and original full commit."""
    from dataclasses import replace
    from backend.git.source_executor import SourceGitExecutor
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig
    from backend.tests.runtime.test_owned_source_setup import git
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;seed=tmp_path/'seed';seed.mkdir();git(seed,'init','-b','main');(seed/'existing.txt').write_text('remote version');(seed/'missing.txt').write_text('from original remote');git(seed,'add','.')
    git(seed,'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-m','Repair fixture');git(seed,'push',str(tls_remote.repo),'main')
    if interruption=='before_clone_default':git(tls_remote.repo,'symbolic-ref','HEAD','refs/heads/main')
    app,runtime=app_for_sources();transport=RemoteTransportConfig(tls_remote.origin+'/api/v1','fixture-user',tls_remote.token_file,NativeNetwork.inspect(resolver='/etc/resolv.conf',ca_bundle=tls_remote.cert));runtime.runtime=replace(runtime.runtime,remote_transport=transport)
    entered=asyncio.Event();original=SourceGitExecutor.stage
    async def before_checkout(self,stage):
        """Pause the actual clone after fetch/index preparation but before any checkout writes."""
        if not self.records.read(202,'repair-clone').get('repair') and stage==('checkout' if interruption=='before_checkout' else 'clone'):entered.set();await asyncio.Event().wait()
        return await original(self,stage)
    monkeypatch.setattr(SourceGitExecutor,'stage',before_checkout)
    target=c.s.root/'repair-clone';body={'operation_key':'repair-clone','mode':'clone','name':'repair-clone','path':str(target),'remote_url':tls_remote.origin+'/owner/repo.git','branch':None if interruption=='before_clone_default' else 'main','use_configured_auth':True};base='/api/projects/202/source-operations/repair-clone'
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base.rsplit('/',1)[0],json=body)).status_code==202
        await asyncio.wait_for(entered.wait(),15);first=(await owner.get(base)).json();assert (await owner.post(base+'/stop',json={'operation_id':first['operation_id'],'fence':first['fence']})).status_code==200
        (target/'existing.txt').write_text('owner work must survive');config=(target/'.git/config').read_bytes() if (target/'.git/config').exists() else None;index=(target/'.git/index').read_bytes() if (target/'.git/index').exists() else None;head=git(seed,'rev-parse','HEAD')
        assert (await owner.post(base+'/observe')).status_code==202
        await runtime.sources.wait(202,'repair-clone')
        first=(await owner.get(base)).json()
        assert first['status']=='needs_reconciliation' and first['repository_id'] is None, 'Readonly inspection must not register an unfinished checkout as owner deletions'
        repaired=await owner.post(base+'/repair',json={'repair_key':'hydrate-original-clone','operation_id':first['operation_id'],'fence':first['fence']});assert repaired.status_code==202,repaired.text
        await runtime.sources.wait(202,'repair-clone');saved=(await owner.get(base)).json();assert saved['status']=='completed',saved
        assert (target/'existing.txt').read_text()=='owner work must survive' and (target/'missing.txt').read_text()=='from original remote'
        assert git(target,'rev-parse','HEAD')==head
        if config is not None:assert (target/'.git/config').read_bytes()==config
        if index is not None:assert (target/'.git/index').read_bytes()==index
        assert saved['observation']['head_sha']==head and saved['observation']['working_tree_clean'] is False
    assert tls_remote.git_writes==0 and not tls_remote.posts
    assert tls_remote.token not in json.dumps(runtime.sources.records.read(202,'repair-clone'))


@pytest.mark.parametrize('handoff',['claim','allocate'])
async def test_early_cancelled_source_handoff_can_explicitly_continue_without_claiming_a_missing_domain(owned_config,monkeypatch,handoff):
    """A real SQL owner/allocation result lost to cancellation is drained and recorded as never entering a domain, then a separate repair can safely allocate or reuse it."""
    import threading
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;app,runtime=app_for_sources();records=runtime.sources.records;entered=threading.Event();release=threading.Event();actual=getattr(records,handoff)
    def hold(*args,**kwargs):
        """Hold the actual committed original handoff, preserving its identity instead of replacing its SQL or filesystem work."""
        result=actual(*args,**kwargs);entered.set();assert release.wait(10);return result
    monkeypatch.setattr(records,handoff,hold)
    target=c.s.root/'early';body={'operation_key':'early','mode':'create','name':'early','path':str(target),'branch':'main'};base='/api/projects/202/source-operations/early'
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base.rsplit('/',1)[0],json=body)).status_code==202
        assert await asyncio.to_thread(entered.wait,5)
        first=(await owner.get(base)).json()
        stopping=asyncio.create_task(owner.post(base+'/stop',json={'operation_id':first['operation_id'],'fence':first['fence']}))
        try:
            async def cancelled():
                """Wait for the actual owning task's cancellation before releasing the original SQL result."""
                while not runtime.sources._workers[(202,'early')].cancelling():await asyncio.sleep(.01)
            await asyncio.wait_for(cancelled(),3)
        finally:release.set()
        assert (await stopping).status_code==200
        closed=records.read(202,'early')
        assert closed['closure']['no_domain_opened'] and closed.get('domain') is None
        monkeypatch.setattr(records,handoff,actual)
        assert (await owner.post(base+'/repair',json={'repair_key':'continue-early','operation_id':first['operation_id'],'fence':first['fence']})).status_code==202
        await runtime.sources.wait(202,'early')
        assert (await owner.get(base)).json()['status']=='completed'
    assert not list(c.parent.glob('researcher-source-setup-*'))


async def test_explicit_repair_can_start_a_source_stopped_before_owner_admission(owned_config,monkeypatch):
    """A planned source cancelled before any lease may explicitly continue without inventing an original owner, attempt or physical domain."""
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;app,runtime=app_for_sources();sources=runtime.sources;entered=asyncio.Event();run=sources._run
    async def before_worker(*_args,**_kwargs):
        """Hold only scheduling before the real worker starts; Stop cancels the real task before any administrative owner admission."""
        entered.set();await asyncio.Event().wait()
    monkeypatch.setattr(sources,'_run',before_worker)
    base='/api/projects/202/source-operations/never-admitted';body={'operation_key':'never-admitted','mode':'create','name':'never-admitted','path':str(c.s.root/'never-admitted'),'branch':'main'}
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base.rsplit('/',1)[0],json=body)).status_code==202
        await asyncio.wait_for(entered.wait(),3);first=(await owner.get(base)).json()
        assert (await owner.post(base+'/stop',json={'operation_id':first['operation_id'],'fence':first['fence']})).status_code==200
        row=sources.records.read(202,'never-admitted')
        assert row['owner'] is None and row['attempt_id'] is None and row.get('domain') is None
        assert row['closure']['never_claimed'] and row['closure']['no_domain_opened']
        monkeypatch.setattr(sources,'_run',run)
        assert (await owner.post(base+'/repair',json={'repair_key':'start-missing-setup','operation_id':first['operation_id'],'fence':first['fence']})).status_code==202
        await sources.wait(202,'never-admitted')
        assert (await owner.get(base)).json()['status']=='completed'
