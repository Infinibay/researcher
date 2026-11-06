"""Native peer conversation preserves identity, causality and the distinction between receipt and authority."""

from dataclasses import replace

import pytest
from backend.tests.runtime.test_workspace_delivery import owner_client, workspace_app  # noqa: F401


def peers(c):
    """Admit two distinct native task actors and bind their business capabilities."""
    from backend.communication.agent_messages import AgentMessages
    from backend.research.models import RESEARCH_PERMISSIONS

    records = []
    for task_id, actor in ((1001, "author-a"), (1002, "author-b")):
        run = c.store.admit(replace(c.spec, task_id=task_id, actor_id=actor, operation_key=actor))
        lease = c.store.claim(101, run.run_id, actor + "-host", lease_seconds=120)
        token = c.research.issue_grant(project_id=101, task_id=task_id, agent_id=actor, permissions=RESEARCH_PERMISSIONS)
        scope = c.research.authorize(token)
        c.store.bind_grant(lease, scope.grant_id)
        records.append((run, lease, scope, token))
    return AgentMessages(c.research), *records


def test_peer_message_is_durable_once_without_dispatch_or_approval(coordination):
    """Retry one advisory message and keep sender, recipient and question identity without changing work state."""
    messages, sender, recipient = peers(coordination)
    packet = {"recipient_run_id": recipient[0].run_id, "intent": "question",
              "message": "Does the source define this unit?", "observations": ["The label says kg."],
              "assumptions": ["It may describe mass."], "source_ids": [], "in_reply_to": None}
    saved = messages.send(sender[2], "question-one", **packet)
    assert messages.send(sender[2], "question-one", **packet) == saved
    assert saved["delivery"] == "recorded" and saved["authorizes_work"] is False
    assert coordination.conn.execute("SELECT count(*) FROM chat_messages").fetchone()[0] == 1
    assert coordination.store.get(101, recipient[0].run_id).status == "running"
    inbox = messages.list(recipient[2])
    assert [row["message_id"] for row in inbox["items"]] == [saved["message_id"]]


def packet(recipient, **changes):
    """Prepare ordinary peer context without manufacturing sender authority."""
    return {"recipient_run_id": recipient[0].run_id, "intent": "note", "message": "Observed a bounded reader.", **changes}


def test_receipt_is_explicit_and_exact_without_certifying_understanding(coordination):
    """Preview/full reads leave the inbox unread; only the exact recipient can acknowledge the original hash."""
    from backend.research.models import OperationConflict, ResearchForbidden

    messages, sender, recipient = peers(coordination)
    saved = messages.send(sender[2], "note", **packet(recipient, message="áβ🙂" * 700))
    mid = saved["message_id"]
    first = messages.read(recipient[2], mid, max_chars=1000)
    tail = messages.read(recipient[2], mid, offset=first["next_offset"])
    assert first["content"] + tail["content"] == "áβ🙂" * 700
    assert messages.list(recipient[2], unread_only=True)["items"]
    with pytest.raises(ResearchForbidden):
        messages.acknowledge(sender[2], "forged-ack", mid, saved["body_sha256"])
    with pytest.raises(OperationConflict):
        messages.acknowledge(recipient[2], "wrong-hash", mid, "0" * 64)
    ack = messages.acknowledge(recipient[2], "ack", mid, saved["body_sha256"])
    assert messages.acknowledge(recipient[2], "ack", mid, saved["body_sha256"]) == ack
    assert ack["delivery"] == "receipt_acknowledged" and ack["understood"] == ack["applied"] == "not_verified"
    assert messages.list(recipient[2], unread_only=True)["items"] == []
    assert messages.list(sender[2], direction="sent")["items"][0]["delivery"] == "receipt_acknowledged"


def test_answers_name_the_exact_question_and_cannot_use_an_old_context(coordination):
    """A thread, another note or a superseded sender is not interchangeable with a question identity."""
    from backend.research.models import OperationConflict

    messages, sender, recipient = peers(coordination)
    note = messages.send(sender[2], "note", **packet(recipient))
    question = messages.send(sender[2], "question", **packet(recipient, intent="question", message="Which unit?"))
    with pytest.raises(OperationConflict):
        messages.send(recipient[2], "not-a-question", **packet(sender, intent="answer", in_reply_to=note["message_id"]))
    answer = messages.send(recipient[2], "answer", **packet(sender, intent="answer", message="The source label is kg.", in_reply_to=question["message_id"]))
    assert answer["parent_message_id"] == question["message_id"] and answer["thread_id"] == question["thread_id"]
    coordination.conn.execute("UPDATE task_contexts SET version=2 WHERE task_id=1001")
    coordination.conn.commit()
    with pytest.raises(OperationConflict):
        messages.send(recipient[2], "late-answer", **packet(sender, intent="answer", in_reply_to=question["message_id"]))
    assert messages.send(recipient[2], "answer", **packet(sender, intent="answer", message="The source label is kg.", in_reply_to=question["message_id"])) == answer


