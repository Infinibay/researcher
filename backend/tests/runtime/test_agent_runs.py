"""Native owner agent ledger: actual run identity, scoped usage and read-only delivery."""

from dataclasses import replace

import httpx
import pytest

from backend.runtime.contracts import RunNotFound
from backend.runtime.views import OwnerRuntimeView
from backend.tests.runtime.test_inference_journal import reservation, reserve


def test_agent_runs_use_native_identity_and_preserve_unknown_usage(coordination):
    """A queued actor needs no legacy roster; absent dispatch observations remain unknown."""
    c = coordination
    run = c.store.admit(c.spec)
    c.store.admit(replace(c.spec, project_id=202, task_id=2002))
    view = OwnerRuntimeView(c.database)
    page = view.agent_runs(101)
    assert page['total_runs'] == page['total_actors'] == 1
    item = page['items'][0]
    assert (item['run_id'], item['actor_id'], item['task_title']) == (run.run_id, 'researcher-a', 'Policy')
    assert item['attempt_id'] is None and item['attempt_count'] == 0
    assert item['observed_tokens'] is None and item['model'] is None
    assert item['peer_count'] == item['unclosed_peer_count'] == 0
    assert page['next_before_seq'] is None
    with pytest.raises(RunNotFound):
        view.agent_runs(999)


def test_agent_runs_report_high_water_not_quota_price_or_physical_completion(coordination):
    """A partial cumulative observation remains visible after Stop without implying settled billing or closed work."""
    c = coordination
    run, lease = reservation(c)
    reserve(c, lease, model='observed-model')
    for tokens in (40, 55, 20):
        c.store.note_inference_usage(lease, tokens)
    c.store.cancel(101, run.run_id)
    item = OwnerRuntimeView(c.database).agent_runs(101)['items'][0]
    assert item['observed_tokens'] == 55
    assert item['dispatch_status'] == 'reserved'
    assert item['model'] == 'observed-model'
    assert item['attempt_id'] == lease.attempt_id and item['attempt_count'] == 1
    assert item['cancel_requested'] is True
    assert 'cost_usd' not in item and 'quota' not in item and 'physically_stopped' not in item


def test_agent_runs_page_history_without_cross_project_or_read_effects(coordination):
    """Stable descending run cursors preserve earlier records while another project stays isolated."""
    c = coordination
    first = c.store.admit(c.spec)
    second = c.store.admit(replace(c.spec, task_id=1002, actor_id='planner-a'))
    c.store.admit(replace(c.spec, project_id=202, task_id=2002))
    before = c.conn.execute('SELECT COUNT(*) FROM events_log').fetchone()[0]
    view = OwnerRuntimeView(c.database)
    page = view.agent_runs(101, limit=1)
    assert page['total_runs'] == page['total_actors'] == 2
    assert page['items'][0]['run_id'] == second.run_id
    older = view.agent_runs(101, before_seq=int(page['next_before_seq']), limit=1)
    assert older['items'][0]['run_id'] == first.run_id and older['next_before_seq'] is None
    assert c.conn.execute('SELECT COUNT(*) FROM events_log').fetchone()[0] == before
    assert c.conn.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
    for args in ({'limit':0},{'limit':101},{'before_seq':-1},{'before_seq':True}):
        with pytest.raises(ValueError):
            view.agent_runs(101, **args)


async def test_agent_runs_owner_route_is_readonly_and_works_without_inference(coordination):
    """Only authenticated owners can read persisted native activity when the runtime is unconfigured."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = coordination
    run = c.store.admit(c.spec)
    app = create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as anonymous:
            assert (await anonymous.get('/api/projects/101/agent-runs')).status_code == 401
        async with owner_client(app) as owner:
            response = await owner.get('/api/projects/101/agent-runs?limit=1')
            assert response.status_code == 200, response.text
            assert response.headers['cache-control'] == 'no-store'
            assert response.json()['items'][0]['run_id'] == run.run_id
            assert response.json()['runtime_configured'] is False
            assert (await owner.get('/api/projects/202/agent-runs')).json()['items'] == []
            assert (await owner.get('/api/projects/999/agent-runs')).status_code == 404
            assert (await owner.get('/api/projects/101/agent-runs?before_seq=-1')).status_code == 422
    assert c.conn.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
