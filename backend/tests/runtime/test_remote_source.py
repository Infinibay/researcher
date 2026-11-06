"""Actual owner HTTP and verified TLS creation, single-write recovery and honest local Stop for empty remote sources."""

import asyncio
import json
from dataclasses import replace

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config
from backend.tests.runtime.test_owned_remote_transport import tls_remote as tls_remote


@pytest.fixture
def remote_source(tls_remote):
    """Extend the real private-CA server with fixed user/org namespaces and controlled lost/pending creation replies."""
    state = tls_remote
    state.repositories = {}
    state.create_posts = []
    state.read_status = None
    state.drop_create = False
    state.hold_create = False
    state.user_login = 'fixture-user'

    def handle(handler, path, raw):
        """Implement only the documented Forgejo user/org and empty-repository endpoints; expose actual wire effects to assertions."""
        if path == '/api/v1/user':
            handler.reply(200, {'id': 81, 'login': state.user_login})
        elif path == '/api/v1/orgs/research':
            handler.reply(200, {'id': 92, 'name': 'research'})
        elif path.startswith('/api/v1/repos/'):
            if state.read_status:
                handler.reply(state.read_status)
            else:
                record = state.repositories.get(path.removeprefix('/api/v1/repos/'))
                handler.reply(200 if record else 404, record)
        elif handler.command == 'POST' and path in ('/api/v1/user/repos', '/api/v1/orgs/research/repos'):
            payload = json.loads(raw)
            owner, owner_id = ('fixture-user', 81) if path.endswith('/user/repos') else ('research', 92)
            name = owner + '/' + payload['name']
            state.create_posts.append((path, payload))
            assert payload['auto_init'] is False and type(payload['private']) is bool
            record = {'id': 301, 'full_name': name, 'name': payload['name'], 'private': payload['private'], 'description': payload['description'], 'owner': {'id': owner_id, 'login': owner}, 'clone_url': state.origin + '/' + name + '.git'}
            if state.hold_create:
                state.entered.set()
                state.release.wait(20)
            state.repositories[name] = record
            state.finished.set()
            if not state.drop_create:
                handler.reply(201, record)
        else:
            return False
        return True

    state.source_handler = handle
    return state


