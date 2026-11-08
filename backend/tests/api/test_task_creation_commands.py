"""Exact owner task creation must recover one original effect, scope and selected metadata."""

import sqlite3

import pytest

from backend.tests.api.test_project_records import client, owner_app

__all__ = ["client", "owner_app"]


def test_repeated_task_creation_recovers_original_task_and_dependencies(client, db_conn, seeded_project):
    """A lost reply followed by exact delivery keeps one task, dependency and trigger-owned audit event."""
    parent = client.post('/api/tasks', json={'project_id': 1, 'title': 'Entrada'}).json()['id']
    body = {'project_id': 1, 'epic_id': 1, 'milestone_id': 1, 'title': 'Salida', 'description': 'CSV de id y value.', 'type': 'documentation', 'complexity': 'high', 'depends_on': [parent], 'operation_key': 'task-reply-lost'}
    before = db_conn.execute('SELECT count(*) FROM events_log').fetchone()[0]
    first, repeated = client.post('/api/tasks', json=body), client.post('/api/tasks', json=body)
    assert first.status_code == repeated.status_code == 201
    assert first.json() == repeated.json()
    assert first.json()['operation_key'] == body['operation_key']
    assert first.json()['estimated_complexity'] == 'high'
    assert db_conn.execute("SELECT count(*) FROM tasks WHERE title='Salida'").fetchone()[0] == 1
    assert db_conn.execute('SELECT task_id,depends_on_task_id FROM task_dependencies').fetchall()[0][:] == (first.json()['id'], parent)
    assert db_conn.execute('SELECT count(*) FROM events_log').fetchone()[0] == before + 1
    assert db_conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0] == 0


def test_task_key_cannot_authorize_changed_content_or_another_metadata_kind(client, db_conn, seeded_project):
    """An original receipt binds its entire task input and cannot be reused as group creation permission."""
    body = {'project_id': 1, 'title': 'Original', 'operation_key': 'original-task-key'}
    assert client.post('/api/tasks', json=body).status_code == 201
    assert client.post('/api/tasks', json={**body, 'title': 'Changed'}).status_code == 409
    assert client.post('/api/epics', json=body).status_code == 409
    assert db_conn.execute('SELECT count(*) FROM owner_planning_commands').fetchone()[0] == 1


@pytest.mark.parametrize('relation', ['epic', 'milestone', 'dependency'])
def test_task_creation_rejects_foreign_project_relations(client, db_conn, seeded_project, relation):
    """A task never imports parents or dependency edges from a different project."""
    other = client.post('/api/projects', json={'name': 'Otro proyecto'}).json()['id']
    group = client.post('/api/epics', json={'project_id': other, 'title': 'Ajeno'}).json()['id']
    milestone = client.post('/api/milestones', json={'epic_id': group, 'title': 'Ajeno'}).json()['id']
    task = client.post('/api/tasks', json={'project_id': other, 'title': 'Ajena'}).json()['id']
    selected = {'epic': {'epic_id': group}, 'milestone': {'milestone_id': milestone}, 'dependency': {'depends_on': [task]}}[relation]
    response = client.post('/api/tasks', json={'project_id': 1, 'title': 'Rechazada', 'operation_key': 'foreign-task', **selected})
    assert response.status_code == 404
    assert db_conn.execute("SELECT count(*) FROM tasks WHERE title='Rechazada'").fetchone()[0] == 0


def test_task_replay_retains_original_receipt_without_reverting_edit_or_recreating_deleted_task(client, db_conn, seeded_project):
    """The creation receipt is history; replay cannot undo an edit or recreate a subsequently deleted task."""
    body = {'project_id': 1, 'title': 'Antes', 'operation_key': 'task-history'}
    first = client.post('/api/tasks', json=body).json()
    assert client.put(f'/api/tasks/{first["id"]}', json={'title': 'Después'}).status_code == 200
    assert client.post('/api/tasks', json=body).json() == first
    assert client.get(f'/api/tasks/{first["id"]}').json()['title'] == 'Después'
    assert client.delete(f'/api/tasks/{first["id"]}').status_code == 204
    assert client.post('/api/tasks', json=body).status_code == 409
    replacement = client.post('/api/tasks', json={**body, 'operation_key': 'new-task'}).json()
    assert replacement['id'] != first['id']


def test_task_complexity_preserves_legacy_alias_and_rejects_ambiguous_values(client, seeded_project):
    """Existing estimated_complexity clients keep their chosen value; conflicting aliases are rejected explicitly."""
    first = client.post('/api/tasks', json={'project_id': 1, 'title': 'Compleja', 'estimated_complexity': 'high'})
    assert first.status_code == 201
    assert first.json()['estimated_complexity'] == 'high'
    assert client.post('/api/tasks', json={'project_id': 1, 'title': 'Ambigua', 'complexity': 'low', 'estimated_complexity': 'high'}).status_code == 422


def test_task_and_receipt_rollback_together(client, db_conn, seeded_project):
    """Receipt persistence failure must leave no task or trigger audit effect behind."""
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import get_db_path

    db_conn.execute("CREATE TRIGGER fail_task_receipt BEFORE INSERT ON owner_planning_commands BEGIN SELECT RAISE(ABORT,'controlled task receipt failure'); END")
    db_conn.commit()
    before = db_conn.execute('SELECT count(*) FROM events_log').fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        OwnerPlanningRecords(SQLiteRunStore(get_db_path())).create_task(project_id=1, title='Atomic task', operation_key='atomic-task')
    assert db_conn.execute("SELECT count(*) FROM tasks WHERE title='Atomic task'").fetchone()[0] == 0
    assert db_conn.execute('SELECT count(*) FROM events_log').fetchone()[0] == before
