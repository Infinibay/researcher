"""Real owned code→code graph with bounded causal artifacts, independent reviews and explicit owner acceptance; generation and Ken are controlled fixtures."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414


@pytest.mark.timeout(480)
async def test_owned_successor_reads_exact_accepted_code_and_input_without_assuming_publication(owned_config, monkeypatch):
    """Real kernel/broker/Git/SQLite prove causal authors/checks/reviews and exact owner project closure with explicit unpublished acknowledgement, without semantic-success or real-model claims."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.planning.execution import PlanExecutions
    from backend.planning.store import ProjectPlans
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.code_reviews import CodeReviews, CodeReviewTarget
    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_code_acceptance import owner_intent
    from backend.tests.runtime.test_development_workspace import fixture_git
    from backend.runtime import service
    from backend.planning.completion import ProjectCompletion

    warning = service.logger.warning

    def fixture_warning(message, *args, **kwargs):
        """Expose the actual stack only in this synthetic protocol test, without logging production inputs or local variables."""
        if message == 'Research run stopped (%s)':
            kwargs['exc_info'] = True
        return warning(message, *args, **kwargs)

    monkeypatch.setattr(service.logger, 'warning', fixture_warning)

    c = owned_config
    # These unused seed rows have no run/attempt/history. Start the physical
    # project with only its real plan, retaining every subsequently issued run.
    c.s.c.conn.execute('DELETE FROM tasks WHERE project_id=101 AND id IN (1001,1002)')
    c.s.c.conn.commit()
    script = Path(c.settings['codex_binary'])
    fixture = script.read_text()
    assert fixture.count('"type": "research",') == 1
    fixture = fixture.replace('"type": "research",', '"type": "code",')
    fixture = fixture.replace('Read relevant code and record cited evidence.', 'Change fact.txt from137to200 and state actual checks.')
    fixture = fixture.replace('A supported explanation and explicit limits.', 'fact.txt contains200 with recorded checks and explicit limits.')
    fixture = fixture.replace('Apply the change supported by inspection.', 'Read the accepted predecessor code and original input; maintain200 in the private copy without assuming publication.')
    script.write_text(fixture)
    c.settings['limits'].update(wall_seconds=180, max_tool_calls=60)
    c.settings['development_checks'] = [{'argv': ['/usr/bin/python3', '-c', "from pathlib import Path;assert Path('fact.txt').read_text()=='200';print('causal exact value checked')"], 'framework': 'command', 'timeout_seconds': 5, 'environment_id': 'system'}]
    c.path.write_text(json.dumps(c.settings))
    await fixture_git(c.s.workspace, 'init', '-q')
    await fixture_git(c.s.workspace, 'add', 'fact.txt')
    await fixture_git(c.s.workspace, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'source137')
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    async with runtime:
        plan = await runtime.start_project_plan(101, operation_key='code-causal-plan', prompt='Change fact.txt from137 to 200, then validate the exact accepted predecessor in a dependent task. Preserve canonical source until explicit publication.', repository_id=11)
        await runtime.wait(plan.run_id)
        plans = ProjectPlans(runtime.store)
        proposed = plans.state(101, plan.run_id)
        graph = plans.accept(101, plan.run_id, operation_key='accept-code-causal-plan', proposal_sha256=proposed['proposal']['proposal_sha256'], context_version=proposed['context_version'])
        executions = PlanExecutions(runtime.store)
        observed = executions.state(101, plan.run_id)
        await runtime.execute_plan(101, plan.run_id, operation_key='execute-code-causal-plan', manifest_sha256=observed['manifest_sha256'])
        tasks = list(graph['tasks'].values())

        async def issued(task_id):
            """Observe only the original registered delivery; never restart work after a short observation window."""
            for _ in range(400):
                deliveries = executions.state(101, plan.run_id)['execution']['deliveries']
                run_id = next(item['run_id'] for item in deliveries if item['task_id'] == task_id)
                if run_id:
                    await runtime.wait(run_id)
                    actual = runtime.store.get(101, run_id)
                    if actual.status not in ('queued', 'running', 'cancelling'):
                        return actual
                await asyncio.sleep(.05)
            raise AssertionError('Original causal delivery was not issued')

        async def review_and_accept(author, name):
            """Run a distinct actual native reviewer and then an explicit exact owner decision, without publishing code."""
            packet = CodeReviews(runtime.store).subject(101, author.attempt_id)
            reviewer = await runtime.review_code(replace(c.s.c.spec, task_id=author.task_id, actor_id='independent-'+name, context_version=author.context_version, operation_key='review-'+name, prompt='Inspect the exact original request, candidate and causal input; do not inherit predecessor approval.'), CodeReviewTarget(author.attempt_id, packet['subject_sha256']))
            await runtime.wait(reviewer.run_id)
            reviewed = runtime.store.get(101, reviewer.run_id)
            assert reviewed.status == 'needs_review', reviewed
            assert reviewed.actor_id != author.actor_id and reviewed.thread_id != author.thread_id
            from backend.tests.runtime.test_code_acceptance import choose_fixture_check_policy
            choose_fixture_check_policy(runtime.store)
            owner = CodeAcceptances(runtime.store)
            state = owner.state(101, author.run_id)
            assert state['eligible'] and state['acceptance'] is None, state
            return owner.accept(101, author.run_id, owner_intent(state, operation_key='accept-'+name))

        first = await issued(tasks[0])
        assert first.status == 'needs_review', first
        assert not runtime.store.task_runs(101, tasks[1])
        await review_and_accept(first, 'predecessor')
        assert (c.s.workspace / 'fact.txt').read_text() == '137'
        await runtime.dispatch_planned_work()
        second = await issued(tasks[1])
        assert second.status == 'needs_review', second
        frozen = json.loads(runtime.store.input_record(101, second.run_id)['input_text'])
        source = frozen['work_delivery']['prerequisites'][0]
        assert source['kind'] == 'accepted_code_candidate' and source['task_id'] == tasks[0]
        assert source['material']['read_tool'] == 'researcher_prerequisite_code'
        assert set(source['material']['sections']['author_input']) == {'status', 'sha256', 'bytes'}
        assert 'diff_base64' not in source['material']
        with runtime.store._transaction() as conn:
            assert any(b'causal predecessor applied' in bytes(row[0]) for row in conn.execute('SELECT stdout FROM runtime_jobs WHERE run_id=?', (second.run_id,)))
        await review_and_accept(second, 'successor')
        assert (c.s.workspace / 'fact.txt').read_text() == '137'
        with runtime.store._transaction() as conn:
            assert conn.execute('SELECT COUNT(*) FROM runtime_code_acceptances').fetchone()[0] == 2
            assert conn.execute('SELECT COUNT(*) FROM runtime_code_publication_requests').fetchone()[0] == 0
        assert len(runtime.store.task_runs(101, tasks[0])) == 2
        assert len(runtime.store.task_runs(101, tasks[1])) == 2
        completion = ProjectCompletion(runtime.store, legacy_active=runtime.legacy_active)
        report = completion.state(101, plan.run_id)
        assert report['eligible'], report['blockers']
        assert len(report['unpublished_attempts']) == 2
        decision = {'operation_key': 'owner-completes-causal-project', 'report_sha256': report['report_sha256'],
                    'acknowledged_unpublished_attempts': report['unpublished_attempts'],
                    'statement': 'Revisé el alcance y los dos candidatos comprobados y revisados. Acepto el cierre con ambos sin publicar y con los límites descritos.'}
        with pytest.raises(RunConflict, match='sin aceptar/cerrar|reconocer'):
            completion.accept(101, plan.run_id, **{**decision, 'acknowledged_unpublished_attempts': []})
        receipt = completion.accept(101, plan.run_id, **decision)
        assert completion.accept(101, plan.run_id, **decision) == receipt
        assert completion.state(101, plan.run_id)['acceptance_current']
        assert receipt['snapshot'] == report['snapshot'] and not receipt['publication_performed']
        assert (c.s.workspace / 'fact.txt').read_text() == '137'
