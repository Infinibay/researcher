"""Base class for DB-polling event listeners.

Split from event_listeners.py for modularity.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from backend.flows.event_bus import EventBus, event_bus

logger = logging.getLogger(__name__)


class BaseEventListener(ABC):
    """Abstract base for DB-polling event listeners."""

    def __init__(
        self,
        project_id: int,
        poll_interval: float = 5.0,
        bus: EventBus | None = None,
    ) -> None:
        self.project_id = project_id
        self.poll_interval = poll_interval
        self.bus = bus or event_bus
        self._running = False
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_check: str = datetime.now(UTC).isoformat()

    def start(self) -> None:
        """Start the listener in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            if self._stop_requested.is_set():
                raise RuntimeError("Listener is still stopping; cannot start another worker")
            return
        self._stop_requested.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name=f"{self.__class__.__name__}-p{self.project_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "%s started for project %d (interval=%.1fs)",
            self.__class__.__name__, self.project_id, self.poll_interval,
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Wake idle polling; retain ownership if a check has not terminated."""
        self._running = False
        self._stop_requested.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                raise TimeoutError(f"{self.__class__.__name__} check is still running")
            self._thread = None
        logger.info("%s stopped for project %d", self.__class__.__name__, self.project_id)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_requested.is_set():
            try:
                self.check()
                self._last_check = datetime.now(UTC).isoformat()
            except Exception:
                logger.exception("%s poll error", self.__class__.__name__)
            self._stop_requested.wait(timeout=self.poll_interval)

    @abstractmethod
    def check(self) -> None:
        """Override: inspect DB and emit events if conditions are met."""
        ...
