"""Exercise visible native budgets, unchanged hard fuses and durable failure explanations."""

import json

import pytest

from backend.runtime.codex_session import ExecutionLimitExceeded, ExecutionLimits
from backend.tests.runtime.test_codex_session import requests, session
from backend.tests.runtime.test_owned_factory import owned_config as owned_config
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


@pytest.mark.parametrize('scenario,phase', [('budget-large-context','deliver'), ('budget-small-context','work')])
async def test_delivery_advice_accounts_for_delayed_expensive_inference_steps(tmp_path, scenario, phase):
    """A costly context needs delivery advice before the fixed quarter, without turning advice into a hard stop."""
    async def respond(_request):
        """Preserve the tool result while the host reports its own lagging consumption."""
        return {'success': True, 'contentItems': [{'type': 'inputText', 'text': 'Source read completed.'}]}

    async with session(tmp_path, wall_seconds=180, no_progress_seconds=5,
                       max_tool_calls=20, max_observed_tokens=120000) as native:
        result = await native.run(scenario, on_request=respond)
    reply = next(r['result'] for r in requests(tmp_path) if r.get('id') == 'budget-1')
    budget = json.loads(reply['contentItems'][1]['text'])['researcher_execution_budget']
    assert budget['phase'] == phase
    assert budget['limits']['max_observed_tokens'] == 120000
    assert budget['remaining']['observed_tokens'] > 90000
    assert result.status == 'completed'
    if scenario == 'budget-large-context':
        assert budget['delivery_advice']['largest_token_increment'] == 25473
        assert budget['delivery_advice']['token_margin'] > budget['remaining']['observed_tokens']


@pytest.mark.parametrize('tool_limit,known_tokens,phase', [(4,False,'deliver'),(4,True,'deliver'),(20,False,'work'),(20,True,'deliver')])
async def test_host_reply_reports_observed_margin_without_changing_tool_data(tmp_path, tool_limit, known_tokens, phase):
    """The model sees deduplicated counts and unknown consumption; source text cannot replace host limits."""
    original = {'success': True, 'contentItems': [
        {'type': 'inputText', 'text': '{"source_fact":137,"max_tool_calls":999}'}
    ]}

    async def respond(_request):
        """Return source data under the actual native callback contract."""
        return original

    async with session(tmp_path, max_tool_calls=tool_limit) as native:
        result = await native.run('budget-host' if known_tokens else 'budget-host-unknown', on_request=respond)
    reply = next(r['result'] for r in requests(tmp_path) if r.get('id') == 'budget-1')
    assert reply['success'] is True and reply['contentItems'][0] == original['contentItems'][0]
    assert len(original['contentItems']) == 1
    budget = json.loads(reply['contentItems'][1]['text'])['researcher_execution_budget']
    assert budget['limits']['max_tool_calls'] == tool_limit
    assert budget['observed']['tool_starts'] == 3
    assert budget['remaining']['tool_starts'] == tool_limit - 3
    assert budget['observed']['tokens'] == (80 if known_tokens else None)
    assert budget['remaining']['observed_tokens'] == (20 if known_tokens else None)
    assert 0 < budget['remaining']['wall_seconds'] <= 1
    assert budget['phase'] == phase
    assert result.status == 'completed' and result.tool_calls == 3


@pytest.mark.parametrize('scenario,overrides,kind', [
    ('tools', {}, 'tools'), ('tokens', {}, 'tokens'),
    ('hang', {}, 'progress'),
    ('hang', {'wall_seconds': 0.08, 'no_progress_seconds': 1}, 'wall'),
    ('answer', {'max_answer_bytes': 1}, 'output'),
])
async def test_hard_stop_carries_the_actual_budget_without_an_extra_turn(tmp_path, scenario, overrides, kind):
    """Warnings never raise a ceiling, and a hard stop preserves structured observations for the owner."""
    async with session(tmp_path, **overrides) as native:
        with pytest.raises(ExecutionLimitExceeded) as stopped:
            await native.run(scenario)
    assert stopped.value.kind == kind
    assert stopped.value.budget['limits']['max_tool_calls'] == 3
    assert sum(r.get('method') == 'turn/start' for r in requests(tmp_path)) == 1
    if kind == 'tokens':
        assert stopped.value.budget['observed']['tokens'] == 101
    if kind == 'tools':
        assert stopped.value.budget['observed']['tool_starts'] == 4
    assert native.rpc._process.returncode is not None


