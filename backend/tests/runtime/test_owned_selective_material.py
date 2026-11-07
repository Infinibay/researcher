"""Actual owned kernel/broker/native calls retrieve selective evidence under the unchanged25-tool budget; generation and Ken are controlled."""

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414


@pytest.mark.timeout(180)
async def test_owned_large_plan_and_report_use_selected_evidence_within_original_budget(owned_config):
    """A native author and developer read the original owner goal, final restriction and linked documentary evidence without copying a400KB report or modifying canonical source."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.tests.runtime.test_development_workspace import fixture_git
    from backend.tests.runtime.test_plan_execution import accepted_plan, authorize
    from backend.tests.runtime.test_result_acceptance import accept

    c = owned_config
    c.s.c.conn.execute('UPDATE projects SET description=? WHERE id=101', ('Context ' * 5000 + '\nRestriction: do not modify the source repository.',))
    c.s.c.conn.commit()
    from pathlib import Path
    binary = Path(c.settings['codex_binary'])
    original = binary.read_text()
    marker = "selective_evidence = Path('/run/researcher-source/.ken/selective-evidence').exists()"
    assert original.count(marker) == 1
    binary.write_text(original.replace(marker, 'selective_evidence = True'))
    await fixture_git(c.s.workspace, 'init', '-q')
    await fixture_git(c.s.workspace, 'add', 'fact.txt')
    await fixture_git(c.s.workspace, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'base')
    s, plan, graph = accepted_plan(c.s)
    authorize(s, plan)
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)

    async def terminal(task_id):
        """Observe the original authorized run without restarting it after a short polling interval."""
        for _ in range(400):
            runs = runtime.store.task_runs(101, task_id)
            if runs:
                await runtime.wait(runs[0].run_id)
                result = runtime.store.get(101, runs[0].run_id)
                if result.status not in ('queued', 'running', 'cancelling'):
                    return result
            await asyncio.sleep(.05)
        raise AssertionError('Original selective-material delivery did not settle')

    async with runtime:
        root = await terminal(graph['tasks']['learn'])
        assert root.status == 'needs_review', root
        state = runtime.store.result_state(101, root.run_id)
        assert state['eligible'], state
        accept(SimpleNamespace(store=runtime.store), SimpleNamespace(run_id=root.run_id, context_version=root.context_version), state)
        await runtime.dispatch_planned_work()
        child = await terminal(graph['tasks']['change'])
        assert child.status == 'needs_review', child
        assert runtime.store.code_result_state(101, child.run_id)['candidate_current']
        assert c.settings['limits']['max_tool_calls'] == 25
        counters = list(c.s.control.glob('native-state/*/home/fixture-tool-count.json'))
        assert len(counters) == 2 and all(0 < json.loads(p.read_text())['requests'] <= 25 for p in counters)
        work_receipts = list(c.s.control.glob('native-state/*/home/fixture-selected-work.json'))
        assert len(work_receipts) == 2
        for receipt in work_receipts:
            pages = json.loads(receipt.read_text())
            assert len(pages) == 4 and sum(len(base64.b64decode(p['data_base64'])) for p in pages) < 3000
            assert all(not p['selection']['whole_section_read'] for p in pages)
        receipts = list(c.s.control.glob('native-state/*/home/fixture-selected-research.json'))
        assert len(receipts) == 1
        pages = json.loads(receipts[0].read_text())
        assert len(pages) == 4 and sum(p['total_bytes'] for p in pages) < 8000
        index = json.loads(base64.b64decode(pages[0]['data_base64']))
        assert next(i for i in index['children'] if i['key'] == 'reports')['bytes'] > 399000
        with runtime.store._transaction() as conn:
            assert conn.execute("SELECT count(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0] == 0
            assert conn.execute('SELECT count(*) FROM runtime_code_acceptances').fetchone()[0] == 0
            inputs = conn.execute('SELECT input_text FROM runtime_input_snapshots').fetchall()
            assert len(inputs) == 2 and all(len(r[0].encode()) < 25000 for r in inputs)
        assert (c.s.workspace / 'fact.txt').read_text() == '137'
