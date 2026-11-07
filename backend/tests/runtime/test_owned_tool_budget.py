"""The actual owned host rejects an over-budget dynamic request before its effect, retaining prior drafts and honest owner feedback; generation/Ken are controlled."""

import json

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414


@pytest.mark.timeout(180)
async def test_owned_missing_start_notifications_stop_before_result_proposal_and_keep_draft(owned_config):
    """Six actual host calls may save a report; the seventh cannot propose a result even though the native fixture sends no item-start notifications."""
    from backend.tests.runtime.test_source_repair import app_for_sources

    c=owned_config
    c.settings['limits']['max_tool_calls']=6
    c.path.write_text(json.dumps(c.settings))
    _app,runtime=app_for_sources()
    async with runtime:
        run=await runtime.submit(c.s.c.spec,repository_id=11)
        await runtime.wait(run.run_id)
        view=runtime.store.get(101,run.run_id)
        assert view.status=='failed' and view.issue['code']=='execution_limit',view
        assert view.issue['limit_kind']=='tools' and 'herramientas' in view.issue['message']
        budget=view.issue['execution_budget']
        assert budget['observed']['tool_starts']==7
        assert budget['observed']['host_tool_requests_admitted']==6
        assert budget['remaining']['tool_starts']==0 and budget['observed']['tokens'] is None
        assert view.result is None
        assert [r[0] for r in c.s.c.conn.execute('SELECT status FROM research_reports')]==['draft']
        for table in ('runtime_result_proposals','runtime_result_acceptances'):
            assert c.s.c.conn.execute('SELECT count(*) FROM '+table).fetchone()[0]==0
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0]==1
        assert c.s.c.conn.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0]==0
        assert c.s.c.conn.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]==0
        files=list(c.s.control.glob('native-state/*/home/fixture-tool-count.json'))
        assert len(files)==1 and json.loads(files[0].read_text())['requests']==7
        progress=json.loads(next(c.s.control.glob('native-state/*/home/fixture-progress.json')).read_text())
        assert progress['step']==6 and progress['response']['success']