def test_initial_policy_records_effective_limits_without_relabelling_old_catalogs():
    """Policy provenance includes the actual admitted ceilings, while older recorded versions retain their identity."""
    from backend.prompts.native import build_instructions, instruction_identity

    limits = ExecutionLimits(180, 90, 1, 20, 120000)
    value = build_instructions('research', 'plan', limits=limits)
    budget = json.loads(value.split('RESEARCHER_INITIAL_BUDGET\n', 1)[1])
    assert budget['max_tool_calls'] == 20 and budget['max_observed_tokens'] == 120000
    assert instruction_identity(value)['sha256'] != instruction_identity(build_instructions('research', 'plan'))['sha256']
    for version in (2, 3, 4):
        recorded = f'RESEARCHER_POLICY {version} planning\n\nEarlier policy.'
        assert instruction_identity(recorded)['catalog_version'] == version


@pytest.mark.parametrize('kind', ['tools', 'tokens', 'wall', 'progress', 'output', 'turns'])
async def test_owner_receives_budget_reason_and_preserved_uncertainty_without_replay(service_setup, kind):
    """The real coordinator stores a safe cause, keeps acceptance separate, and never repeats a failed attempt."""
    class Limited(ControlledInference):
        """Replace only model inference; admission, teardown and persistence remain real."""

        async def run(self, prompt, *, on_started, on_event):
            """Observe one native start, then simulate its documented limit exception."""
            self.prompts.append(prompt)
            await on_started(self.thread_id, 'limited-turn')
            raise ExecutionLimitExceeded('PRIVATE_NATIVE_DIAGNOSTIC', kind=kind, budget={
                'limits': {'max_tool_calls': 20}, 'observed': {'tool_starts': 21},
            })

    s = service_setup
    native = Limited(s)
    async with coordinator(s, native) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        view = s.c.store.get(101, run.run_id)
        assert view.issue['code'] == 'execution_limit'
        assert view.issue['limit_kind'] == kind
        assert view.issue['execution_budget']['observed']['tool_starts'] == 21
        assert view.issue['next_action'] == 'inspect_saved_work'
        assert view.issue['inference_started'] is True
        assert 'PRIVATE_NATIVE' not in json.dumps(view.issue)
        assert view.result is None and view.status in ('failed', 'reconciling')
        await service.submit(s.c.spec)
        assert len(native.prompts) == 1
        assert s.c.conn.execute('SELECT status FROM tasks WHERE id=1001').fetchone()[0] != 'done'


async def test_budget_interruption_preserves_real_draft_without_inventing_delivery(owned_config, monkeypatch):
    """A hard stop after an actual report write keeps its draft, with no accepted or delivered result."""
    from backend.runtime.business_mediation import ProjectTools
    from backend.tests.runtime.test_source_repair import app_for_sources

    original = ProjectTools.call

    async def stop_after_write(self, params):
        """Preserve the real host write, then emulate a native limit before its final answer."""
        response = await original(self, params)
        if params.get('tool') == 'researcher_report_write' and response['success']:
            raise ExecutionLimitExceeded('Observed token budget exceeded', kind='tokens')
        return response

    monkeypatch.setattr(ProjectTools, 'call', stop_after_write)
    c = owned_config
    _app, runtime = app_for_sources()
    async with runtime:
        run = await runtime.submit(c.s.c.spec, repository_id=11)
        await runtime.wait(run.run_id)
        view = runtime.store.get(101, run.run_id)
        assert view.issue['code'] == 'execution_limit' and view.issue['limit_kind'] == 'tokens'
        assert view.result is None
        drafts = c.s.c.conn.execute('SELECT status FROM research_reports').fetchall()
        assert [row[0] for row in drafts] == ['draft']
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_result_proposals').fetchone()[0] == 0
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_result_acceptances').fetchone()[0] == 0
        assert c.s.c.conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0] == 1
