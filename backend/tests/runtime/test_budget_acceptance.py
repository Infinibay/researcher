"""Full budget-boundary acceptance: host capacity, quota refusal, retained accounting and no automatic provider/turn replay; controlled generation only."""

import asyncio
import json
from dataclasses import replace

import pytest

from backend.runtime.history import RuntimeHistory
from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


@pytest.mark.parametrize('project_id,task_id', [(101,1002),(202,2002)])
async def test_host_capacity_precedes_preparation_in_same_or_another_project(service_setup, project_id, task_id):
    """The one host gate bounds both same-project work and total concurrent work before another native reservation."""
    s = service_setup
    if project_id == 202:
        workspace = s.root/'beta'
        workspace.mkdir()
        s.c.conn.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(22,202,'beta',?)", (str(workspace),))
        s.c.conn.commit()
    native = ControlledInference(s)
    async with coordinator(s, native, max_concurrent=1) as service:
        first = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), timeout=3)
        second = await service.submit(replace(s.c.spec, project_id=project_id, task_id=task_id, operation_key='competing'))
        view = s.c.store.get(project_id, second.run_id)
        assert view.issue['code'] == 'capacity', view
        assert view.issue['inference_started'] is False
        assert s.c.conn.execute('SELECT count(*) FROM runtime_preparation_reservations').fetchone()[0] == 1
        assert len(native.prompts) == 1
        native.release.set()
        await service.wait(first.run_id)
        # Completing another request never silently starts the refused one.
        assert len(native.prompts) == 1 and s.c.store.get(project_id, second.run_id).issue['code'] == 'capacity'


@pytest.mark.timeout(180)
async def test_owned_quota_failure_keeps_original_model_and_hold_without_replay(owned_config):
    """A controlled native quota failure crosses real broker/process/storage boundaries without starting an alternative model/provider or retrying the original request."""
    from backend.tests.runtime.test_source_repair import app_for_sources

    c = owned_config
    marker = c.s.workspace/'.ken/quota-exhausted'
    marker.parent.mkdir(exist_ok=True)
    marker.touch()
    _app, runtime = app_for_sources()
    async with runtime:
        run = await runtime.submit(c.s.c.spec, repository_id=11)
        await runtime.wait(run.run_id)
        view = runtime.store.get(101, run.run_id)
        assert view.status == 'failed', view
        assert (await runtime.submit(c.s.c.spec, repository_id=11)).run_id == run.run_id
        await runtime.wait(run.run_id)
        budget = RuntimeHistory(c.s.c.database).budget(101)
        assert budget['used_turns'] == 1 and budget['accounted_tokens'] == 1000
        assert budget['observed_tokens'] is None and budget['held_tokens'] == 1000
        assert runtime.store.input_record(101, run.run_id)['model'] == 'controlled-only'
        for table in ('runtime_inference_dispatches','runtime_preparation_reservations','runtime_attempts'):
            assert c.s.c.conn.execute('SELECT count(*) FROM '+table).fetchone()[0] == 1
        assert c.s.c.conn.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0] == 0
        assert c.s.c.conn.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0] == 0
        records = list(c.s.control.glob('native-state/*/home/fixture-quota.json'))
        assert len(records) == 1 and json.loads(records[0].read_text()) == {'turns':1,'model_provider':'openai'}
        assert not list(c.s.control.glob('native-state/*/home/fixture-tool-count.json'))
