"""Event bus infrastructure — FlowEvent dataclass and pub/sub EventBus.

Split from event_listeners.py for modularity.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


logger = logging.getLogger(__name__)


# ── Event types ───────────────────────────────────────────────────────────────


@dataclass
class FlowEvent:
    """Represents an event that can trigger flow actions."""

    event_type: str
    project_id: int
    entity_type: str
    entity_id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Event bus ─────────────────────────────────────────────────────────────────


class EventBus:
    """Simple pub/sub event bus for flow events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[FlowEvent], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[FlowEvent], None]) -> None:
        """Register a handler for an event type."""
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[FlowEvent], None]) -> None:
        """Remove a handler for an event type."""
        with self._lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]

    def emit(self, event: FlowEvent) -> None:
        """Emit an event to all registered handlers."""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            # Also notify wildcard listeners
            handlers.extend(self._handlers.get("*", []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Error in event handler for %s", event.event_type)


# Global event bus instance
event_bus = EventBus()