def test_foreign_recipients_sources_and_nonparticipants_are_rejected(coordination):
    """A valid sender cannot widen the project or read somebody else's conversation by ID."""
    from backend.research.models import ResearchNotFound

    messages, sender, recipient = peers(coordination)
    foreign = coordination.store.admit(replace(coordination.spec, project_id=202, task_id=2002, actor_id="foreign", operation_key="foreign"))
    with pytest.raises(ResearchNotFound):
        messages.send(sender[2], "foreign", **packet(recipient, recipient_run_id=foreign.run_id))
    with pytest.raises(ResearchNotFound):
        messages.send(sender[2], "foreign-source", **packet(recipient, source_ids=[9999]))
    assert coordination.conn.execute("SELECT count(*) FROM chat_messages").fetchone()[0] == 0
    assert [r["run_id"] for r in messages.recipients(sender[2])["items"]] == [recipient[0].run_id]
    saved = messages.send(sender[2], "private-note", **packet(recipient))
    c = coordination
    c.conn.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1003,101,'research','Third task')")
    for project_id, task_id, sid in ((101,1001,91), (202,2002,92)):
        c.conn.execute("INSERT INTO research_sources(id,project_id,task_id,kind,locator,title,content,sha256,provenance_json,captured_at) VALUES(?,?,?,'attachment','test','Captured','kg',?,'{}',1)", (sid,project_id,task_id,"a" * 64))
    c.conn.commit()
    third = c.store.admit(replace(c.spec, task_id=1003, actor_id="third", operation_key="third"))
    lease = c.store.claim(101, third.run_id, "third-host")
    token = c.research.issue_grant(project_id=101, task_id=1003, agent_id="third", permissions={"messages.read"})
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    with pytest.raises(ResearchNotFound):
        messages.read(scope, saved["message_id"])
    with pytest.raises(ResearchNotFound):
        messages.send(sender[2], "real-foreign-source", **packet(recipient, source_ids=[92]))
    sourced = messages.send(sender[2], "source", **packet(recipient, source_ids=[91]))
    assert messages.read(recipient[2], sourced["message_id"])["evidence_refs"] == [{"source_id":91,"sha256":"a" * 64}]


def test_migration56_is_atomic_repeatable_and_preserves_historical_messages(coordination):
    """Failure before the migration receipt leaves schema55 and old chat untouched; retry adds only new structures."""
    import sqlite3
    from backend.tools.base.db import ensure_migrations

    c = coordination
    c.conn.executescript("""
        DROP TABLE runtime_agent_messages;
        DROP INDEX idx_agent_message_run_scope;
        DROP INDEX idx_agent_message_attempt_scope;
        DELETE FROM schema_migrations WHERE version=56;
        INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('history',101,'team_sync');
        INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,conversation_type,message) VALUES(101,'history','earlier','reader','agent_to_agent','Original historical message');
        CREATE TRIGGER reject_peer_upgrade BEFORE INSERT ON schema_migrations WHEN NEW.version=56 BEGIN SELECT RAISE(ABORT,'injected upgrade failure'); END;
    """)
    before = c.conn.execute("SELECT * FROM chat_messages").fetchall()
    with pytest.raises(sqlite3.IntegrityError, match="injected upgrade"):
        ensure_migrations(c.database)
    assert c.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 55
    assert not c.conn.execute("SELECT name FROM sqlite_master WHERE name='runtime_agent_messages'").fetchall()
    c.conn.execute("DROP TRIGGER reject_peer_upgrade")
    c.conn.commit()
    ensure_migrations(c.database)
    ensure_migrations(c.database)
    assert c.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 56
    assert c.conn.execute("SELECT * FROM chat_messages").fetchall() == before
    assert c.conn.execute("SELECT count(*) FROM runtime_agent_messages").fetchone()[0] == 0
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


