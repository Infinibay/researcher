"""Project selection uses actual activity and exact original decisions; pure storage fixtures here do not prove physical worker closure."""

from dataclasses import replace

import pytest

from backend.runtime.contracts import RunConflict
from backend.runtime.workspaces import WorkspaceRegistry


def workspace(s):
    """Use a real bounded source root and explicit observed absence of registered legacy workers in these synthetic storage tests."""
    from backend.planning.project_workspace import ProjectWorkspace

    return ProjectWorkspace(s.c.store, workspaces=WorkspaceRegistry(s.c.database, s.root), legacy_active=lambda _: False)


def test_workspace_observes_queued_work_even_when_project_label_is_new(service_setup):
    """Metadata never stands in for actual run state, and simply reading a project never starts its queued original work."""
    s = service_setup
    run = s.c.store.admit(s.c.spec, binding=WorkspaceRegistry(s.c.database, s.root).bind(101, 11))
    state = workspace(s).state(101)
    assert state['project']['status'] == 'new'
    assert [r['run_id'] for r in state['activity']] == [run.run_id]
    assert state['sources'][0]['availability'] == 'available'
    assert state['stop']['task_id'] == 1001
    assert s.c.store.get(101, run.run_id).status == 'queued'


def test_registered_source_is_explicit_and_never_initializes_or_retargets_git(service_setup):
    """A fresh project can adopt an existing managed directory with an idempotent resource identity, preserving every file and unrelated registration."""
    s = service_setup
    target = s.root / 'beta'
    target.mkdir()
    (target / 'fact.txt').write_text('137')
    records = workspace(s)
    first = records.register_source(202, name='beta', path=str(target))
    assert records.register_source(202, name='beta', path=str(target)) == first
    assert records.state(202)['sources'][0]['repository_id'] == first['repository_id']
    assert (target / 'fact.txt').read_text() == '137' and not (target / '.git').exists()
    assert s.c.conn.execute('SELECT remote_url FROM repositories WHERE id=?', (first['repository_id'],)).fetchone()[0] is None
    with pytest.raises(RunConflict):
        records.register_source(202, name='alpha-copy', path=str(s.workspace))
    with pytest.raises(RunConflict):
        records.register_source(202, name='escape', path=str(s.root.parent))
    with pytest.raises(RunConflict):
        records.register_source(202, name='beta', path=str(s.workspace))
    assert s.c.conn.execute('SELECT COUNT(*) FROM repositories WHERE project_id=202').fetchone()[0] == 1


def test_offline_source_state_stays_unknown_without_host_root_policy(service_setup):
    """Stored metadata remains readable while directory availability is not claimed without the actual runtime root policy."""
    from backend.planning.project_workspace import ProjectWorkspace

    records = ProjectWorkspace(service_setup.c.store, workspaces=None, legacy_active=lambda _: False)
    state = records.state(101)
    assert not state['runtime_available'] and state['sources'][0]['availability'] == 'unknown'
    with pytest.raises(RunConflict):
        records.register_source(202, name='unknown-root', path=str(service_setup.root))


def test_stop_freezes_targets_and_pauses_dispatch_before_receipt_without_retargeting_replay(service_setup):
    """Atomic durable withdrawal survives response loss; original receipt recovery must not cancel a newer task or resume a graph."""
    from backend.tests.runtime.test_plan_execution import accepted_plan, authorize

    s, plan, graph = accepted_plan(service_setup, research_only=True)
    executions, receipt = authorize(s, plan)
    spec, binding = executions.prepare(receipt['execution_id'], graph['tasks']['learn'])
    run = s.c.store.admit(spec, binding=binding)
    records = workspace(s)
    observed = records.state(101)['stop']
    body = {'operation_key':'stop-observed-project', **observed}
    stopped, created = records.request_stop(101, **body)
    assert created and stopped['run_ids'] == [run.run_id]
    assert stopped['closure'] == 'unconfirmed'
    assert executions.state(101, plan.run_id)['execution']['status'] == 'paused'
    assert s.c.store.get(101, run.run_id).status == 'cancelled'
    newer = s.c.store.admit(replace(s.c.spec,task_id=1002,context_version=s.c.store.context_snapshot(101,1002)['context_version'],operation_key='later-work'), binding=binding)
    again, created = records.request_stop(101, **body)
    assert again == stopped and not created
    assert s.c.store.get(101, newer.run_id).status == 'queued'
    with pytest.raises(RunConflict):
        records.request_stop(101, **{**body,'operation_key':'stale-new-stop'})


