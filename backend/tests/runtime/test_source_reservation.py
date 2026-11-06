"""Ending a closed administrative source reservation preserves user Git and makes a separate explicit adoption possible without reviving old writers."""

import asyncio
import json

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config


async def test_release_preserves_owner_history_and_allows_new_adoption_without_retargeting_old_commands(owned_config,monkeypatch):
    """A live source cannot be released; after actual Stop, one original release allows adoption while old replay/repair/observe cannot withdraw the new owner or change files."""
    from backend.git.source_executor import SourceGitExecutor
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.tests.runtime.test_source_repair import app_for_sources
    from backend.tests.runtime.test_workspace_delivery import owner_client
    from backend.tests.runtime.test_owned_source_setup import git

    c=owned_config;app,runtime=app_for_sources();original=SourceGitExecutor.stage;started=asyncio.Event();adopting=asyncio.Event();finish=asyncio.Event()
    async def hold(self,stage):
        """Hold only real original owners between fixed stages, without replacing Git results or physical retirement receipts."""
        if self.request.name=='original' and stage=='commit':started.set();await asyncio.Event().wait()
        if self.request.name=='adoptada' and stage=='head':adopting.set();await finish.wait()
        return await original(self,stage)
    monkeypatch.setattr(SourceGitExecutor,'stage',hold)
    path=c.s.root/'retained';base='/api/projects/202/source-operations';body={'operation_key':'original','mode':'create','name':'original','path':str(path),'branch':'main'}
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base,json=body)).status_code==202
        await asyncio.wait_for(started.wait(),10);value=(await owner.get(base+'/original')).json()
        release={'release_key':'close-original-reservation','operation_id':value['operation_id'],'fence':value['fence']}
        assert (await owner.post(base+'/original/release',json=release)).status_code==409
        assert (await owner.post(base+'/original/stop',json={'operation_id':value['operation_id'],'fence':value['fence']})).status_code==200
        (path/'work.txt').write_text('owner history:137\n');git(path,'add','work.txt');git(path,'-c','user.name=Owner','-c','user.email=owner@localhost','commit','-m','Owner history must survive')
        head=git(path,'rev-parse','HEAD');config=(path/'.git/config').read_bytes();inode=path.stat().st_ino
        adopt={'operation_key':'new-adoption','mode':'adopt','name':'adoptada','path':str(path)}
        assert (await owner.post(base,json=adopt)).status_code==409
        runtime.sources.records.prepare_repair(202,'original',repair_key='old-repair',operation_id=value['operation_id'],fence=value['fence'])
        assert (await owner.post(base+'/original/release',json={**release,'fence':value['fence']+1})).status_code==409
        response=await owner.post(base+'/original/release',json=release)
        assert response.status_code==200,response.text
        released=response.json();assert released['reservation_released'] and not released['requires_reconciliation']
        assert released['repository_id'] is None and released['receipt'] is None
        assert released['reservation_release']['release_key']==release['release_key']
        assert (await owner.post(base,json=adopt)).status_code==202
        await asyncio.wait_for(adopting.wait(),10)
        control=runtime.sources._owners[(202,'new-adoption')]
        assert (await owner.post(base+'/original/release',json=release)).json()==released
        assert not control.owner.broker._withdrawn.is_set()
        with WitnessedAuthorityJournal(**c.settings['authority']) as journal:
            assert journal.load().records['broker:active']==control.owner.broker.grant_id
        assert (await owner.post(base+'/original/repair',json={'repair_key':'old-repair','operation_id':value['operation_id'],'fence':value['fence']})).status_code==409
        assert (await owner.post(base+'/original/observe',json={'operation_id':value['operation_id'],'fence':value['fence']})).status_code==409
        assert (await owner.post(base,json=body)).json()['reservation_released'] is True
        assert not control.owner.broker._withdrawn.is_set()
        finish.set();await runtime.sources.wait(202,'new-adoption')
        adopted=(await owner.get(base+'/new-adoption')).json();assert adopted['status']=='completed' and adopted['observation']['head_sha']==head
        assert (await owner.post('/api/projects/202/stop')).status_code==200
        assert (await owner.get(base+'/original')).json()['reservation_released'] is True
        assert (await owner.delete('/api/projects/202')).status_code==409
        assert path.stat().st_ino==inode and (path/'.git/config').read_bytes()==config and git(path,'rev-parse','HEAD')==head
        assert (path/'work.txt').read_text()=='owner history:137\n'
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0