def configured_app(c, remote, tmp_path):
    """Use the real owner service and host transport, with isolated fixture credentials instead of any user remote or model."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.remote_transport import RemoteTransportConfig

    app = create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    runtime = configured_runtime(app.state.live_grants, app=app)
    resolver = tmp_path / 'source-resolv.conf'
    resolver.write_text('nameserver 127.0.0.1\n')
    transport = RemoteTransportConfig(remote.origin + '/api/v1', 'fixture-user', remote.token_file, NativeNetwork.inspect(ca_bundle=remote.cert, resolver=resolver))
    runtime.runtime = replace(runtime.runtime, remote_transport=transport)
    app.state.runtime_service = runtime
    return app, runtime


@pytest.mark.parametrize('namespace,private,drop', [('fixture-user', True, False), ('research', False, False), ('research', True, True)])
async def test_remote_creation_preserves_namespace_visibility_and_single_original_write(owned_config, remote_source, tmp_path, namespace, private, drop):
    """Real REST writes use the selected owner and visibility; replay and lost-response observation cannot create twice or initialize local Git."""
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c, remote = owned_config, remote_source
    app, runtime = configured_app(c, remote, tmp_path)
    remote.drop_create = drop
    before = set(c.s.root.iterdir())
    body = {'operation_key': 'create-empty-remote', 'mode': 'create_remote', 'name': 'empty', 'remote_owner': namespace, 'private': private, 'remote_server': remote.origin + '/api/v1'}
    base = '/api/projects/202/source-operations'
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        options = await owner.get(base)
        assert options.status_code == 200
        assert options.json() == {'remote_server': body['remote_server'], 'remote_username': 'fixture-user'}
        first = await owner.post(base, json=body)
        assert first.status_code == 202, first.text
        await runtime.sources.wait(202, body['operation_key'])
        original = (await owner.get(base + '/' + body['operation_key'])).json()
        if drop:
            assert original['status'] == 'needs_reconciliation'
            assert (await owner.post(base, json=body)).json() == original
            assert (await owner.post(base + '/' + body['operation_key'] + '/observe')).status_code == 202
            await runtime.sources.wait(202, body['operation_key'])
        result = (await owner.get(base + '/' + body['operation_key'])).json()
        assert result['status'] == 'completed', result
        assert result['repository_id'] is None and result['observation'] is None
        assert result['local_closure'] == 'confirmed' and not result['worker_active']
        assert result['receipt']['remote']['full_name'] == namespace + '/empty'
        assert result['receipt']['remote']['private'] is private
        assert result['receipt']['remote']['id'] == 301
        assert (await owner.post(base, json=body)).json() == result
        assert (await owner.post(base, json={**body, 'private': not private})).status_code == 409
        assert (await owner.post(base, json={**body, 'operation_key': 'wrong-server', 'remote_server': 'https://other.example/api/v1'})).status_code == 409
        assert remote.token not in json.dumps(runtime.sources.records.read(202, body['operation_key']))
    assert len(remote.create_posts) == 1 and remote.git_writes == 0 and not remote.posts
    assert remote.create_posts[0][0] == ('/api/v1/user/repos' if namespace == 'fixture-user' else '/api/v1/orgs/research/repos')
    assert set(c.s.root.iterdir()) == before
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0] == 0
    assert c.s.c.conn.execute('SELECT COUNT(*) FROM repositories WHERE name=?', ('empty',)).fetchone()[0] == 0


@pytest.mark.parametrize('failure', ['existing', 'forbidden', 'server_error', 'wrong_user'])
async def test_remote_preflight_errors_never_become_absence_or_namespace_fallback(owned_config, remote_source, tmp_path, failure):
    """A foreign repository, failed read or mismatching authenticated identity cannot authorize creation in either namespace."""
    from backend.tests.runtime.test_workspace_delivery import owner_client

    remote = remote_source
    remote.repositories['research/empty'] = {'id': 44} if failure == 'existing' else None
    remote.read_status = {'forbidden': 403, 'server_error': 500}.get(failure)
    if failure == 'wrong_user':
        remote.user_login = 'different-user'
    app, runtime = configured_app(owned_config, remote, tmp_path)
    body = {'operation_key': 'blocked-remote', 'mode': 'create_remote', 'name': 'empty', 'remote_owner': 'research', 'private': True, 'remote_server': remote.origin + '/api/v1'}
    base = '/api/projects/202/source-operations'
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        assert (await owner.post(base, json=body)).status_code == 202
        await runtime.sources.wait(202, body['operation_key'])
        result = (await owner.get(base + '/' + body['operation_key'])).json()
        assert result['status'] != 'completed' and result['receipt'] is None
        assert (await owner.post(base, json=body)).status_code == 202
        assert not remote.create_posts


@pytest.mark.parametrize('stop_kind', ['individual', 'project_bodyless', 'project_observed'])
async def test_remote_stop_closes_local_transport_but_preserves_unknown_server_outcome(owned_config, remote_source, tmp_path, stop_kind):
    """Actual Stop while POST is pending cannot claim rollback; readonly observation can later recover exactly that single original effect."""
    from backend.tests.runtime.test_workspace_delivery import owner_client

    remote = remote_source
    remote.hold_create = True
    app, runtime = configured_app(owned_config, remote, tmp_path)
    body = {'operation_key': 'stop-remote', 'mode': 'create_remote', 'name': 'empty', 'remote_owner': 'research', 'private': True, 'remote_server': remote.origin + '/api/v1'}
    base = '/api/projects/202/source-operations/stop-remote'
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        assert (await owner.post(base.rsplit('/', 1)[0], json=body)).status_code == 202
        assert await asyncio.to_thread(remote.entered.wait, 10)
        original = (await owner.get(base)).json()
        if stop_kind == 'individual':
            control = runtime.sources._owners[(202, body['operation_key'])].owner
            owned_config.s.c.conn.execute('BEGIN IMMEDIATE')
            stopping = asyncio.create_task(owner.post(base + '/stop', json={'operation_id': original['operation_id'], 'fence': original['fence']}))
            try:
                async def closed_before_sql():
                    """Wait only for this real controller's original close future; no SQL observation or fabricated closure flag is used."""
                    while control._closing is None:
                        await asyncio.sleep(.01)
                    await asyncio.shield(control._closing)
                await asyncio.wait_for(closed_before_sql(), 2)
                assert control.client._client.is_closed and not stopping.done()
                assert not remote.finished.is_set()
            finally:
                owned_config.s.c.conn.rollback()
            result = await stopping
        elif stop_kind == 'project_bodyless':
            result = await owner.post('/api/projects/202/stop')
        else:
            scope = (await owner.get('/api/projects/202/workspace')).json()['stop']
            result = await owner.post('/api/projects/202/stop', json={'operation_key':'stop-original-remote', **scope})
        assert result.status_code == 200, result.text
        stopped = (await owner.get(base)).json()
        assert stopped['local_closure'] == 'confirmed'
        assert stopped['status'] == 'needs_reconciliation' and not stopped['worker_active']
        assert not remote.finished.is_set()
        assert (await owner.post(base + '/observe')).status_code == 202
        await runtime.sources.wait(202, body['operation_key'])
        assert (await owner.get(base)).json()['status'] == 'needs_reconciliation'
        remote.release.set()
        assert await asyncio.to_thread(remote.finished.wait, 10)
        record = remote.repositories['research/empty']
        marker = record['description']
        record['description'] = 'a foreign result is not original creation evidence'
        assert (await owner.post(base + '/observe')).status_code == 202
        await runtime.sources.wait(202, body['operation_key'])
        assert (await owner.get(base)).json()['status'] == 'needs_reconciliation'
        record['description'] = marker
        assert (await owner.post(base + '/observe')).status_code == 202
        await runtime.sources.wait(202, body['operation_key'])
        final = (await owner.get(base)).json()
        assert final['status'] == 'completed'
        assert final['receipt']['completed_after_withdrawal'] is True
    assert len(remote.create_posts) == 1


