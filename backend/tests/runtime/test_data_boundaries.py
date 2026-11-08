"""Keep real owner controls responsive to SQLite contention without claiming premature durable cancellation."""

import asyncio
import sqlite3
import threading
from contextlib import closing

import httpx

from backend.api.local_access import LocalAccess
from backend.api.main import create_app
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


async def test_stop_interrupts_original_worker_before_contended_write_finishes(service_setup, monkeypatch):
    """A real HTTP writer waits on SQLite while the same loop withdraws native authority and serves health."""
    from backend.runtime import sqlite_runs

    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    app = create_app(access=LocalAccess(pairing_key='contention-owner-code-at-least-32-characters'), runtime_service=service)
    entered = threading.Event()
    original = sqlite_runs.connect

    def observed_connection(*args, **kwargs):
        """Observe the task receipt writer transaction before its real contended SQLite lock."""
        conn = original(*args, **kwargs)
        conn.set_trace_callback(lambda sql: entered.set() if sql.strip().upper() == 'BEGIN IMMEDIATE' else None)
        return conn

    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
        paired = await client.post('/api/session', json={'code': 'contention-owner-code-at-least-32-characters'}, headers={'X-Researcher-Client': 'web'})
        assert paired.status_code == 200
        client.headers['X-Researcher-CSRF'] = paired.json()['csrf_token']
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        monkeypatch.setattr(sqlite_runs, 'connect', observed_connection)
        with closing(sqlite3.connect(s.c.database)) as writer:
            writer.execute('BEGIN IMMEDIATE')
            mutation = asyncio.create_task(client.post('/api/tasks', json={'project_id': 101, 'title': 'Contended one-time write'}))
            stop = None
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                stop = asyncio.create_task(client.post(f'/api/projects/101/runs/{run.run_id}/stop'))
                await asyncio.wait_for(native.interrupted.wait(), 0.5)
                assert not native.active()
                assert not stop.done(), 'Cancellation cannot claim its durable commit while another writer owns SQLite'
                health = await asyncio.wait_for(client.get('/api/health'), 0.5)
                assert health.status_code == 200
                assert not mutation.done()
            finally:
                writer.rollback()
                if stop is not None:
                    response = await asyncio.wait_for(stop, 5)
                    assert response.status_code == 202, response.text
                assert (await asyncio.wait_for(mutation, 5)).status_code == 201
        await service.wait(run.run_id)
        assert s.c.store.get(101, run.run_id).status == 'cancelled'
        assert len(native.prompts) == 1
        assert s.c.conn.execute("SELECT count(*) FROM tasks WHERE title='Contended one-time write'").fetchone()[0] == 1
        assert s.c.conn.execute("SELECT count(*) FROM events_log WHERE event_type='run.cancel_requested'").fetchone()[0] == 1
