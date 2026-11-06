"""Owner HTTP and actual source-worker lifecycle over real Git and kernel closure, without model turns or user remotes."""

import asyncio

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414
from backend.tests.runtime.test_owned_remote_transport import tls_remote as tls_remote  # noqa: PLC0414


@pytest.mark.timeout(120)
async def test_owner_can_create_observe_and_replay_one_source_operation(owned_config):
    """The actual owner route creates one source asynchronously, while exact replay retains its registration and never creates a native task."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = owned_config
    app = create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    app.state.runtime_service = configured_runtime(app.state.live_grants, app=app)
    body = {'operation_key':'owner-source-create', 'mode':'create', 'name':'owner-source', 'path':str(c.s.root/'owner-source'), 'branch':'main'}
    path = '/api/projects/202/source-operations'
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        first = await owner.post(path, json=body)
        assert first.status_code == 202, first.text
        await app.state.runtime_service.sources.wait(202, body['operation_key'])
        saved = (await owner.get(path+'/'+body['operation_key'])).json()
        assert saved['status'] == 'completed' and saved['repository_id'] > 0
        assert saved['receipt']['observation']['branch'] == 'main'
        assert not saved['worker_active'] and 'peers' not in saved and 'owner' not in saved
        assert (await owner.post(path, json=body)).json() == saved
        assert (await owner.post(path, json={**body, 'branch':'other'})).status_code == 409
        assert (await owner.post('/api/git/repos?project_id=202', json={'name':'unsafe-old-path','local_path':str(c.s.root/'unsafe-old-path')})).status_code == 409
        assert not (c.s.root/'unsafe-old-path').exists()
        assert (await owner.delete('/api/projects/202')).status_code == 409
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] == 3


@pytest.mark.timeout(120)
async def test_source_stop_and_shutdown_close_original_worker_and_retain_partial_git(owned_config, monkeypatch):
    """Stopping after init withdraws the original administrative attempt, proves its local domain closure and preserves the unfinished source on exit."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.git.source_executor import SourceGitExecutor
    from backend.runtime.authority_journal import WitnessedAuthorityJournal
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = owned_config
    app = create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    initialized = asyncio.Event()
    original = SourceGitExecutor.stage

    async def hold_commit(self, stage):
        """Pause the actual worker between fixed Git stages, after real init/peer closure and before any commit effect."""
        if stage == 'commit':
            initialized.set()
            await asyncio.Event().wait()
        return await original(self, stage)

    monkeypatch.setattr(SourceGitExecutor, 'stage', hold_commit)
    path = '/api/projects/202/source-operations'
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        for name in ('explicit-stop', 'project-stop', 'default-project-stop', 'shutdown-stop'):
            initialized.clear()
            body = {'operation_key':name, 'mode':'create', 'name':name, 'path':str(c.s.root/name), 'branch':'main'}
            assert (await owner.post(path, json=body)).status_code == 202
            await asyncio.wait_for(initialized.wait(), 20)
            saved = (await owner.get(path+'/'+name)).json()
            assert saved['status'] == 'running' and saved['worker_active']
            if name == 'explicit-stop':
                stop = {'operation_id':saved['operation_id'], 'fence':saved['fence']}
                assert (await owner.post(path+'/'+name+'/stop', json={**stop,'fence':0})).status_code == 409
                stopped = await owner.post(path+'/'+name+'/stop', json=stop)
                assert stopped.status_code == 200, stopped.text
                assert stopped.json()['status'] == 'stopped' and stopped.json()['local_closure'] == 'confirmed'
                assert not stopped.json()['worker_active']
                assert (await owner.post('/api/projects/202/sources', json={'name':name,'path':body['path']})).status_code == 409
                assert (await owner.post(path, json=body)).json()['status'] == 'stopped'
            elif name == 'project-stop':
                observed = (await owner.get('/api/projects/202/workspace')).json()['stop']
                assert observed is not None and observed['task_id'] is None
                packet = {'operation_key':'stop-source-only-project', **observed}
                stopped = await owner.post('/api/projects/202/stop', json=packet)
                assert stopped.status_code == 200, stopped.text
                assert stopped.json()['source_operations'][0]['operation_key'] == name
                assert (await owner.get(path+'/'+name)).json()['status'] == 'stopped'
                assert (await owner.post('/api/projects/202/stop', json=packet)).json() == stopped.json()
            elif name == 'default-project-stop':
                stopped = await owner.post('/api/projects/202/stop')
                assert stopped.status_code == 200, stopped.text
                assert (await owner.get(path+'/'+name)).json()['status'] == 'stopped'
    assert runtime.sources.records.read(202, 'shutdown-stop')['status'] == 'stopped'
    assert all((c.s.root/name/'.git').is_dir() for name in ('explicit-stop','project-stop','default-project-stop','shutdown-stop'))
    with WitnessedAuthorityJournal(**c.settings['authority']) as journal:
        records = journal.load().records
        assert records['broker:active'] is None
        grants = [value for key,value in records.items() if key.startswith('broker:grant:')]
        assert len(grants) == 4 and all(g['state']=='retired' and g['domain_removed'] for g in grants)
    assert not list(c.parent.glob('researcher-source-setup-*'))


