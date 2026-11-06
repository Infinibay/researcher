"""Exact whole-project reports and explicit closure over accepted evidence; storage process witnesses are synthetic, never a physical execution claim."""

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_plan_execution import accepted_plan, accept_documentary_result, authorize


def completed_outputs(service_setup):
    """Construct a clean project before any history, then actually propose/accept both documentary outputs using existing synthetic peer fixtures."""
    service_setup.c.conn.execute('DELETE FROM tasks WHERE id=1002')
    service_setup.c.conn.commit()
    s, plan, graph = accepted_plan(service_setup, research_only=True)
    executions, execution = authorize(s, plan)
    for task in graph['tasks'].values():
        spec, binding = executions.prepare(execution['execution_id'], task)
        run = s.c.store.admit(spec, binding=binding)
        accept_documentary_result(s, run)
    return s, plan, graph


def command(state, key='close-project'):
    """An explicit owner statement reviews the exact scope and known unpublished candidates, without asserting scientific proof."""
    return {'operation_key': key, 'report_sha256': state['report_sha256'],
            'acknowledged_unpublished_attempts': state['unpublished_attempts'],
            'statement': 'Revisé el alcance original, los resultados y los límites de este informe; acepto el cierre.'}


def test_task_labels_and_pending_graph_never_prove_whole_project_completion(service_setup):
    """Done labels without accepted outputs and unissued causal deliveries stay explicit blockers rather than successful objectives."""
    from backend.planning.completion import ProjectCompletion

    s, plan, _graph = accepted_plan(service_setup, research_only=True)
    authorize(s, plan)
    s.c.conn.execute("INSERT INTO tasks(id,project_id,type,title,status)VALUES(3001,101,'research','Historical done label','done')")
    s.c.conn.commit()
    state = ProjectCompletion(s.c.store, legacy_active=lambda _: False).state(101, plan.run_id)
    assert not state['eligible']
    assert any(b.get('task_id') == 3001 for b in state['blockers'])
    assert 'no demuestra' in state['report_markdown']
    with pytest.raises(RunConflict):
        ProjectCompletion(s.c.store, legacy_active=lambda _: False).accept(101, plan.run_id, **command(state))


def test_exact_report_and_owner_decision_survive_reopen_without_another_effect(service_setup):
    """The owner receives actual accepted report content/citations/limits and an atomic historical decision, without another native turn or inferred publication."""
    from backend.planning.completion import ProjectCompletion
    from backend.runtime.sqlite_runs import SQLiteRunStore

    s, plan, _graph = completed_outputs(service_setup)
    records = ProjectCompletion(s.c.store, legacy_active=lambda _: False)
    state = records.state(101, plan.run_id)
    assert state['eligible'], state['blockers']
    assert state['unpublished_attempts'] == []
    assert 'The sample contains 137 units.' in state['report_markdown']
    assert 'Measurement not repeated.' in state['report_markdown']
    assert len(state['snapshot']['tasks']) == 3
    receipt = records.accept(101, plan.run_id, **command(state))
    assert receipt['kind'] == 'project.completion'
    assert receipt['project_status'] == 'completed' and not receipt['publication_performed']
    assert receipt['report_markdown'] == state['report_markdown']
    assert records.state(101, plan.run_id)['acceptance_current'] is True
    again = ProjectCompletion(SQLiteRunStore(s.c.database, clock=s.c.store.clock), legacy_active=lambda _: False)
    assert again.accept(101, plan.run_id, **command(state)) == receipt
    assert s.c.conn.execute("SELECT COUNT(*) FROM events_log WHERE event_type='project.completed'").fetchone()[0] == 1


@pytest.mark.parametrize('change', ['new_task', 'description', 'correction'])
def test_later_scope_changes_invalidate_current_report_but_preserve_original_receipt(service_setup, change):
    """Historical completion survives a later premise change; an original retry never closes the changed project again or hides its missing work."""
    from backend.planning.completion import ProjectCompletion

    s, plan, graph = completed_outputs(service_setup)
    records = ProjectCompletion(s.c.store, legacy_active=lambda _: False)
    before = records.state(101, plan.run_id)
    original = records.accept(101, plan.run_id, **command(before))
    if change == 'new_task':
        s.c.conn.execute("INSERT INTO tasks(project_id,type,title,status)VALUES(101,'research','Additional obligation','pending')")
        s.c.conn.commit()
    elif change == 'description':
        s.c.conn.execute("UPDATE projects SET description='Changed owner scope' WHERE id=101")
        s.c.conn.commit()
    else:
        task = graph['tasks']['learn']
        s.c.store.correct_context(project_id=101, task_id=task, expected_version=s.c.store.context_snapshot(101, task)['context_version'], operation_key='correct-closed-scope', statement='The criterion was incomplete.', source_kind='user_message', source_reference='owner:scope-correction')
    current = records.state(101, plan.run_id)
    assert current['acceptance'] == original and not current['acceptance_current']
    assert current['report_sha256'] != before['report_sha256']
    with pytest.raises(RunConflict):
        records.accept(101, plan.run_id, **{**command(before), 'operation_key': 'another-close'})
    assert records.accept(101, plan.run_id, **command(before)) == original


