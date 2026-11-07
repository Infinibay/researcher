"""Committed event pages, cursor expiry and independent bounded WebSocket delivery."""

import asyncio
import json

import pytest


def event_log(c):
    """Bind the production reader to the fixture's migrated SQLite database."""
    from backend.runtime.event_history import EventHistory

    return EventHistory(c.database)


def append_events(c, count, project_id=101):
    """Commit tied-timestamp observations and return the real globally unique sequence IDs."""
    ids = []
    for index in range(count):
        ids.append(c.conn.execute("INSERT INTO events_log(project_id,event_type,event_source,event_data_json,created_at) VALUES(?,'run.observed','runtime',?,'2026-11-07 00:00:00')", (project_id, json.dumps({"index": index}))).lastrowid)
    c.conn.commit()
    return ids


def test_pages_recover_more_than_one_page_with_concurrent_arrivals_and_equal_times(coordination):
    """Ascending durable IDs cover every retained row once despite another project's gaps and new writes."""
    c = coordination
    before = c.conn.execute("SELECT COALESCE(MAX(id),0) FROM events_log").fetchone()[0]
    ids = append_events(c, 213)
    append_events(c, 5, 202)
    reader = event_log(c)
    first = reader.page(101, after_id=before, limit=100)
    assert first["has_more"] is True
    ids += append_events(c, 31)
    found = first["events"]
    cursor = first["next_after_id"]
    while True:
        page = reader.page(101, after_id=int(cursor), limit=100)
        found += page["events"]
        cursor = page["next_after_id"]
        if not page["has_more"]:
            break
    assert [int(event["event_id"]) for event in found] == ids
    assert all(event["project_id"] == 101 for event in found)
    assert len({event["timestamp"] for event in found}) == 1
    assert reader.page(101, after_id=int(cursor))["events"] == []
    for options in ({"after_id": -1}, {"after_id": True}, {"limit": 201}):
        with pytest.raises(ValueError):
            reader.page(101, **options)


def test_deleted_events_require_explicit_snapshot_and_watermark_rolls_back(coordination):
    """A retained-history hole cannot be disguised as an empty successful catch-up page."""
    c = coordination
    ids = append_events(c, 8)
    c.conn.execute("DELETE FROM events_log WHERE id=?", (ids[3],))
    c.conn.rollback()
    assert event_log(c).page(101)["reset_required"] is False
    c.conn.execute("DELETE FROM events_log WHERE id=?", (ids[3],))
    c.conn.commit()
    expired = event_log(c).page(101, after_id=ids[1])
    assert expired["reset_required"] is True
    assert expired["events"] == [] and expired["resume_after_id"] == str(ids[3])
    assert event_log(c).page(202)["reset_required"] is False
    recovered = event_log(c).page(101, after_id=ids[3])
    assert [int(item["event_id"]) for item in recovered["events"]] == ids[4:]


class RecordingSocket:
    """Observe socket frames and optionally emulate a client that never drains a send."""

    def __init__(self, *, blocked=False):
        """Initialize independently observable send progress and close status."""
        self.messages = []
        self.blocked = blocked
        self.received = asyncio.Event()
        self.closed = asyncio.Event()
        self.code = None

    async def accept(self):
        """Accept the test transport without creating a real network listener."""

    async def send_json(self, message):
        """Record a frame or remain backpressured until the manager's timeout cancels it."""
        if self.blocked:
            await asyncio.Event().wait()
        self.messages.append(message)
        self.received.set()

    async def close(self, code=1000):
        """Record the close code and release observers waiting for slow-client retirement."""
        self.code = code
        self.closed.set()


async def test_slow_client_cannot_delay_healthy_delivery_or_leave_sender_tasks(coordination):
    """Each client holds one bounded page and closes independently when it cannot drain writes."""
    from backend.api.websocket import ConnectionManager

    c = coordination
    ids = append_events(c, 205)
    manager = ConnectionManager(poll_interval=0.01, send_timeout=0.05, page_size=100)
    slow, fast = RecordingSocket(blocked=True), RecordingSocket()
    await manager.connect(slow, 101, database=c.database)
    await manager.connect(fast, 101, database=c.database)
    try:
        await asyncio.wait_for(slow.closed.wait(), 1)
        assert slow.code == 1013
        for _ in range(100):
            delivered = [int(event["event_id"]) for frame in fast.messages for event in frame.get("events", [])]
            if ids[-1] in delivered:
                break
            await asyncio.sleep(0.005)
        assert [identity for identity in delivered if identity in ids] == ids
        assert all(len(frame.get("events", [])) <= 100 for frame in fast.messages)
        assert manager.active_connections == 1
    finally:
        await manager.disconnect(slow, 101)
        await manager.disconnect(fast, 101)
    assert manager.active_connections == 0


async def test_reconnected_stream_resumes_durable_cursor_without_volatile_bus(coordination):
    """Reconnect replays committed rows written while disconnected and excludes already applied IDs."""
    from backend.api.websocket import ConnectionManager

    c = coordination
    first_ids = append_events(c, 3)
    manager = ConnectionManager(poll_interval=0.01)
    first = RecordingSocket()
    await manager.connect(first, 101, database=c.database)
    await asyncio.wait_for(first.received.wait(), 1)
    cursor = int(first.messages[-1]["next_after_id"])
    await manager.disconnect(first, 101)
    assert cursor == first_ids[-1]
    retained = append_events(c, 250)
    second = RecordingSocket()
    await manager.connect(second, 101, database=c.database, after_id=cursor)
    try:
        for _ in range(100):
            delivered = [int(event["event_id"]) for frame in second.messages for event in frame.get("events", [])]
            if retained[-1] in delivered:
                break
            await asyncio.sleep(0.005)
        assert delivered == retained
    finally:
        await manager.disconnect(second, 101)
