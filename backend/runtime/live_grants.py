"""Immediate host authority withdrawal and closure tracking for in-flight tools."""

import time
from contextlib import contextmanager
from threading import Event, Lock

from backend.research.models import ResearchForbidden


class LiveGrants:
    """Fence writes immediately while retaining registered tools until physical closure."""

    def __init__(self):
        """Create a process-local gate; durable grant validity still belongs to storage."""
        self._active: set[str] = set()
        self._lock = Lock()
        self._operations = {}
        self._withdrawn = set()
        self._closed = False

    def activate(self, grant_id: str):
        """Register the current host's runtime authority, without reviving closed tools."""
        with self._lock:
            self._active.add(grant_id)

    def withdraw(self, grant_id: str):
        """Reject future work and signal in-flight tools before waiting on SQL or I/O."""
        with self._lock:
            self._active.discard(grant_id)
            self._withdrawn.add(grant_id)
            for cancelled, _ in self._operations.get(grant_id, {}).values():
                cancelled.set()

    def allows(self, grant_id: str) -> bool:
        """Report live runtime registration; this does not prove worker termination."""
        with self._lock:
            return not self._closed and grant_id in self._active

    @contextmanager
    def operation(self, grant_id):
        """Register trusted tool ownership before spawn; exit only after actual cleanup.

        Non-runtime grants are still authenticated by the API/storage boundary.
        Withdrawal tombstones close the authorize→register race without SQL reads.
        """
        cancelled, closed, identity = Event(), Event(), object()
        with self._lock:
            if self._closed or grant_id in self._withdrawn:
                raise ResearchForbidden(
                    "Tool authority was withdrawn before worker admission"
                )
            self._operations.setdefault(grant_id, {})[identity] = (cancelled, closed)
        try:
            yield cancelled
        finally:
            with self._lock:
                closed.set()
                workers = self._operations[grant_id]
                workers.pop(identity)
                if not workers:
                    self._operations.pop(grant_id)

    def wait_closed(self, grant_id=None, *, timeout=5):
        """Wait for registered tools, raising on uncertainty rather than claiming closure.

        Call after withdraw/close to seal admission. This waits outside the lock,
        so workers and Stop can make progress independently of SQLite contention.
        """
        with self._lock:
            entries = (
                self._operations.get(grant_id, {})
                if grant_id is not None
                else {
                    identity: item
                    for group in self._operations.values()
                    for identity, item in group.items()
                }
            )
            events = [closed for _, closed in entries.values()]
        deadline = time.monotonic() + timeout
        for closed in events:
            if not closed.wait(max(0, deadline - time.monotonic())):
                raise TimeoutError("Host tool worker closure is not yet confirmed")

    def close(self):
        """Close admission and request all registered workers to stop; wait separately."""
        with self._lock:
            self._closed = True
            self._active.clear()
            for group in self._operations.values():
                for cancelled, _ in group.values():
                    cancelled.set()