def test_generic_legacy_status_update_cannot_declare_project_completed(service_setup):
    """A status string is not an owner decision over a report, including before native admission."""
    from backend.flows.helpers.db_helpers import update_project_status
    from backend.runtime.lifecycle import NativeOwnerRequired

    with pytest.raises(NativeOwnerRequired):
        update_project_status(101, 'completed')
    assert service_setup.c.conn.execute('SELECT status FROM projects WHERE id=101').fetchone()[0] == 'new'


async def test_owner_http_report_and_exact_closure_reject_generic_completion_and_scope_expansion(service_setup):
    """Paired owner/CSRF boundaries protect an exact offline report; generic CRUD cannot bypass report acceptance, and foreign scope/proof arguments fail."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.planning.completion import ProjectCompletion
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, plan, _graph = completed_outputs(service_setup)
    app = create_app(access=LocalAccess(pairing_key='workspace-owner-key-at-least-32-characters'))
    path = f'/api/projects/101/runs/{plan.run_id}/project-plan/completion'
    body = command(ProjectCompletion(s.c.store, legacy_active=lambda _: False).state(101, plan.run_id))
    async with app.router.lifespan_context(app), owner_client(app) as client:
        preview = await client.get(path)
        assert preview.status_code == 200, preview.text
        assert preview.headers['cache-control'] == 'no-store' and preview.json()['eligible']
        assert (await client.put('/api/projects/101', json={'status':'completed'})).status_code == 409
        assert (await client.post(path+'/accept', json={**body, 'proof':True})).status_code == 422
        assert (await client.post(path+'/accept', json=body, headers={'X-Researcher-CSRF':'wrong'})).status_code == 403
        assert (await client.get(path.replace('/101/','/202/'))).status_code == 404
        response = await client.post(path+'/accept', json=body)
        assert response.status_code == 200, response.text
        assert (await client.post(path+'/accept', json=body)).json() == response.json()
        assert (await client.get(path)).json()['acceptance_current']
        changed = await client.put('/api/projects/101', json={'description':'Ahora se exige otra medición.'})
        assert changed.status_code == 200, changed.text
        assert not (await client.get(path)).json()['acceptance_current']


def test_registered_legacy_work_blocks_new_completion_but_not_historical_receipt_recovery(service_setup):
    """An owner cannot use an unobserved competing loop as closure evidence; later activity never authorizes replay of an old completion effect."""
    from backend.planning.completion import ProjectCompletion

    s, plan, _graph = completed_outputs(service_setup)
    observed = [False]
    records = ProjectCompletion(s.c.store, legacy_active=lambda _: observed[0])
    original = records.state(101, plan.run_id)
    observed[0] = True
    assert any(b['code'] == 'legacy_work_registered' for b in records.state(101, plan.run_id)['blockers'])
    with pytest.raises(RunConflict):
        records.accept(101, plan.run_id, **command(original))
    observed[0] = False
    receipt = records.accept(101, plan.run_id, **command(original))
    observed[0] = True
    assert records.accept(101, plan.run_id, **command(original)) == receipt
    assert not records.state(101, plan.run_id)['acceptance_current']


@pytest.mark.parametrize('phase', ['planned', 'running', 'needs_reconciliation'])
def test_source_setup_invalidates_current_completion_without_erasing_owner_history(service_setup, phase):
    """An administrative source intent is real outstanding project work even without a native task; a historical owner decision cannot close it by replay."""
    from backend.git.source_operations import SourceRequest
    from backend.planning.completion import ProjectCompletion
    from backend.tests.runtime.test_source_operations import operations

    s, plan, _graph = completed_outputs(service_setup)
    reports = ProjectCompletion(s.c.store, legacy_active=lambda _: False)
    before = reports.state(101, plan.run_id)
    receipt = reports.accept(101, plan.run_id, **command(before))
    sources = operations(s)
    sources.prepare(101, 'source-after-report', SourceRequest(mode='create', name='pending-source', path=str(s.root/'pending-source'), branch='main'))
    if phase != 'planned':
        lease = sources.claim(101, 'source-after-report', 'original-owner')
        sources.allocate(lease)
        if phase == 'needs_reconciliation':
            sources.uncertain(lease)
    after = reports.state(101, plan.run_id)
    assert not after['acceptance_current'] and after['report_sha256'] != before['report_sha256']
    assert any(b['code'] == 'source_setup_unclosed' for b in after['blockers'])
    assert after['snapshot']['source_operations'][0]['status'] == phase
    assert 'pending-source' in after['report_markdown']
    assert 'observación registrada' in after['report_markdown']
    with pytest.raises(RunConflict):
        reports.accept(101, plan.run_id, **command(after, 'cannot-close-source'))
    assert reports.accept(101, plan.run_id, **command(before)) == receipt