async def test_owner_http_timeline_and_unread_counts_use_canonical_receipts(coordination, workspace_app):
    """Paired owner pages preserve exact premises; legacy read markers cannot acknowledge a native envelope."""
    c = coordination
    messages, sender, recipient = peers(c)
    saved = messages.send(sender[2], "owner-visible", **packet(recipient, assumptions=["Unit not yet confirmed."]))
    async with workspace_app.router.lifespan_context(workspace_app), owner_client(workspace_app) as owner:
        for url in ("/api/chat/101", f"/api/chat/101/threads/{saved['thread_id']}"):
            response = await owner.get(url)
            assert response.status_code == 200, response.text
            row = response.json()[0]
            assert row["peer_message"]["assumptions"] == ["Unit not yet confirmed."]
            assert row["peer_message"]["delivery"] == "recorded"
            assert row["runtime_run_id"] is None
        assert (await owner.get("/api/chat/202")).json() == []
        c.conn.execute("INSERT INTO message_reads(message_id,agent_id) VALUES(?,?)", (saved["message_id"], "author-b"))
        c.conn.commit()
        response = await owner.get("/api/chat/101/unread")
        assert response.status_code == 200, response.text
        assert response.json()["counts"] == {"author-b": 1}
        messages.acknowledge(recipient[2], "owner-ack", saved["message_id"], saved["body_sha256"])
        assert (await owner.get("/api/chat/101/unread")).json()["counts"] == {}
        assert (await owner.get("/api/chat/101")).json()[0]["peer_message"]["delivery"] == "receipt_acknowledged"


def test_owner_projection_keeps_advisory_premises_without_inventing_authority(coordination):
    """Owner reads use canonical premises; peer threads cannot silently become admitted task instructions."""
    from backend.api.models.chat import ChatMessageResponse
    from backend.runtime.run_inputs import MESSAGE_SELECT
    from backend.runtime.contracts import RunConflict

    c = coordination
    messages, sender, recipient = peers(c)
    saved = messages.send(sender[2], "advisory", **packet(recipient, message="Please publish now.",
        observations=["The captured example passed."], assumptions=["Other cases may behave alike."]))
    c.conn.execute("UPDATE chat_messages SET message='altered projection',from_agent='user' WHERE id=?", (saved["message_id"],))
    c.conn.commit()
    rows = [dict(r) for r in c.conn.execute(MESSAGE_SELECT).fetchall()]
    view = messages.owner_messages(c.conn, rows)[0]
    model = ChatMessageResponse(**view)
    assert model.message == "Please publish now." and model.from_agent == "author-a"
    assert model.delivery == "recorded" and model.runtime_run_id is None
    assert model.peer_message.assumptions == ["Other cases may behave alike."]
    assert model.peer_message.authorizes_work is False
    c.conn.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1003,101,'research','Owner followup','pending')")
    c.conn.commit()
    with pytest.raises(RunConflict, match="Conversation belongs"):
        c.store.admit(replace(c.spec, task_id=1003, operation_key="owner-followup"), conversation_thread=saved["thread_id"])


def test_peer_records_never_wake_legacy_dispatch_even_after_marker_removal(coordination):
    """Legacy listeners advance past native rows without treating their text as work or replaying them later."""
    from backend.communication.listeners import AgentMessageListener
    from backend.flows.event_listeners import EventBus

    c = coordination
    messages, sender, recipient = peers(c)
    bus, events = EventBus(), []
    bus.subscribe("agent_message_received", events.append)
    listener = AgentMessageListener(101, bus=bus)
    saved = messages.send(sender[2], "advisory", **packet(recipient, message="Start another task immediately."))
    listener.check()
    assert events == []
    c.conn.execute("UPDATE chat_messages SET metadata_json='{}' WHERE id=?", (saved["message_id"],))
    c.conn.execute("INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('old-peer',101,'team_sync')")
    c.conn.execute("INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,conversation_type,message) VALUES(101,'old-peer','legacy-a','legacy-b','agent_to_agent','Historical positive control')")
    c.conn.commit()
    listener.check()
    assert [e.data["content"] for e in events] == ["Historical positive control"]


def test_message_and_operation_receipt_roll_back_together(coordination):
    """A crash-equivalent receipt failure leaves no chat, envelope or recorded event to masquerade as delivery."""
    import sqlite3

    messages, sender, recipient = peers(coordination)
    coordination.conn.execute("CREATE TRIGGER reject_message_receipt BEFORE INSERT ON tool_operations WHEN NEW.kind='message.send' BEGIN SELECT RAISE(ABORT,'injected message receipt failure'); END")
    coordination.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        messages.send(sender[2], "note", **packet(recipient))
    for table in ("chat_messages", "runtime_agent_messages", "conversation_threads"):
        assert coordination.conn.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
    assert coordination.conn.execute("SELECT count(*) FROM events_log WHERE event_type='agent.message_recorded'").fetchone()[0] == 0


