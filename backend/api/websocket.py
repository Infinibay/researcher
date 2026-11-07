"""Resumable owner event delivery from committed SQLite, with independent bounded senders."""

import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

from backend.runtime.event_history import EventHistory

logger = logging.getLogger(__name__)


@dataclass
class _Client:
    """Own one socket's send lock and single page-producing task, without an event queue."""

    project_id: int
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task | None = None


class ConnectionManager:
    """Deliver retained events per socket; a slow reader cannot hold up another connection."""

    def __init__(self, *, poll_interval=0.25, send_timeout=5.0, page_size=100):
        """Set bounded delivery parameters without subscribing to a volatile global event loop."""
        if poll_interval <= 0 or send_timeout <= 0 or not 1 <= page_size <= 200:
            raise ValueError("Invalid event stream limits")
        self.poll_interval = poll_interval
        self.send_timeout = send_timeout
        self.page_size = page_size
        self._connections: dict[WebSocket, _Client] = {}

    async def connect(self, websocket, project_id, *, database, after_id=0):
        """Accept after validating a retained page, then follow committed rows from the supplied cursor."""
        reader = EventHistory(database)
        page = await asyncio.to_thread(reader.page, project_id, after_id=after_id, limit=self.page_size)
        await websocket.accept()
        client = _Client(project_id)
        self._connections[websocket] = client
        client.task = asyncio.create_task(self._stream(websocket, client, reader, page))

    async def _send(self, websocket, client, message):
        """Serialize ping and history frames with a deadline covering both lock and socket waits."""
        async with asyncio.timeout(self.send_timeout):
            async with client.lock:
                await websocket.send_json(message)

    async def _close_socket(self, websocket, code):
        """Bound transport closure so a stalled client cannot keep its sender alive indefinitely."""
        try:
            async with asyncio.timeout(self.send_timeout):
                await websocket.close(code=code)
        except Exception:
            logger.debug("Event socket already closed or unresponsive", exc_info=True)

    async def _stream(self, websocket, client, reader, page):
        """Hold one page at a time, send catch-up immediately and poll only after reaching its tail."""
        first = True
        try:
            while True:
                if first or page["events"] or page["reset_required"]:
                    await self._send(websocket, client, page)
                    first = page["reset_required"]
                cursor = int(page["resume_after_id"] if page["reset_required"] else page["next_after_id"])
                if not page["has_more"] and not page["reset_required"]:
                    await asyncio.sleep(self.poll_interval)
                page = await asyncio.to_thread(reader.page, client.project_id, after_id=cursor, limit=self.page_size)
        except TimeoutError:
            await self._close_socket(websocket, 1013)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Durable event stream unavailable")
            await self._close_socket(websocket, 1011)
        finally:
            if self._connections.get(websocket) is client:
                self._connections.pop(websocket)

    async def disconnect(self, websocket, project_id):
        """Retire and await only this project's original sender, including cancelled transport waits."""
        client = self._connections.get(websocket)
        if client is None or client.project_id != project_id:
            return
        self._connections.pop(websocket)
        if client.task is not None:
            client.task.cancel()
            await asyncio.gather(client.task, return_exceptions=True)

    async def send_personal_message(self, message, websocket):
        """Send a bounded keepalive through the same per-socket writer as event pages."""
        client = self._connections.get(websocket)
        if client is not None:
            try:
                await self._send(websocket, client, message)
            except Exception:
                await self._close_socket(websocket, 1013)
                await self.disconnect(websocket, client.project_id)

    async def close(self):
        """Close and drain all senders owned by this application instance during shutdown."""
        for websocket, client in list(self._connections.items()):
            await self.disconnect(websocket, client.project_id)
            await self._close_socket(websocket, 1001)

    @property
    def active_connections(self):
        """Count registered senders rather than infer runtime or provider activity."""
        return len(self._connections)