async def test_release_never_accepts_missing_closure_or_caller_supplied_proof(owned_config):
    """A real admitted but unclosed administrative owner is not released from directory absence or a body containing a fake closure claim."""
    from backend.git.source_operations import SourceRequest
    from backend.tests.runtime.test_source_repair import app_for_sources
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;app,runtime=app_for_sources();records=runtime.sources.records
    records.prepare(202,'unknown',SourceRequest(mode='create',name='unknown',path=str(c.s.root/'unknown'),branch='main'))
    lease=records.claim(202,'unknown','original-unclosed-owner');records.uncertain(lease)
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        row=records.read(202,'unknown');body={'release_key':'do-not-guess','operation_id':row['operation_id'],'fence':row['fence']};base='/api/projects/202/source-operations/unknown/release'
        assert (await owner.post(base,json={**body,'domain_removed':True})).status_code==422
        result=await owner.post(base,json=body);assert result.status_code==409,result.text
        assert records.read(202,'unknown').get('reservation_release') is None
        assert not (c.s.root/'unknown').exists()


async def test_never_claimed_source_can_be_closed_without_a_synthetic_original_domain(owned_config):
    """Stop and release of a planned intent retain its never-claimed proof, create no folder and make old repair authority unusable."""
    from backend.git.source_operations import SourceRequest
    from backend.tests.runtime.test_source_repair import app_for_sources
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;app,runtime=app_for_sources();records=runtime.sources.records
    row=records.prepare(202,'unused',SourceRequest(mode='create',name='unused',path=str(c.s.root/'unused'),branch='main'));scope={'operation_id':row['operation_id'],'fence':row['fence']};base='/api/projects/202/source-operations/unused'
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base+'/stop',json=scope)).status_code==200
        value=await owner.post(base+'/release',json={'release_key':'close-unused',**scope});assert value.status_code==200,value.text
        saved=records.read(202,'unused');assert saved['owner'] is None and saved['attempt_id'] is None and saved.get('domain') is None
        assert saved['closure']['never_claimed'] and saved['reservation_release']['closure_kind']=='never_claimed'
        assert not (c.s.root/'unused').exists()


async def test_saved_repair_cancelled_before_scheduling_resumes_the_same_authorization_once(owned_config,monkeypatch):
    """A cancelled real SQL-to-HTTP handoff can replay an unclaimed repair at the same original fence; an admitted or completed writer is never reissued."""
    import threading
    from backend.git.source_executor import SourceGitExecutor
    from backend.tests.runtime.test_source_repair import app_for_sources
    from backend.tests.runtime.test_workspace_delivery import owner_client
    from backend.tests.runtime.test_owned_source_setup import git

    c=owned_config;app,runtime=app_for_sources();started=asyncio.Event();stage=SourceGitExecutor.stage
    async def held_commit(self,name):
        """Stop the actual original owner between successful init and any initial commit."""
        if name=='commit':started.set();await asyncio.Event().wait()
        return await stage(self,name)
    monkeypatch.setattr(SourceGitExecutor,'stage',held_commit)
    base='/api/projects/202/source-operations/handoff';body={'operation_key':'handoff','mode':'create','name':'handoff','path':str(c.s.root/'handoff'),'branch':'main'}
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base.rsplit('/',1)[0],json=body)).status_code==202
        await asyncio.wait_for(started.wait(),10);first=(await owner.get(base)).json();scope={'operation_id':first['operation_id'],'fence':first['fence']}
        assert (await owner.post(base+'/stop',json=scope)).status_code==200
        actual=runtime.sources.records.prepare_repair;entered=threading.Event();release=threading.Event()
        def held_prepare(*args,**kwargs):
            """Retain the real committed authorization at its thread handoff, without fabricating admission or a worker receipt."""
            result=actual(*args,**kwargs);entered.set();assert release.wait(10);return result
        monkeypatch.setattr(runtime.sources.records,'prepare_repair',held_prepare)
        repair={'repair_key':'original-saved-repair',**scope};request=asyncio.create_task(owner.post(base+'/repair',json=repair))
        try:
            assert await asyncio.to_thread(entered.wait,5)
            request.cancel()
        finally:release.set()
        with pytest.raises(asyncio.CancelledError):await request
        saved=runtime.sources.records.read(202,'handoff')
        assert saved['fence']==scope['fence'] and saved.get('repair') is None and len(saved['repair_commands'])==1
        monkeypatch.setattr(runtime.sources.records,'prepare_repair',actual)
        result=await owner.post(base+'/repair',json=repair);assert result.status_code==202,result.text
        await runtime.sources.wait(202,'handoff');complete=(await owner.get(base)).json();assert complete['status']=='completed',complete
        assert complete['receipt']['repair_key']==repair['repair_key']
        assert (await owner.post(base+'/repair',json=repair)).json()==complete
        assert len(runtime.sources.records.read(202,'handoff')['history'])==1
        assert len(runtime.sources.records.read(202,'handoff')['repair_commands'])==1
        assert git(c.s.root/'handoff','rev-list','--count','HEAD')=='1'
