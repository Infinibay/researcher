"""Base class for DB-polling event listeners.

Split from event_listeners.py for modularity.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

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
        self._thread: threading.Thread | None = None
        self._last_check: str = datetime.now(timezone.utc).isoformat()

    def start(self) -> None:
        """Start the listener in a background daemon thread."""
        if self._running:
            return
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

    def stop(self) -> None:
        """Signal the listener to stop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval * 2)
            self._thread = None
        logger.info("%s stopped for project %d", self.__class__.__name__, self.project_id)

    @property
    def is_running(self) -> bool:
        return self._running

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                self.check()
                self._last_check = datetime.now(timezone.utc).isoformat()
            except Exception:
                logger.exception("%s poll error", self.__class__.__name__)
            time.sleep(self.poll_interval)

    @abstractmethod
    def check(self) -> None:
        """Override: inspect DB and emit events if conditions are met."""
        ...
