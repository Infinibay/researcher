"""In-memory registry mapping thread_id → threading.Event for instant reply notification.

Tools like ``AskTeamLeadTool`` register an event before waiting; ``SendMessageTool``
calls ``notify()`` after inserting a reply into the same thread.  This eliminates
polling and unblocks the waiting agent immediately.
"""

from __future__ import annotations

import threading


class ResponseEventRegistry:
    """Thread-safe singleton registry of pending reply events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}

    def register(self, thread_id: str) -> threading.Event:
        """Create (or return existing) ``threading.Event`` for *thread_id*."""
        with self._lock:
            if thread_id not in self._events:
                self._events[thread_id] = threading.Event()
            return self._events[thread_id]

    def notify(self, thread_id: str) -> None:
        """Set the event for *thread_id* if registered.  No-op otherwise."""
        with self._lock:
            evt = self._events.get(thread_id)
        if evt is not None:
            evt.set()

    def unregister(self, thread_id: str) -> None:
        """Remove the entry for *thread_id*."""
        with self._lock:
            self._events.pop(thread_id, None)

    def is_registered(self, thread_id: str) -> bool:
        """Return ``True`` if a pending event exists for *thread_id*."""
        with self._lock:
            return thread_id in self._events


# Module-level singleton
response_event_registry = ResponseEventRegistry()