@pytest.mark.timeout(120)
async def test_owner_observes_original_source_after_failed_registration_without_reinitialization(owned_config, monkeypatch):
    """The UI receives a redacted saved uncertainty and can explicitly recover the actual existing initial revision through the owner observation endpoint."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.tests.runtime.test_owned_source_setup import git
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    runtime=configured_runtime(app.state.live_grants,app=app);app.state.runtime_service=runtime
    records=runtime.sources.records;original=records.register

    def fail_registration(*_args):
        """Lose the actual registration reply after Git completed; this private detail must not enter the owner response."""
        raise RuntimeError('fixture-secret-never-expose')

    monkeypatch.setattr(records,'register',fail_registration)
    target=c.s.root/'recover-original'
    base='/api/projects/202/source-operations'
    body={'operation_key':'recover-original','mode':'create','name':'recover-original','path':str(target),'branch':'main'}
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post(base,json=body)).status_code==202
        await runtime.sources.wait(202,'recover-original')
        failed=await owner.get(base+'/recover-original')
        assert failed.json()['status']=='needs_reconciliation'
        assert failed.json()['issue']['code']=='source_result_unconfirmed'
        assert 'fixture-secret-never-expose' not in failed.text
        head=git(target,'rev-parse','HEAD')
        monkeypatch.setattr(records,'register',original)
        assert (await owner.post(base+'/recover-original/observe')).status_code==202
        await runtime.sources.wait(202,'recover-original')
        recovered=(await owner.get(base+'/recover-original')).json()
        assert recovered['status']=='completed' and recovered['receipt']['observation']['head_sha']==head
        assert git(target,'rev-list','--count','HEAD')=='1'
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0


@pytest.mark.timeout(120)
async def test_owner_authenticated_clone_uses_selected_remote_tls_trust(owned_config, tls_remote, tmp_path):
    """The real owner clone uses its configured credential origin and CA, independently of the model runtime's public-network trust configuration."""
    from dataclasses import replace

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig
    from backend.tests.runtime.test_owned_source_setup import git
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c=owned_config;seed=tmp_path/'seed';seed.mkdir()
    git(seed,'init','-b','main');(seed/'fact.txt').write_text('137');git(seed,'add','fact.txt')
    git(seed,'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-m','Controlled remote source')
    git(seed,'push',str(tls_remote.repo),'main')
    app=create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    runtime=configured_runtime(app.state.live_grants,app=app);app.state.runtime_service=runtime
    remote_network=NativeNetwork.inspect(resolver='/etc/resolv.conf',ca_bundle=tls_remote.cert)
    assert remote_network!=runtime.runtime.network
    transport=RemoteTransportConfig(tls_remote.origin+'/api/v1','fixture-user',tls_remote.token_file,remote_network)
    runtime.runtime=replace(runtime.runtime,remote_transport=transport)
    target=c.s.root/'owner-clone';body={'operation_key':'owner-clone','mode':'clone','name':'owner-clone','path':str(target),'remote_url':tls_remote.origin+'/owner/repo.git','use_configured_auth':True}
    async with app.router.lifespan_context(app),owner_client(app) as owner:
        assert (await owner.post('/api/projects/202/source-operations',json=body)).status_code==202
        await runtime.sources.wait(202,'owner-clone')
        result=(await owner.get('/api/projects/202/source-operations/owner-clone')).json()
        assert result['status']=='completed',result
        assert result['receipt']['observation']['head_sha']==git(seed,'rev-parse','HEAD')
        assert (target/'fact.txt').read_text()=='137'
        assert tls_remote.token not in (target/'.git/config').read_text()
        assert tls_remote.token not in str(runtime.sources.records.read(202,'owner-clone'))
    assert tls_remote.git_writes==0 and not tls_remote.posts
