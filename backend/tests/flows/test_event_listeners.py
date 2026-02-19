"""Tests for event listeners."""

from __future__ import annotations

import json
import sqlite3
import time
from unittest.mock import MagicMock

import pytest

from backend.flows.event_listeners import (
    AllTasksDoneListener,
    EpicCreatedListener,
    EventBus,
    FlowEvent,
    ListenerManager,
    NewTaskCreatedListener,
    StagnationDetectedListener,
    TaskStatusChangedListener,
    UserMessageListener,
)


class TestEventBus:
    """Test the EventBus pub/sub system."""

    def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("test_event", handler)
        bus.emit(FlowEvent(
            event_type="test_event",
            project_id=1,
            entity_type="task",
        ))

        assert len(received) == 1
        assert received[0].event_type == "test_event"

    def test_multiple_handlers(self):
        bus = EventBus()
        results = []

        bus.subscribe("test", lambda e: results.append("a"))
        bus.subscribe("test", lambda e: results.append("b"))
        bus.emit(FlowEvent(event_type="test", project_id=1, entity_type="task"))

        assert results == ["a", "b"]

    def test_wildcard_handler(self):
        bus = EventBus()
        received = []

        bus.subscribe("*", lambda e: received.append(e.event_type))
        bus.emit(FlowEvent(event_type="event_a", project_id=1, entity_type="task"))
        bus.emit(FlowEvent(event_type="event_b", project_id=1, entity_type="task"))

        assert received == ["event_a", "event_b"]

    def test_unsubscribe(self):
        bus = EventBus()
        results = []

        def handler(e):
            results.append(1)

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        bus.emit(FlowEvent(event_type="test", project_id=1, entity_type="task"))

        assert results == []

    def test_handler_error_doesnt_stop_others(self):
        bus = EventBus()
        results = []

        def bad_handler(e):
            raise RuntimeError("oops")

        def good_handler(e):
            results.append("ok")

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        bus.emit(FlowEvent(event_type="test", project_id=1, entity_type="task"))

        assert results == ["ok"]


class TestFlowEvent:
    """Test FlowEvent dataclass."""

    def test_default_values(self):
        event = FlowEvent(
            event_type="test", project_id=1, entity_type="task",
        )
        assert event.entity_id is None
        assert event.data == {}
        assert event.timestamp is not None

    def test_with_data(self):
        event = FlowEvent(
            event_type="task_done",
            project_id=1,
            entity_type="task",
            entity_id=42,
            data={"status": "done"},
        )
        assert event.entity_id == 42
        assert event.data["status"] == "done"


class TestTaskStatusChangedListener:
    """Test task status change listener."""

    def test_detects_status_change(self, db_conn, executing_project):
        bus = EventBus()
        received = []
        bus.subscribe("task_status_changed", lambda e: received.append(e))

        # Insert a task_status_changed event into events_log
        db_conn.execute(
            """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type,
                    entity_id, event_data_json, created_at)
               VALUES (?, 'task_status_changed', 'trigger', 'task', 1, ?, CURRENT_TIMESTAMP)""",
            (executing_project, json.dumps({"new_status": "done", "old_status": "in_progress"})),
        )
        db_conn.commit()

        listener = TaskStatusChangedListener(executing_project, bus=bus, poll_interval=0.1)
        listener._last_event_id = 0  # Reset to catch our event
        listener.check()

        assert len(received) >= 1
        assert received[0].data["new_status"] == "done"

    def test_emits_sub_events(self, db_conn, executing_project):
        bus = EventBus()
        done_events = []
        review_events = []
        bus.subscribe("task_done", lambda e: done_events.append(e))
        bus.subscribe("task_review_ready", lambda e: review_events.append(e))

        # Insert events
        db_conn.execute(
            """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type,
                    entity_id, event_data_json, created_at)
               VALUES (?, 'task_status_changed', 'trigger', 'task', 1, ?, CURRENT_TIMESTAMP)""",
            (executing_project, json.dumps({"new_status": "done"})),
        )
        db_conn.execute(
            """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type,
                    entity_id, event_data_json, created_at)
               VALUES (?, 'task_status_changed', 'trigger', 'task', 2, ?, CURRENT_TIMESTAMP)""",
            (executing_project, json.dumps({"new_status": "review_ready"})),
        )
        db_conn.commit()

        listener = TaskStatusChangedListener(executing_project, bus=bus, poll_interval=0.1)
        listener._last_event_id = 0
        listener.check()

        assert len(done_events) == 1
        assert len(review_events) == 1


