"""A disconnected loop must not retain the global event subscription."""

import asyncio

from backend.api.websocket import ConnectionManager
from backend.flows.event_bus import EventBus, FlowEvent


class RecordingSocket:
    def __init__(self):
        self.messages = []
        self.received = asyncio.Event()

    async def accept(self):
        pass

    async def send_json(self, message):
        self.messages.append(message)
        self.received.set()


def test_reconnected_client_receives_events_after_previous_event_loop_closed():
    manager = ConnectionManager()
    manager._event_bus = EventBus()

    async def cycle(marker):
        socket = RecordingSocket()
        await manager.connect(socket, 101)
        try:
            manager._event_bus.emit(
                FlowEvent("task_updated", 101, "task", data={"marker": marker})
            )
            await asyncio.wait_for(socket.received.wait(), timeout=0.25)
            assert [message["data"] for message in socket.messages] == [
                {"marker": marker}
            ]
        finally:
            manager.disconnect(socket, 101)

    asyncio.run(cycle("first"))
    asyncio.run(cycle("second"))
