"""Tests for CommunicationService in backend/communication/service.py."""

from unittest.mock import MagicMock

import pytest

from backend.communication.service import CommunicationService
from backend.flows.event_listeners import FlowEvent


@pytest.fixture()
def mock_bus():
    return MagicMock()


@pytest.fixture()
def service(mock_bus):
    return CommunicationService(bus=mock_bus)


class TestSend:
    def test_send_creates_message_and_thread(self, seeded_project, service, db_conn):
        msg_id = service.send(
            project_id=1,
            from_agent="dev-1",
            message="Hello team",
            to_agent="lead-1",
        )

        assert isinstance(msg_id, int)

        # Verify chat_messages row
        row = db_conn.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (msg_id,)
        ).fetchone()
        assert row is not None
        assert row["from_agent"] == "dev-1"
        assert row["to_agent"] == "lead-1"
        assert row["message"] == "Hello team"

        # Verify conversation_threads row was created
        threads = db_conn.execute(
            "SELECT * FROM conversation_threads WHERE project_id = 1"
        ).fetchall()
        assert len(threads) >= 1

    def test_send_emits_event(self, seeded_project, service, mock_bus):
        service.send(
            project_id=1,
            from_agent="dev-1",
            message="Test event",
            to_agent="lead-1",
        )

        mock_bus.emit.assert_called_once()
        event = mock_bus.emit.call_args[0][0]
        assert isinstance(event, FlowEvent)
        assert event.event_type == "message_sent"
        assert event.data["from_agent"] == "dev-1"
        assert event.data["to_agent"] == "lead-1"
        assert event.data["thread_id"] is not None

    def test_send_reuses_existing_thread(self, seeded_project, service, db_conn):
        # Create a thread first
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type, created_at)
               VALUES ('existing-thread', 1, 'team_sync', CURRENT_TIMESTAMP)"""
        )
        db_conn.commit()

        service.send(
            project_id=1,
            from_agent="dev-1",
            message="Using existing thread",
            thread_id="existing-thread",
        )

        # Verify no new thread was created
        threads = db_conn.execute(
            "SELECT * FROM conversation_threads WHERE project_id = 1"
        ).fetchall()
        assert len(threads) == 1
        assert threads[0]["thread_id"] == "existing-thread"


class TestGetMessages:
    def test_get_messages_by_project(self, seeded_project, service):
        service.send(project_id=1, from_agent="dev-1", message="msg 1")
        service.send(project_id=1, from_agent="dev-1", message="msg 2")
        service.send(project_id=1, from_agent="lead-1", message="msg 3")

        messages = service.get_messages(project_id=1)
        assert len(messages) == 3

    def test_get_messages_by_thread(self, seeded_project, service, db_conn):
        # Send two messages with different threads
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type, created_at)
               VALUES ('thread-a', 1, 'team_sync', CURRENT_TIMESTAMP)"""
        )
        db_conn.execute(
            """INSERT INTO conversation_threads
               (thread_id, project_id, thread_type, created_at)
               VALUES ('thread-b', 1, 'team_sync', CURRENT_TIMESTAMP)"""
        )
        db_conn.commit()

        service.send(project_id=1, from_agent="dev-1", message="in A", thread_id="thread-a")
        service.send(project_id=1, from_agent="dev-1", message="in B", thread_id="thread-b")

        messages = service.get_messages(project_id=1, thread_id="thread-a")
        assert len(messages) == 1
        assert messages[0]["message"] == "in A"

    def test_get_messages_unread_only(self, seeded_project, service):
        msg1 = service.send(project_id=1, from_agent="dev-1", message="unread", to_agent="lead-1")
        msg2 = service.send(project_id=1, from_agent="dev-1", message="read", to_agent="lead-1")

        service.mark_read([msg2], agent_id="lead-1")

        messages = service.get_messages(
            project_id=1, agent_id="lead-1", unread_only=True,
        )
        msg_ids = [m["id"] for m in messages]
        assert msg1 in msg_ids
        assert msg2 not in msg_ids


class TestMarkRead:
    def test_mark_read_idempotent(self, seeded_project, service, db_conn):
        msg_id = service.send(project_id=1, from_agent="dev-1", message="test", to_agent="lead-1")

        service.mark_read([msg_id], agent_id="lead-1")
        service.mark_read([msg_id], agent_id="lead-1")  # Second call should not error

        rows = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM message_reads WHERE message_id = ? AND agent_id = 'lead-1'",
            (msg_id,),
        ).fetchone()
        assert rows["cnt"] == 1


class TestGetUnreadCount:
    def test_get_unread_count(self, seeded_project, service):
        service.send(project_id=1, from_agent="dev-1", message="msg 1", to_agent="lead-1")
        msg2 = service.send(project_id=1, from_agent="dev-1", message="msg 2", to_agent="lead-1")

        service.mark_read([msg2], agent_id="lead-1")

        count = service.get_unread_count(project_id=1, agent_id="lead-1")
        assert count == 1


class TestGetThread:
    def test_get_thread_returns_none_for_missing(self, seeded_project, service):
        result = service.get_thread("nonexistent-thread-id")
        assert result is None

    def test_get_thread_returns_existing(self, seeded_project, service):
        # Send a message to create a thread
        service.send(project_id=1, from_agent="dev-1", message="hello")

        # The thread was auto-created — get all threads and verify one is retrievable
        messages = service.get_messages(project_id=1)
        assert len(messages) == 1
        thread_id = messages[0]["thread_id"]

        thread = service.get_thread(thread_id)
        assert thread is not None
        assert thread["thread_id"] == thread_id