class TestNewTaskCreatedListener:
    """Test new task creation listener."""

    def test_detects_new_task(self, db_conn, executing_project):
        bus = EventBus()
        received = []
        bus.subscribe("new_task_created", lambda e: received.append(e))

        # Initialize listener AFTER fixture inserts, so it skips existing events
        listener = NewTaskCreatedListener(executing_project, bus=bus)

        # Now insert a new task_created event
        db_conn.execute(
            """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type,
                    entity_id, event_data_json, created_at)
               VALUES (?, 'task_created', 'trigger', 'task', 10, '{}', CURRENT_TIMESTAMP)""",
            (executing_project,),
        )
        db_conn.commit()

        listener.check()

        assert len(received) == 1
        assert received[0].entity_id == 10


class TestUserMessageListener:
    """Test user message listener."""

    def test_detects_user_message(self, db_conn, executing_project):
        bus = EventBus()
        received = []
        bus.subscribe("user_message_received", lambda e: received.append(e))

        # Insert a thread (thread_id is TEXT)
        import uuid
        thread_id = str(uuid.uuid4())
        db_conn.execute(
            """INSERT INTO conversation_threads
                   (thread_id, project_id, thread_type, created_at)
               VALUES (?, ?, 'user_chat', CURRENT_TIMESTAMP)""",
            (thread_id, executing_project),
        )
        db_conn.execute(
            """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, to_role,
                    message, conversation_type, created_at)
               VALUES (?, ?, 'user', 'project_lead',
                       'Hello!', 'user_to_agent', CURRENT_TIMESTAMP)""",
            (executing_project, thread_id),
        )
        db_conn.commit()

        listener = UserMessageListener(executing_project, bus=bus)
        listener._last_message_id = 0
        listener.check()

        assert len(received) == 1
        assert received[0].data["content"] == "Hello!"
        assert received[0].data["to_role"] == "project_lead"


class TestStagnationDetectedListener:
    """Test stagnation detection."""

    def test_no_stagnation_for_non_executing(self, db_conn, sample_project):
        bus = EventBus()
        received = []
        bus.subscribe("stagnation_detected", lambda e: received.append(e))

        listener = StagnationDetectedListener(sample_project, bus=bus)
        listener.check()

        assert len(received) == 0

    def test_stagnation_detected(self, db_conn, executing_project):
        bus = EventBus()
        received = []
        bus.subscribe("stagnation_detected", lambda e: received.append(e))

        # Set tasks as stuck (created long ago to match created_at query)
        db_conn.execute(
            """UPDATE tasks SET status = 'in_progress',
                   created_at = datetime('now', '-60 minutes')
               WHERE project_id = ?""",
            (executing_project,),
        )
        db_conn.commit()

        listener = StagnationDetectedListener(
            executing_project, bus=bus, stagnation_threshold_minutes=30,
        )
        listener.check()

        assert len(received) == 1


class TestAllTasksDoneListener:
    """Test all-tasks-done detection."""

    def test_not_all_done(self, db_conn, executing_project):
        bus = EventBus()
        received = []
        bus.subscribe("all_tasks_done", lambda e: received.append(e))

        listener = AllTasksDoneListener(executing_project, bus=bus)
        listener.check()

        assert len(received) == 0

    def test_all_done(self, db_conn, executing_project):
        bus = EventBus()
        received = []
        bus.subscribe("all_tasks_done", lambda e: received.append(e))

        db_conn.execute(
            "UPDATE tasks SET status = 'done' WHERE project_id = ?",
            (executing_project,),
        )
        db_conn.commit()

        listener = AllTasksDoneListener(executing_project, bus=bus)
        listener.check()

        assert len(received) == 1


class TestListenerManager:
    """Test the listener manager."""

    def test_start_and_stop_all(self, db_conn, executing_project):
        bus = EventBus()
        manager = ListenerManager(executing_project, bus=bus)

        manager.start_all()
        assert len(manager.listeners) == 9
        assert all(l.is_running for l in manager.listeners)

        manager.stop_all()
        assert len(manager.listeners) == 0

    def test_add_custom_listener(self, db_conn, executing_project):
        bus = EventBus()
        manager = ListenerManager(executing_project, bus=bus)

        custom = TaskStatusChangedListener(executing_project, bus=bus, poll_interval=0.1)
        manager.add_listener(custom)

        assert len(manager.listeners) == 1
        assert custom.is_running

        manager.stop_all()