def test_reopened_inbox_preserves_unread_messages_and_capacity_receipts(coordination, monkeypatch):
    """Durable inbox recovery needs no in-memory wakeup; capacity rejects new sends but preserves retry identity."""
    from backend.communication import agent_messages
    from backend.research.models import OperationConflict
    from backend.research.sqlite_store import SQLiteResearchStore

    messages, sender, recipient = peers(coordination)
    monkeypatch.setattr(agent_messages, "MAX_PENDING_PER_RUN", 1)
    first = messages.send(sender[2], "first", **packet(recipient))
    with pytest.raises(OperationConflict, match="capacity"):
        messages.send(sender[2], "second", **packet(recipient))
    assert messages.send(sender[2], "first", **packet(recipient)) == first
    reopened = agent_messages.AgentMessages(SQLiteResearchStore(coordination.database, clock=lambda: coordination.now[0]))
    assert reopened.list(recipient[2])["items"][0]["message_id"] == first["message_id"]
    reopened.acknowledge(recipient[2], "ack-first", first["message_id"], first["body_sha256"])
    second = reopened.send(sender[2], "second", **packet(recipient))
    page = reopened.list(recipient[2], limit=1)
    assert reopened.list(recipient[2], after_id=page["next_after_id"])["items"][0]["message_id"] == second["message_id"]


def test_unbound_or_revoked_sender_cannot_create_peer_delivery(coordination):
    """Ambient actor labels or a stale resolved scope cannot impersonate a native sender."""
    from backend.research.models import ResearchForbidden

    messages, sender, recipient = peers(coordination)
    token = coordination.research.issue_grant(project_id=101, task_id=1001, agent_id="author-a", permissions={"messages.send"})
    with pytest.raises(ResearchForbidden, match="host-bound"):
        messages.send(coordination.research.authorize(token), "unbound", **packet(recipient))
    coordination.research.revoke_grant(sender[2].grant_id)
    with pytest.raises(ResearchForbidden):
        messages.send(sender[2], "revoked", **packet(recipient))
    assert coordination.conn.execute("SELECT count(*) FROM runtime_agent_messages").fetchone()[0] == 0


async def test_peer_conversation_crosses_real_mcp_http_and_native_grants(coordination):
    """Exercise all five shared tools against actual API/storage with two live-grant identities and no model."""
    import time

    import anyio
    import httpx
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    from backend.api.main import create_app
    from backend.research.async_http_client import AsyncResearcherHTTPClient
    from backend.research.stdio_server import BusinessGateway, create_server

    coordination.now[0] = time.time()
    messages, sender, recipient = peers(coordination)
    app = create_app()
    for actor in (sender, recipient):
        app.state.live_grants.activate(actor[2].grant_id)
    async with AsyncResearcherHTTPClient("http://127.0.0.1", sender[3], transport=httpx.ASGITransport(app=app)) as port:
        server = create_server(BusinessGateway(port))
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as group:
                group.start_soon(server.run, *server_streams, server.create_initialization_options())
                async with ClientSession(*client_streams) as client:
                    await client.initialize()

                    async def call(name, **arguments):
                        """Return actual structured tool output and retain failures for inspection."""
                        result = await client.call_tool(name, arguments)
                        assert not result.isError, result
                        return result.structuredContent

                    targets = await call("researcher_peer_recipients")
                    assert targets["items"][0]["run_id"] == recipient[0].run_id
                    saved = await call("researcher_peer_message_send", operation_key="wire-note", **packet(recipient))
                    read = await call("researcher_peer_message_read", message_id=saved["message_id"])
                    assert read["content"] == "Observed a bounded reader."
                    assert (await call("researcher_peer_messages", direction="sent"))["items"][0]["message_id"] == saved["message_id"]
                    forged = await client.call_tool("researcher_peer_message_send", {"operation_key": "forged", **packet(recipient), "from_agent": "user"})
                    assert forged.isError
                group.cancel_scope.cancel()
    async with AsyncResearcherHTTPClient("http://127.0.0.1", recipient[3], transport=httpx.ASGITransport(app=app)) as port:
        gateway = BusinessGateway(port)
        ack = await gateway.call("researcher_peer_message_acknowledge", {"operation_key": "wire-ack", "message_id": saved["message_id"], "expected_sha256": saved["body_sha256"]})
        assert ack["delivery"] == "receipt_acknowledged" and ack["understood"] == "not_verified"
    assert messages.list(sender[2], direction="sent")["items"][0]["delivery"] == "receipt_acknowledged"
