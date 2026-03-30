"""Base event handler and shared utilities."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from backend.autonomy.events import update_event_status

logger = logging.getLogger(__name__)


def _parse_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Parse payload_json from an event dict."""
    raw = event.get("payload_json", "{}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


class EventHandler(ABC):
    """Base class for event handlers."""

    @abstractmethod
    def execute(self, event: dict[str, Any]) -> None:
        """Execute the work for this event."""
        ...

    def save_progress(self, event: dict[str, Any], progress: dict[str, Any]) -> None:
        """Save progress checkpoint for crash recovery."""
        update_event_status(event["id"], "in_progress", progress=progress)
