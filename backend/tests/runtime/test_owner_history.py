"""Conversation archive and historical inbox remain scoped owner operations after old scheduling services are removed."""

import sqlite3

import pytest

from backend.tests.runtime.test_workspace_delivery import owner_client, workspace_app

__all__ = ["workspace_app"]


async def test_archive_requires_the_actual_project_and_preserves_native_receipts(coordination, workspace_app):
    """Archive is idempotent presentation state, not permission to cancel work, erase messages or acknowledge another actor's question."""
    from backend.research.models import OperationConflict
    from backend.tests.runtime.test_agent_messages import packet, peers

    c = coordination
    messages, sender, recipient = peers(c)
    saved = messages.send(sender[2], "archive-question", **packet(recipient, intent="question"))
    thread = saved["thread_id"]
    before = tuple(c.conn.execute("SELECT * FROM chat_messages WHERE id=?", (saved["message_id"],)).fetchone())
    async with workspace_app.router.lifespan_context(workspace_app), owner_client(workspace_app) as owner:
        wrong = await owner.post(f"/api/chat/202/threads/{thread}/archive")
        assert wrong.status_code == 404
        assert c.conn.execute("SELECT status FROM conversation_threads WHERE thread_id=?", (thread,)).fetchone()[0] == "active"
        assert (await owner.post("/api/chat/101/threads/missing/archive")).status_code == 404
        first = await owner.post(f"/api/chat/101/threads/{thread}/archive")
        assert first.status_code == 200, first.text
        assert (await owner.post(f"/api/chat/101/threads/{thread}/archive")).json() == first.json()
        viewed = await owner.get(f"/api/chat/101/threads/{thread}")
        assert viewed.json()[0]["peer_message"]["delivery"] == "recorded"
    assert tuple(c.conn.execute("SELECT * FROM chat_messages WHERE id=?", (saved["message_id"],)).fetchone()) == before
    assert c.conn.execute("SELECT count(*) FROM events_log WHERE event_type='conversation.archived'").fetchone()[0] == 1
    assert c.conn.execute("SELECT count(*) FROM agent_events").fetchone()[0] == 0
    assert c.store.get(101, sender[0].run_id).status == c.store.get(101, recipient[0].run_id).status == "running"
    with pytest.raises(OperationConflict, match="closed"):
        messages.send(recipient[2], "closed-reply", recipient_run_id=sender[0].run_id, intent="answer", message="An answer", in_reply_to=saved["message_id"])
    assert messages.read(recipient[2], saved["message_id"])["delivery"] == "recorded"


def test_archive_and_durable_event_commit_or_rollback_together(coordination):
    """A failed event insert cannot leave a silently archived conversation; retry records exactly one transition."""
    from backend.communication.owner_history import OwnerHistory

    c = coordination
    c.conn.execute("INSERT INTO conversation_threads(thread_id,project_id,thread_type)VALUES('archive-atomic',101,'user_chat')")
    c.conn.execute("CREATE TRIGGER fail_archive BEFORE INSERT ON events_log WHEN NEW.event_type='conversation.archived' BEGIN SELECT RAISE(ABORT,'archive-event-failed'); END")
    c.conn.commit()
    history = OwnerHistory(c.store)
    with pytest.raises(sqlite3.IntegrityError, match="archive-event-failed"):
        history.archive(101, "archive-atomic")
    assert c.conn.execute("SELECT status FROM conversation_threads WHERE thread_id='archive-atomic'").fetchone()[0] == "active"
    c.conn.execute("DROP TRIGGER fail_archive")
    c.conn.commit()
    history.archive(101, "archive-atomic")
    history.archive(101, "archive-atomic")
    assert c.conn.execute("SELECT count(*) FROM events_log WHERE event_type='conversation.archived'").fetchone()[0] == 1


async def test_owner_historical_inbox_keeps_read_markers_without_reclassifying_native_messages(coordination, workspace_app):
    """Historical role labels are only read filters; canonical native ownership survives removal of advisory metadata."""
    from backend.tests.runtime.test_agent_messages import packet, peers

    c = coordination
    messages, sender, recipient = peers(c)
    saved = messages.send(sender[2], "native-peer", **packet(recipient))
    c.conn.execute("UPDATE chat_messages SET metadata_json='{}' WHERE id=?", (saved["message_id"],))
    c.conn.execute("INSERT INTO roster(agent_id,name,role)VALUES('author-b','Historical reader','researcher')")
    c.conn.execute("INSERT INTO conversation_threads(thread_id,project_id,thread_type)VALUES('old-inbox',101,'team_sync'),('foreign-inbox',202,'team_sync')")
    ids = []
    for text, target, role in (("read history", "author-b", None), ("role history", None, "researcher"), ("broadcast history", None, None)):
        ids.append(c.conn.execute("INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,to_role,message)VALUES(101,'old-inbox','old-sender',?,?,?)", (target, role, text)).lastrowid)
    c.conn.execute("INSERT INTO message_reads(message_id,agent_id)VALUES(?,'author-b')", (ids[0],))
    c.conn.execute("INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,message)VALUES(202,'foreign-inbox','old-sender','author-b','Foreign history')")
    c.conn.commit()
    async with workspace_app.router.lifespan_context(workspace_app), owner_client(workspace_app) as owner:
        path = "/api/chat/101/agent/author-b"
        assert [m["id"] for m in (await owner.get(path)).json()] == ids
        assert [m["id"] for m in (await owner.get(path, params={"unread_only": True})).json()] == ids[1:]
        assert [m["id"] for m in (await owner.get(path, params={"limit": 1})).json()] == ids[-1:]
        timeline = (await owner.get("/api/chat/101")).json()
        assert any(m["id"] == saved["message_id"] and m["peer_message"] for m in timeline)
    assert c.conn.execute("SELECT count(*) FROM message_reads").fetchone()[0] == 1
    assert c.conn.execute("SELECT count(*) FROM agent_events").fetchone()[0] == 0
