"""A disconnected event loop cannot retain sender tasks or hide later committed observations."""

import asyncio

from backend.api.websocket import ConnectionManager
from backend.tests.runtime.test_durable_events import RecordingSocket
from backend.tools.base.db import ensure_migrations


def test_reconnected_client_receives_events_after_previous_event_loop_closed(_isolated_db, db_conn):
    """A manager reused after orderly disconnect creates fresh loop-owned delivery tasks."""
    ensure_migrations(_isolated_db)
    db_conn.execute("INSERT INTO projects(id,name) VALUES(101,'Event lifecycle')")
    db_conn.commit()
    manager = ConnectionManager()

    async def cycle(marker):
        """Read the original committed marker and drain this loop before starting another."""
        db_conn.execute("INSERT INTO events_log(project_id,event_type,event_source,event_data_json) VALUES(101,'test.observed','test',?)", ('{"marker":"'+marker+'"}',))
        db_conn.commit()
        socket = RecordingSocket()
        await manager.connect(socket, 101, database=_isolated_db)
        try:
            await asyncio.wait_for(socket.received.wait(), timeout=1)
            assert socket.messages[-1]['events'][-1]['data'] == {'marker':marker}
        finally:
            await manager.disconnect(socket, 101)
        assert manager.active_connections == 0

    asyncio.run(cycle('first'))
    asyncio.run(cycle('second'))
