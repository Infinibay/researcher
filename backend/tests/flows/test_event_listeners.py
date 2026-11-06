"""Retained shared event bus contracts, independent of removed polling listeners."""

from backend.flows.event_bus import EventBus, FlowEvent


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
