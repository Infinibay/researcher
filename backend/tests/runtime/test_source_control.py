"""Source Stop must close its original actual Git domain before waiting for SQLite; local closure never proves remote handler termination."""

import asyncio

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414
from backend.tests.runtime.test_owned_remote_transport import tls_remote as tls_remote  # noqa: PLC0414


async def physical_before_sql_release(control):
    """Observe the actual original broker's returned kernel DomainClosure; journal sealing is checked after persistence drains, without polling its mutation lock."""
    while control.owner.broker._physical_closed is None:
        await asyncio.sleep(.01)
    return control.owner.broker._physical_closed


@pytest.mark.parametrize('control', ['individual', 'application', 'project_observed', 'project_bodyless'])
@pytest.mark.timeout(90)
async def test_source_stop_retires_actual_clone_before_sqlite_intent_can_commit(owned_config, tls_remote, tmp_path, control):
    """A real TLS clone remains blocked at its server while its exact local kernel domain closes despite an unrelated source-store writer."""
    from dataclasses import replace

    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.git.source_operations import SourceRequest
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig
    from backend.tests.runtime.test_owned_source_setup import git

    c = owned_config
    seed = tmp_path / 'seed'
    seed.mkdir()
    git(seed, 'init', '-b', 'main')
    (seed / 'fact.txt').write_text('137')
    git(seed, 'add', 'fact.txt')
    git(seed, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-m', 'Controlled source')
    git(seed, 'push', str(tls_remote.repo), 'main')
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    network = NativeNetwork.inspect(resolver='/etc/resolv.conf', ca_bundle=tls_remote.cert)
    transport = RemoteTransportConfig(tls_remote.origin + '/api/v1', 'fixture-user', tls_remote.token_file, network)
    runtime.runtime = replace(runtime.runtime, remote_transport=transport)
    tls_remote.hold_clone = True
    await runtime.__aenter__()
    sources = runtime.sources
    await sources.submit(202, 'held-clone', SourceRequest(mode='clone', name='held-clone', path=str(c.s.root / 'held-clone'), remote_url=tls_remote.origin + '/owner/repo.git', use_configured_auth=True))
    assert await asyncio.to_thread(tls_remote.entered.wait, 10)
    row = sources.records.read(202, 'held-clone')
    grant_id = row['domain']['grant_id']
    original = sources._owners[(202,'held-clone')]
    from types import SimpleNamespace

    from backend.api.routes.projects import StopObservedProject, _workspace, stop_project

    request = SimpleNamespace(app=app)
    packet = {'operation_key':'stop-held-project', **_workspace(request).state(202)['stop']}
    c.s.c.conn.execute('BEGIN IMMEDIATE')
    if control == 'individual':
        stop = asyncio.create_task(sources.stop(202, 'held-clone', operation_id=row['operation_id'], fence=row['fence']))
    elif control == 'application':
        stop = asyncio.create_task(runtime.__aexit__(None, None, None))
    else:
        body = StopObservedProject(**packet) if control == 'project_observed' else None
        stop = asyncio.create_task(stop_project(202, request, body))
    try:
        from dataclasses import asdict
        from pathlib import Path

        from backend.runtime.contracts import RunConflict

        if control == 'individual':
            with pytest.raises(RunConflict):
                await asyncio.wait_for(sources.stop(202, 'held-clone', operation_id=row['operation_id'], fence=row['fence'] + 1), .5)
            assert not original.owner.broker._withdrawn.is_set()
            assert 'populated 1' in (Path(row['domain']['path'])/'cgroup.events').read_text()

        closure = await asyncio.wait_for(physical_before_sql_release(original), 2)
        assert closure.removed and asdict(closure.identity) == row['domain']['identity']
        assert not stop.done(), 'The intent still awaits the actual SQLite writer'
        assert not tls_remote.finished.is_set(), 'Local client closure cannot acknowledge remote server termination'
    finally:
        c.s.c.conn.rollback()
        tls_remote.release.set()
        await asyncio.wait_for(stop, 15)
        if control != 'application':
            await runtime.__aexit__(None, None, None)
    saved = sources.records.read(202, 'held-clone')
    assert saved['status'] == 'stopped' and saved['closure']['domain_removed']
    assert all(peer['state'] == 'closed' for peer in saved['peers'].values())
    from backend.runtime.authority_journal import WitnessedAuthorityJournal

    with WitnessedAuthorityJournal(**c.settings['authority']) as journal:
        grant = journal.load().records['broker:grant:' + grant_id]
        assert grant['state'] == 'retired' and grant['domain_removed']
        assert grant['attempt_id'] == row['attempt_id'] and grant['source_operation_id'] == row['operation_id']
    assert tls_remote.git_writes == 0 and not tls_remote.posts
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0


@pytest.mark.timeout(90)
async def test_project_stop_receipt_replay_cannot_withdraw_a_new_held_source(owned_config, tls_remote, tmp_path):
    """The exact prior project Stop returns its old receipt while SQLite is busy and another actual source clone remains alive, never borrowing the new owner."""
    import json
    from dataclasses import replace
    from pathlib import Path
    from types import SimpleNamespace

    from backend.api.main import create_app
    from backend.api.routes.projects import StopObservedProject, _workspace, stop_project
    from backend.api.runtime_dependencies import configured_runtime
    from backend.git.source_operations import SourceRequest
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig
    from backend.tests.runtime.test_owned_source_setup import git

    c=owned_config;seed=tmp_path/'seed';seed.mkdir()
    git(seed,'init','-b','main');(seed/'fact.txt').write_text('137');git(seed,'add','fact.txt')
    git(seed,'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-m','Original source')
    git(seed,'push',str(tls_remote.repo),'main')
    app=create_app();runtime=configured_runtime(app.state.live_grants,app=app);app.state.runtime_service=runtime
    network=NativeNetwork.inspect(resolver='/etc/resolv.conf',ca_bundle=tls_remote.cert)
    runtime.runtime=replace(runtime.runtime,remote_transport=RemoteTransportConfig(tls_remote.origin+'/api/v1','fixture-user',tls_remote.token_file,network))
    request=SimpleNamespace(app=app);tls_remote.hold_clone=True
    async with runtime:
        for name in ('original-clone','later-clone'):
            await runtime.sources.submit(202,name,SourceRequest(mode='clone',name=name,path=str(c.s.root/name),remote_url=tls_remote.origin+'/owner/repo.git',use_configured_auth=True))
            assert await asyncio.to_thread(tls_remote.entered.wait,10)
            if name == 'original-clone':
                body=StopObservedProject(operation_key='original-project-stop',**_workspace(request).state(202)['stop'])
                first=await stop_project(202,request,body)
                tls_remote.release.set()
                assert await asyncio.to_thread(tls_remote.finished.wait,5)
                tls_remote.entered.clear();tls_remote.finished.clear();tls_remote.release.clear()
        sources=runtime.sources;row=sources.records.read(202,'later-clone')
        original=sources._owners[(202,'later-clone')]
        c.s.c.conn.execute('BEGIN IMMEDIATE')
        try:
            replay=await asyncio.wait_for(stop_project(202,request,body),1)
            assert json.loads(replay.body)==json.loads(first.body)
            assert not original.owner.broker._withdrawn.is_set()
            assert 'populated 1' in (Path(row['domain']['path'])/'cgroup.events').read_text()
        finally:
            c.s.c.conn.rollback()
            tls_remote.release.set()
        await sources.stop(202,'later-clone',operation_id=row['operation_id'],fence=row['fence'])
    assert tls_remote.git_writes==0 and not tls_remote.posts
