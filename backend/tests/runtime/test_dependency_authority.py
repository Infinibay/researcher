"""Blocking dependencies retain causal authority across manual admission and context changes."""

from dataclasses import replace

import pytest

from backend.research.models import ResearchForbidden, SourceDraft
from backend.runtime.contracts import RunConflict, StaleAttempt
from backend.tests.runtime.test_result_acceptance import make_accepted_result


@pytest.fixture
def schema_target(request):
    """Select historical schema70 only for the explicit no-backfill compatibility test."""
    return getattr(request,'param',None)


def block(c, child=1002, parent=1001, kind='blocks'):
    """Create a baseline relation before any dependent admission, without simulating an owner edit."""
    c.conn.execute('INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(?,?,?)',(child,parent,kind))
    c.conn.commit()


def child(c):
    """Admit the manual consumer through the actual native run store."""
    return c.store.admit(replace(c.spec,task_id=1002,operation_key='dependent-request'))


def change_parent(c, writer):
    """Change the actual parent's premises through either retained product writer boundary."""
    if writer=='metadata':
        c.conn.execute("UPDATE tasks SET description='A changed requirement' WHERE id=1001")
        c.conn.commit()
    else:
        c.store.correct_context(project_id=101,task_id=1001,expected_version=1,operation_key='parent-change',statement='Use another observed input.',source_kind='user_message',source_reference='test:parent-change')


@pytest.mark.parametrize('status',['pending','done'])
def test_manual_consumer_requires_current_acceptance_not_just_parent_status(coordination,status):
    """Manual blocks cannot bypass the prerequisite gate or turn historical done into acceptance."""
    c=coordination
    if status=='done':
        c.conn.execute('DELETE FROM tasks WHERE id=1001')
        c.conn.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Historical done fixture','done')")
    else:
        c.conn.execute('UPDATE tasks SET status=? WHERE id=1001',(status,))
    c.conn.commit()
    block(c)
    with pytest.raises(RunConflict,match='prerequisite'):
        child(c)
    assert not c.store.task_runs(101,1002)


@pytest.mark.parametrize('kind',['related_to','parent_of'])
def test_nonblocking_relations_do_not_require_acceptance(coordination,kind):
    """Informational relation kinds preserve their distinct semantics."""
    block(coordination,kind=kind)
    assert child(coordination).status=='queued'


def test_current_accepted_parent_allows_manual_consumer(coordination):
    """A current explicit acceptance permits one ordinary dependent admission."""
    c,_=make_accepted_result(coordination)
    block(c)
    assert child(c).status=='queued'


@pytest.mark.parametrize('writer',['metadata','correction'])
def test_parent_change_withdraws_already_active_manual_child_and_grant(coordination,writer):
    """Both retained writers atomically invalidate dependent tools and native authority before any polling."""
    c,_=make_accepted_result(coordination)
    block(c)
    run=child(c)
    lease=c.store.claim(101,run.run_id,'synthetic-child-owner')
    token=c.research.issue_grant(project_id=101,task_id=1002,agent_id=lease.actor_id,permissions={'sources.capture'})
    scope=c.research.authorize(token);c.store.bind_grant(lease,scope.grant_id)
    change_parent(c,writer)
    with pytest.raises(ResearchForbidden):
        c.research.capture_source(scope,'late-child-write',SourceDraft('attachment','synthetic:late','Late','An obsolete write.'),intent={})
    with pytest.raises(StaleAttempt):
        c.store.heartbeat(lease)
    assert c.store.context_snapshot(101,1002)['context_version']==2
    assert c.store.get(101,run.run_id).status=='reconciling'


def test_parent_change_between_admission_and_claim_withdraws_queued_child(coordination):
    """A queued consumer cannot start after its accepted prerequisite changes."""
    c,_=make_accepted_result(coordination)
    block(c);run=child(c)
    change_parent(c,'metadata')
    with pytest.raises(RunConflict):
        c.store.claim(101,run.run_id,'synthetic-child-owner')
    assert c.store.get(101,run.run_id).status=='superseded'


@pytest.mark.parametrize('recursive',[False,True])
def test_one_cause_versions_diamond_cycle_and_initial_context_once(coordination,recursive):
    """Materializing the closure handles both SQLite recursion modes without crossing projects or informational links."""
    c=coordination
    c.conn.execute(f'PRAGMA recursive_triggers={int(recursive)}')
    c.conn.executemany("INSERT INTO tasks(id,project_id,type,title,status) VALUES(?,101,'research','Causal fixture','pending')",[(1003,),(1004,),(1005,)])
    c.conn.executemany("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(?,?,'blocks')",[(1002,1001),(1003,1001),(1004,1002),(1004,1003),(1001,1004),(2002,1001)])
    c.conn.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(1005,1001,'related_to')")
    c.conn.commit()
    change_parent(c,'metadata')
    assert [tuple(row) for row in c.conn.execute('SELECT task_id,version FROM task_contexts ORDER BY task_id')]==[(1001,2),(1002,2),(1003,2),(1004,2)]
    assert c.conn.execute('SELECT count(*) FROM runtime_context_causes').fetchone()[0]==1
    assert c.conn.execute('SELECT count(*) FROM runtime_context_causes WHERE processing=1').fetchone()[0]==0
    assert c.conn.execute('SELECT count(*) FROM runtime_context_affected').fetchone()[0]==4


