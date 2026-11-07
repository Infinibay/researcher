"""Exercise real SQLite contention, audit atomicity and startup readiness through the owner API."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import closing

import pytest
from starlette.testclient import TestClient


def test_creation_has_one_transactional_event(client, seeded_project, db_conn):
    """A task and its trigger event commit together without a second API audit copy."""
    response = client.post('/api/tasks', json={'project_id': seeded_project, 'title': 'One event'})
    assert response.status_code == 201, response.text
    task_id = response.json()['id']
    events = db_conn.execute("SELECT event_data_json FROM events_log WHERE event_type='task_created' AND entity_id=?", (task_id,)).fetchall()
    assert len(events) == 1


def test_failed_audit_rolls_back_task_and_dependencies(client, seeded_project, db_conn):
    """Rejecting the durable event cannot leave a successful orphan business transition."""
    db_conn.execute("CREATE TRIGGER reject_task_event BEFORE INSERT ON events_log WHEN NEW.event_type='task_created' BEGIN SELECT RAISE(ABORT,'audit rejected'); END")
    db_conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match='audit rejected'):
        client.post('/api/tasks', json={'project_id': seeded_project, 'title': 'Must roll back'})
    assert db_conn.execute("SELECT count(*) FROM tasks WHERE title='Must roll back'").fetchone()[0] == 0


def test_writer_contention_leaves_health_and_websocket_responsive(client, seeded_project, _isolated_db, monkeypatch):
    """Hold a real writer lock while independent API and WebSocket reads use the same event loop."""
    from backend.tools.base import db

    entered = threading.Event()
    original = db.get_connection

    def observed_connection(*args, **kwargs):
        """Observe the original insert reaching SQLite without replacing database execution."""
        conn = original(*args, **kwargs)
        conn.set_trace_callback(lambda sql: entered.set() if sql.lstrip().upper().startswith('INSERT INTO TASKS') else None)
        return conn

    def read_surfaces():
        """Read both owner surfaces before the blocked writer is allowed to commit."""
        assert client.get('/api/health').status_code == 200
        with client.websocket_connect('ws://localhost/ws?project_id=1', headers={'Origin': 'http://localhost'}) as socket:
            assert socket.receive_json()['type'] == 'events.page'
        return True

    monkeypatch.setattr(db, 'get_connection', observed_connection)
    responsive = False
    with closing(sqlite3.connect(_isolated_db)) as writer, ThreadPoolExecutor(max_workers=2) as pool:
        writer.execute('BEGIN IMMEDIATE')
        pending = pool.submit(client.post, '/api/tasks', json={'project_id': seeded_project, 'title': 'Wait once'})
        try:
            assert entered.wait(2), 'Original request never reached its write'
            read = pool.submit(read_surfaces)
            try:
                responsive = read.result(timeout=0.5)
            except TimeoutError:
                pass
            assert not pending.done(), 'The held SQLite lock did not exercise contention'
        finally:
            writer.rollback()
        assert pending.result(timeout=5).status_code == 201
        assert read.result(timeout=5)
    assert responsive, 'A blocked writer prevented health/WebSocket work on the event loop'


def test_startup_refuses_existing_foreign_key_damage(_isolated_db):
    """A migrated file with broken relationships cannot acquire owner access and begin serving."""
    from backend.api.main import create_app
    from backend.tools.base.db import ensure_migrations

    ensure_migrations(_isolated_db)
    with closing(sqlite3.connect(_isolated_db)) as db, db:
        db.execute("INSERT INTO tasks(project_id,type,title) VALUES(999,'research','Missing parent')")
    app = create_app()
    with pytest.raises(RuntimeError, match='integrity|foreign|relationship'), TestClient(app):
        pytest.fail('Corrupt relational data was accepted for serving')
    assert app.state.local_access.key_file is None


def test_readiness_requires_current_complete_schema(client, db_conn):
    """Reachability alone cannot report readiness after the required schema record disappears."""
    db_conn.execute('DELETE FROM schema_migrations WHERE version=65')
    db_conn.commit()
    assert client.get('/api/health/ready').status_code == 503


def test_busy_after_committed_effect_is_never_automatically_repeated(_isolated_db):
    """A lost post-commit observation must not turn a callback retry into duplicate business rows."""
    from backend.tools.base.db import execute_with_retry

    calls = []

    def committed_then_uncertain(conn):
        """Commit a real row, then inject an uncertain observation from the callback."""
        calls.append(True)
        conn.execute("INSERT INTO projects(name) VALUES('Original effect')")
        conn.commit()
        raise sqlite3.OperationalError('database is locked')

    with pytest.raises(sqlite3.OperationalError):
        execute_with_retry(committed_then_uncertain, _isolated_db, max_retries=2, base_delay=0)
    with closing(sqlite3.connect(_isolated_db)) as db:
        assert db.execute("SELECT count(*) FROM projects WHERE name='Original effect'").fetchone() == (1,)
    assert len(calls) == 1


@pytest.mark.parametrize('boundary', ['before', 'after'])
def test_process_loss_preserves_one_atomic_task_event(client, seeded_project, _isolated_db, boundary):
    """Kill an owned writer around its original commit; reopen the same file without replaying the create request."""
    import hashlib
    import subprocess
    import sys
    from pathlib import Path
    from backend.api.routes import tasks

    program = '''"""Crash an isolated API callback at its physical SQLite commit boundary."""
import hashlib,os,sqlite3,sys
from pathlib import Path
from backend.api.models.task import TaskCreate
from backend.api.routes import tasks
from backend.tools.base import db
assert hashlib.sha256(Path(tasks.__file__).read_bytes()).hexdigest()==sys.argv[3]
class CrashConnection(sqlite3.Connection):
    """Preserve the actual transaction while terminating before or after its commit."""
    def commit(self):
        """Terminate only this process at the requested physical boundary."""
        if sys.argv[2]=='before':os._exit(72)
        super().commit()
        os._exit(73)
def connection(*args,**kwargs):
    """Use the original database with real trigger/FK behavior and a commit observation seam."""
    conn=sqlite3.connect(sys.argv[1],factory=CrashConnection)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn
db.get_connection=connection
tasks.create_task(TaskCreate(project_id=1,title='Crash boundary'))
'''
    result = subprocess.run([sys.executable, '-c', program, _isolated_db, boundary,
                             hashlib.sha256(Path(tasks.__file__).read_bytes()).hexdigest()],
                            cwd=Path(__file__).resolve().parents[3], capture_output=True, timeout=15)
    assert result.returncode == (72 if boundary == 'before' else 73), result.stderr.decode()[-2000:]
    with closing(sqlite3.connect(_isolated_db)) as db:
        expected = 0 if boundary == 'before' else 1
        assert db.execute("SELECT count(*) FROM tasks WHERE title='Crash boundary'").fetchone() == (expected,)
        assert db.execute("SELECT count(*) FROM events_log WHERE event_type='task_created' AND json_extract(event_data_json,'$.title')='Crash boundary'").fetchone() == (expected,)
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
