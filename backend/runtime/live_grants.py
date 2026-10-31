"""Host-local authority: revoke queued effects before a SQLite writer unlocks."""

from threading import Lock


class LiveGrants:
    def __init__(self):
        self._active: set[str] = set()
        self._lock = Lock()

    def activate(self, grant_id: str):
        with self._lock:
            self._active.add(grant_id)

    def withdraw(self, grant_id: str):
        with self._lock:
            self._active.discard(grant_id)

    def allows(self, grant_id: str) -> bool:
        with self._lock:
            return grant_id in self._active

    def close(self):
        with self._lock:
            self._active.clear()
