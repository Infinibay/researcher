"""Exact owner task notes survive reply loss without duplication or native authority."""

from concurrent.futures import ThreadPoolExecutor

from backend.tests.api.test_project_records import client, owner_app

__all__ = ['client', 'owner_app']


def original(client):
    """Create a real owner task and literal advisory note packet without native work."""
    task = client.post('/api/tasks', json={'project_id': 1, 'title': 'Relacionar entradas y salida', 'type': 'research'}).json()['id']
    return task, {'project_id': 1, 'operation_key': 'original-comment', 'author': 'user', 'content': 'El dato es un ejemplo, no una medición.', 'comment_type': 'approval'}


def test_same_task_note_recovers_original_receipt_after_lost_reply(client, db_conn, seeded_project):
    """Retried original bytes must return the first stored note rather than append another."""
    task, body = original(client)
    first = client.post(f'/api/tasks/{task}/comments', json=body)
    second = client.post(f'/api/tasks/{task}/comments', json=body)
    assert first.status_code == second.status_code == 201
    assert second.json()['id'] == first.json()['id']
    assert second.json() == first.json()
    assert first.json()['operation_key'] == body['operation_key']
    assert first.json()['project_id'] == 1
    assert first.json()['authorizes_work'] is False
    assert db_conn.execute('SELECT count(*) FROM task_comments WHERE task_id=?', (task,)).fetchone()[0] == 1
    assert db_conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0] == 0
    assert db_conn.execute('SELECT status FROM tasks WHERE id=?', (task,)).fetchone()[0] == 'backlog'


def test_changed_body_cannot_reuse_a_task_note_key(client, db_conn, seeded_project):
    """The original key protects literal content, author and type rather than just note existence."""
    task, body = original(client)
    assert client.post(f'/api/tasks/{task}/comments', json=body).status_code == 201
    for field, value in [('content', 'Otro contenido'), ('author', 'another-label'), ('comment_type', 'change_request')]:
        response = client.post(f'/api/tasks/{task}/comments', json={**body, field: value})
        assert response.status_code == 409
    assert client.get(f'/api/tasks/{task}/comments').json()[0]['content'] == body['content']


def test_task_note_cannot_be_retargeted_to_a_foreign_project(client, db_conn, seeded_project):
    """A task ID and captured project must agree before any note is appended."""
    task, body = original(client)
    project = client.post('/api/projects', json={'name': 'Otro proyecto'}).json()['id']
    assert client.post(f'/api/tasks/{task}/comments', json={**body, 'project_id': project}).status_code == 404
    assert client.get(f'/api/tasks/{task}/comments').json() == []


def test_concurrent_original_task_note_has_one_effect(client, db_conn, seeded_project):
    """Independent owner requests serialize the identity lookup and insert as one transaction."""
    task, body = original(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post(f'/api/tasks/{task}/comments', json=body), range(4)))
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()['id'] for response in responses}) == 1
    assert db_conn.execute('SELECT count(*) FROM task_comments WHERE task_id=?', (task,)).fetchone()[0] == 1


def test_note_and_receipt_rollback_together(client, db_conn, seeded_project):
    """An interruption while storing metadata cannot leave an unkeyed note that a retry duplicates."""
    import sqlite3

    import pytest

    task, body = original(client)
    db_conn.execute("CREATE TRIGGER reject_note_receipt BEFORE UPDATE OF metadata_json ON task_comments BEGIN SELECT RAISE(ABORT,'controlled receipt failure'); END")
    db_conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        client.post(f'/api/tasks/{task}/comments', json=body)
    assert db_conn.execute('SELECT count(*) FROM task_comments WHERE task_id=?', (task,)).fetchone()[0] == 0
    db_conn.execute('DROP TRIGGER reject_note_receipt')
    db_conn.commit()
    assert client.post(f'/api/tasks/{task}/comments', json=body).status_code == 201


def test_legacy_notes_remain_readable_and_distinct_without_claiming_retry_identity(client, db_conn, seeded_project):
    """Unkeyed older clients append independently; unrelated native metadata is preserved unchanged."""
    task, body = original(client)
    legacy = {key: value for key, value in body.items() if key not in {'project_id', 'operation_key'}}
    rows = [client.post(f'/api/tasks/{task}/comments', json=legacy).json() for _ in range(2)]
    assert rows[0]['id'] != rows[1]['id']
    assert rows[0]['operation_key'] != rows[1]['operation_key']
    db_conn.execute("INSERT INTO task_comments(task_id,author,content,metadata_json) VALUES(?,'native','Observed information','{\"source_kind\":\"native_advisory_comment\"}')", (task,))
    db_conn.commit()
    assert len(client.get(f'/api/tasks/{task}/comments').json()) == 3
    assert db_conn.execute("SELECT metadata_json FROM task_comments WHERE author='native'").fetchone()[0] == '{"source_kind":"native_advisory_comment"}'
