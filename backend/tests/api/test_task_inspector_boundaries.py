"""Owner dependency edits revoke old context atomically and task deletion preserves native history."""

import sqlite3
from types import SimpleNamespace

import pytest

from backend.runtime.contracts import RunSpec, StaleAttempt
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.tests.api.test_project_records import client, owner_app
from backend.tools.base.db import get_db_path

__all__ = ['client','owner_app']


def tasks(client):
    """Create three same-project manual tasks without admitting native work or inventing completion."""
    return [client.post('/api/tasks',json={'project_id':1,'title':title,'type':'research'}).json()['id'] for title in ['Entrada','Salida','Alternativa']]


def test_foreign_dependency_edit_is_rejected_without_removing_original_edges(client, db_conn, seeded_project):
    """A foreign prerequisite cannot replace a valid original relationship even though both tasks exist."""
    first,second,_=tasks(client)
    assert client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[first]}).status_code==201
    project=client.post('/api/projects',json={'name':'Ajeno'}).json()['id']
    foreign=client.post('/api/tasks',json={'project_id':project,'title':'Ajena'}).json()['id']
    rejected=client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[foreign]})
    assert rejected.status_code==404
    assert client.get(f'/api/tasks/{second}/dependencies').json()==[{'task_id':second,'depends_on_task_id':first,'dependency_type':'blocks'}]


def test_dependency_edit_versions_inputs_withdraws_authority_and_notifies_after_commit(client,owner_app,db_conn,seeded_project,monkeypatch):
    """An active lease cannot survive a changed prerequisite; the host callback observes the committed withdrawal."""
    first,second,_=tasks(client)
    store=SQLiteRunStore(get_db_path())
    context=store.context_snapshot(1,second)['context_version']
    run=store.admit(RunSpec(1,second,'synthetic-never-launched',context,'original-work','Read current inputs','codex'))
    lease=store.claim(1,run.run_id,'synthetic-owner')
    calls=[]
    def notified(project,task):
        """Observe the durable status after the edit's transaction, never while its write lock is held."""
        calls.append((project,task,store.get(project,run.run_id).status))
    with monkeypatch.context() as patch:
        patch.setattr(owner_app[0].state,'runtime_service',SimpleNamespace(task_inputs_changed=notified))
        result=client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[first]})
    assert result.status_code==201
    assert store.context_snapshot(1,second)['context_version']==context+1
    assert store.get(1,run.run_id).status=='reconciling'
    with pytest.raises(StaleAttempt):store.heartbeat(lease)
    assert calls==[(1,second,'reconciling')]
    snapshot=store.context_snapshot(1,second)
    assert snapshot['corrections'][-1]['source_kind']=='tool_evidence'
    assert str(first) in snapshot['corrections'][-1]['statement']


def test_identical_dependency_replacement_preserves_version_and_event_count(client,db_conn,seeded_project):
    """A repeated set-valued edit is a no-op rather than a new context revision or duplicate event."""
    first,second,third=tasks(client)
    body={'depends_on':[first,third]}
    assert client.post(f'/api/tasks/{second}/dependencies',json=body).status_code==201
    store=SQLiteRunStore(get_db_path());version=store.context_snapshot(1,second)['context_version']
    count=db_conn.execute('SELECT count(*) FROM events_log').fetchone()[0]
    assert client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[third,first]}).status_code==201
    assert store.context_snapshot(1,second)['context_version']==version
    assert db_conn.execute('SELECT count(*) FROM events_log').fetchone()[0]==count


def test_failed_dependency_event_rolls_back_edges_and_context(client,db_conn,seeded_project):
    """The prerequisite set and its context cannot commit when the matching durable event fails."""
    from backend.planning.owner_records import OwnerPlanningRecords

    first,second,_=tasks(client);store=SQLiteRunStore(get_db_path())
    version=store.context_snapshot(1,second)['context_version']
    run=store.admit(RunSpec(1,second,'synthetic-never-launched',version,'rollback-work','Original inputs','codex'))
    lease=store.claim(1,run.run_id,'synthetic-owner')
    before=store.context_snapshot(1,second)
    db_conn.execute("CREATE TRIGGER fail_dependency_context BEFORE INSERT ON events_log WHEN new.event_type='context.corrected' BEGIN SELECT RAISE(ABORT,'controlled dependency context failure'); END")
    db_conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        OwnerPlanningRecords(store).set_task_dependencies(second,[first])
    assert client.get(f'/api/tasks/{second}/dependencies').json()==[]
    assert store.context_snapshot(1,second)==before
    assert store.heartbeat(lease).fence==lease.fence


def test_pending_task_with_native_history_cannot_be_deleted(client,db_conn,seeded_project):
    """Even a queued original admission protects the task and its identity from a generic DELETE cascade."""
    first,_,_=tasks(client);store=SQLiteRunStore(get_db_path())
    run=store.admit(RunSpec(1,first,'synthetic-never-launched',1,'kept-admission','Original request','codex'))
    response=client.delete(f'/api/tasks/{first}')
    assert response.status_code==409
    assert store.get(1,run.run_id).prompt=='Original request'
    assert client.get(f'/api/tasks/{first}').status_code==200


def test_manual_task_with_dependents_requires_explicit_edge_removal_before_delete(client,db_conn,seeded_project):
    """Deleting a manual prerequisite cannot silently remove another task's requirements."""
    first,second,_=tasks(client)
    assert client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[first]}).status_code==201
    assert client.delete(f'/api/tasks/{first}').status_code==409
    assert client.get(f'/api/tasks/{second}/dependencies').json()[0]['depends_on_task_id']==first
    assert client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[]}).status_code==201
    assert client.delete(f'/api/tasks/{first}').status_code==204


def test_incoming_relationships_are_an_explicit_read_option(client,seeded_project):
    """The inspector can inspect dependents while older outgoing-only readers retain their response contract."""
    first,second,_=tasks(client)
    assert client.post(f'/api/tasks/{second}/dependencies',json={'depends_on':[first]}).status_code==201
    assert client.get(f'/api/tasks/{first}/dependencies').json()==[]
    assert client.get(f'/api/tasks/{first}/dependencies?include_incoming=true').json()==[{'task_id':second,'depends_on_task_id':first,'dependency_type':'blocks'}]
