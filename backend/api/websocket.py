"""WebSocket connection manager for real-time updates."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from backend.flows.event_listeners import EventBus, FlowEvent, event_bus

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by project_id."""

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = {}
        self._event_bus: EventBus = event_bus
        self._subscribed = False
        self._on_event = None

    async def connect(self, websocket: WebSocket, project_id: int) -> None:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        if project_id not in self._connections:
            self._connections[project_id] = []
        self._connections[project_id].append(websocket)
        logger.info(
            "WebSocket connected for project %d (total: %d)",
            project_id,
            len(self._connections[project_id]),
        )

        if not self._subscribed:
            self._subscribe_to_events()
            self._subscribed = True

    def disconnect(self, websocket: WebSocket, project_id: int) -> None:
        """Remove a WebSocket connection."""
        if project_id in self._connections:
            self._connections[project_id] = [
                ws for ws in self._connections[project_id] if ws is not websocket
            ]
            if not self._connections[project_id]:
                del self._connections[project_id]
        if not self._connections and self._on_event is not None:
            self._event_bus.unsubscribe("*", self._on_event)
            self._on_event = None
            self._subscribed = False
        logger.info("WebSocket disconnected for project %d", project_id)

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception:
            logger.debug("Failed to send personal message", exc_info=True)

    async def broadcast(self, message: dict, project_id: int) -> None:
        """Send a message to all connections for a project."""
        if project_id not in self._connections:
            return
        disconnected = []
        for ws in self._connections[project_id]:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — one failed client must not fail the others
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws, project_id)

    async def broadcast_all(self, message: dict) -> None:
        """Send a message to all connected clients."""
        for project_id in list(self._connections.keys()):
            await self.broadcast(message, project_id)

    def _subscribe_to_events(self) -> None:
        """Subscribe to the global EventBus to relay events via WebSocket.

        The EventBus emits from background threads (listener threads and
        CrewAI flow threads), so we capture the asyncio event loop here
        (called from an async context) and use ``call_soon_threadsafe``
        to schedule the broadcast coroutine on the correct loop.
        """
        loop = asyncio.get_running_loop()

        def _on_event(event: FlowEvent) -> None:
            message = {
                "type": event.event_type,
                "project_id": event.project_id,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "data": event.data,
                "timestamp": event.timestamp,
            }

            def deliver():
                asyncio.create_task(self.broadcast(message, event.project_id))

            try:
                loop.call_soon_threadsafe(deliver)
            except RuntimeError:
                # Event loop closed during shutdown — safe to ignore.
                pass

        self._on_event = _on_event
        self._event_bus.subscribe("*", _on_event)
        logger.info("WebSocket manager subscribed to EventBus")

    @property
    def active_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# Global manager instance
manager = ConnectionManager()