def test_causal_event_failure_rolls_back_parent_and_child_authority(coordination):
    """A failed dependent event cannot commit the parent edit or partly withdraw its consumer."""
    c,_=make_accepted_result(coordination);block(c);run=child(c)
    lease=c.store.claim(101,run.run_id,'synthetic-child-owner')
    c.conn.execute("CREATE TRIGGER fail_causal_event BEFORE INSERT ON events_log WHEN new.event_type='context.dependencies_changed' BEGIN SELECT RAISE(ABORT,'injected causal failure'); END")
    c.conn.commit()
    with pytest.raises(Exception,match='injected causal failure'):
        change_parent(c,'metadata')
    c.conn.rollback()
    assert c.store.heartbeat(lease).fence==lease.fence
    assert c.store.context_snapshot(101,1001)['context_version']==1
    assert c.store.context_snapshot(101,1002)['context_version']==1
    assert c.conn.execute('SELECT count(*) FROM runtime_context_causes').fetchone()[0]==0


def test_accepted_child_reopens_and_retains_original_acceptance_when_parent_changes(coordination):
    """A child acceptance becomes historical under a changed premise, without deleting its report or receipt."""
    from types import SimpleNamespace
    from backend.tests.runtime.test_plan_execution import accept_documentary_result

    c,_=make_accepted_result(coordination);block(c);run=child(c)
    receipt=accept_documentary_result(SimpleNamespace(c=c),run)
    before=c.store.result_state(101,run.run_id)
    change_parent(c,'correction')
    after=c.store.result_state(101,run.run_id)
    assert after['acceptance']['acceptance_id']==receipt['acceptance_id']
    assert after['candidate']==before['candidate'] and not after['acceptance_current']
    assert c.conn.execute('SELECT status FROM tasks WHERE id=1002').fetchone()[0]=='pending'
    assert c.store.get(101,run.run_id).status=='accepted'


def test_reaccepting_parent_cannot_revive_old_consumer_lease(coordination):
    """A new parent acceptance does not refresh the context or grant of an already retired child."""
    from types import SimpleNamespace
    from backend.tests.runtime.test_plan_execution import accept_documentary_result

    c,_=make_accepted_result(coordination);block(c);run=child(c)
    lease=c.store.claim(101,run.run_id,'synthetic-child-owner')
    change_parent(c,'correction')
    renewed=c.store.admit(replace(c.spec,context_version=2,operation_key='new-parent-request'))
    from backend.tests.runtime.test_result_acceptance import accept
    new_lease,state=accept_documentary_result(SimpleNamespace(c=c),renewed,accept_now=False)
    accept(c,new_lease,state,key='new-parent-acceptance')
    with pytest.raises(StaleAttempt):
        c.store.heartbeat(lease)
    assert c.store.context_snapshot(101,1002)['context_version']==2
    assert c.store.get(101,run.run_id).status=='reconciling'


def test_manual_consumer_receives_and_reads_exact_accepted_parent_material(coordination):
    """Manual dependency authority includes retrievable accepted evidence, with source scope and limitations preserved."""
    import json
    from backend.planning.materials import PredecessorMaterials
    from backend.runtime.run_inputs import freeze_input

    c,parent=make_accepted_result(coordination);block(c);run=child(c)
    lease=c.store.claim(101,run.run_id,'synthetic-child-owner')
    material=PredecessorMaterials(c.store)
    assert material.available(lease)
    window=material.read_research(lease,1001)
    assert window['source']['run_id']==parent.run_id
    context=c.store.context_snapshot(101,1002)
    with c.store._transaction() as conn:
        frozen=freeze_input(conn,c.store._row(conn,101,run.run_id),context)
    packet=json.loads(frozen.input_text)['prerequisite_material']
    assert packet['prerequisites'][0]['run_id']==parent.run_id
    assert packet['prerequisites'][0]['material']['current_task_authority']=='data_only'
    assert packet['prerequisites'][0]['material']['sections']['author_input']['status']=='unknown'
    with pytest.raises(RunConflict):
        material.read_research(lease,2002)


@pytest.mark.parametrize('schema_target',[70],indirect=True)
def test_upgrade_never_invents_missing_material_for_historical_manual_run(coordination):
    """An old queued admission keeps its original receipt but cannot claim authority with reconstructed premises."""
    from backend.tools.base.db import ensure_migrations

    c,_=make_accepted_result(coordination);block(c);run=child(c)
    ensure_migrations(c.database,target_version=71,existing_only=True)
    with pytest.raises(RunConflict,match='material is unknown'):
        c.store.claim(101,run.run_id,'synthetic-child-owner')
    assert c.store.get(101,run.run_id).status=='queued'
    assert c.conn.execute('SELECT count(*) FROM runtime_manual_prerequisites').fetchone()[0]==0