async def test_owner_workspace_registration_and_history_deletion_guard(service_setup):
    """Actual owner HTTP/CSRF checks scope and strict source fields, and denies deleting native history even without a running metadata label."""
    from types import SimpleNamespace

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s = service_setup
    runtime = coordinator(s, SimpleNamespace(supported_task_types=('plan','research')))
    app = create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'),runtime_service=runtime)
    target = s.root / 'beta'
    target.mkdir()
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        creation = {'name':'Gamma','description':'New exact project scope','operation_key':'create-original-project'}
        first = await owner.post('/api/projects',json=creation)
        second = await owner.post('/api/projects',json=creation)
        assert first.status_code == 201 and first.json()['id'] == second.json()['id']
        assert first.json()['creation']['request'] == creation
        assert (await owner.post('/api/projects',json={**creation,'description':'Different intent'})).status_code == 409
        view = await owner.get('/api/projects/202/workspace')
        assert view.status_code == 200, view.text
        assert view.headers['cache-control'] == 'no-store'
        scope = view.json()['metadata_sha256']
        assert (await owner.put('/api/projects/202',json={'description':'A revised purpose','expected_scope_sha256':scope})).status_code == 200
        assert (await owner.put('/api/projects/202',json={'description':'Overwrite stale view','expected_scope_sha256':scope})).status_code == 409
        path = '/api/projects/202/sources'
        assert (await owner.post(path,json={'name':'beta','path':str(target),'remote_url':'https://not-authorized'})).status_code == 422
        assert (await owner.post(path,json={'name':'beta','path':str(target)},headers={'X-Researcher-CSRF':'wrong'})).status_code == 403
        registered = await owner.post(path,json={'name':'beta','path':str(target)})
        assert registered.status_code == 200, registered.text
        assert (await owner.post(path,json={'name':'beta','path':str(target)})).json() == registered.json()
        run = s.c.store.admit(s.c.spec, binding=WorkspaceRegistry(s.c.database,s.root).bind(101,11))
        assert (await owner.delete('/api/projects/101')).status_code == 409
        assert s.c.store.get(101,run.run_id).status == 'queued'
        observed = (await owner.get('/api/projects/101/workspace')).json()['stop']
        stop_body = {'operation_key':'http-stop-original',**observed}
        stopped = await owner.post('/api/projects/101/stop',json=stop_body)
        assert stopped.status_code == 200, stopped.text
        later = s.c.store.admit(replace(s.c.spec,task_id=1002,context_version=s.c.store.context_snapshot(101,1002)['context_version'],operation_key='later-after-http-stop'),binding=runtime.workspaces.bind(101,11))
        assert (await owner.post('/api/projects/101/stop',json=stop_body)).json() == stopped.json()
        assert s.c.store.get(101,later.run_id).status == 'queued'
        # A genuinely unused project can still be removed; history protection
        # must not leave the explicit owner deletion permanently broken.
        s.c.conn.execute("INSERT INTO agent_performance(agent_id,role)VALUES('shared-global-agent','research')")
        s.c.conn.commit()
        deleted = await owner.delete(f"/api/projects/{first.json()['id']}")
        assert deleted.status_code == 204, deleted.text
        assert (await owner.get(f"/api/projects/{first.json()['id']}")).status_code == 404
        assert s.c.conn.execute("SELECT 1 FROM agent_performance WHERE agent_id='shared-global-agent'").fetchone()