async def test_cancellation_during_http_owner_handoff_closes_the_original_record_without_requests(owned_config, remote_source, tmp_path, monkeypatch):
    """Cancellation after atomic SQL admission but before the lease returns cannot strand an open client identity or release any HTTP request."""
    import threading

    from backend.git.source_operations import SourceRequest
    from backend.git.source_remote import RemoteSourceRecords, execute_remote_source

    _, runtime = configured_app(owned_config, remote_source, tmp_path)
    records = runtime.sources.records
    records.prepare(202, 'cancel-handoff', SourceRequest(mode='create_remote', name='empty', remote_owner='research', private=True, remote_server=remote_source.origin+'/api/v1'), remote_identity=runtime.runtime.remote_transport.identity)
    entered, release = threading.Event(), threading.Event()
    begin = RemoteSourceRecords.begin

    def held_handoff(self, *args, **kwargs):
        """Hold the real committed lease only at its thread-to-event-loop handoff, without replacing its actual admission or receipt."""
        lease = begin(self, *args, **kwargs)
        entered.set()
        assert release.wait(10)
        return lease

    monkeypatch.setattr(RemoteSourceRecords, 'begin', held_handoff)
    task = asyncio.create_task(execute_remote_source(records, 202, 'cancel-handoff', runtime.runtime.remote_transport))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    row = records.read(202, 'cancel-handoff')
    assert row['http_client']['state'] == 'closed' and row.get('remote_effect') is None
    assert not remote_source.paths and not remote_source.create_posts
