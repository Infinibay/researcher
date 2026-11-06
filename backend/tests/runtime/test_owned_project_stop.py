"""Actual owned native project Stop with original scope and physical closure; generation and Ken are controlled and no real model is invoked."""

import asyncio
import json

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414


@pytest.mark.timeout(120)
async def test_observed_project_stop_withdraws_actual_original_worker_and_replay_is_readonly(owned_config):
    """The existing runtime owns the kernel domain; SQL fences and exact owner targets precede local withdrawal, while a replay returns only the original intent receipt."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.api.routes.projects import StopObservedProject, stop_project
    from backend.planning.project_workspace import ProjectWorkspace
    from backend.tests.runtime.authority_fixture import journal

    c = owned_config
    markers = c.s.workspace / '.ken'
    markers.mkdir()
    (markers / 'hold-turn').write_text('hold')
    c.settings['limits'].update(wall_seconds=90,no_progress_seconds=60)
    c.path.write_text(json.dumps(c.settings))
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    async with runtime:
        run = await runtime.submit(c.s.c.spec,repository_id=11)
        async with asyncio.timeout(45):
            while not list(c.s.control.glob('native-state/*/home/turn-entered')):
                await asyncio.sleep(.05)
        records = ProjectWorkspace(runtime.store,workspaces=runtime.workspaces,legacy_active=runtime.legacy_active)
        state = records.state(101)
        assert state['project']['status'] == 'new'
        assert [r['run_id'] for r in state['activity']] == [run.run_id]
        body = {'operation_key':'stop-original-native-project',**state['stop']}
        from types import SimpleNamespace

        response = await stop_project(101,SimpleNamespace(app=app),StopObservedProject(**body))
        receipt = json.loads(response.body)
        assert receipt['closure']=='unconfirmed'
        assert runtime.store.get(101,run.run_id).status in ('cancelling','cancelled')
        await asyncio.wait_for(runtime.wait(run.run_id),20)
        assert runtime.store.get(101,run.run_id).status == 'cancelled'
        assert records.request_stop(101,**body) == (receipt,False)
        with journal(c.authority) as authority:
            assert authority.load().records['broker:active'] is None
        with runtime.store._transaction() as conn:
            assert not conn.execute("SELECT 1 FROM runtime_peers WHERE state!='closed'").fetchone()
            assert conn.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 1
            assert conn.execute('SELECT COUNT(*) FROM research_reports').fetchone()[0] == 0
