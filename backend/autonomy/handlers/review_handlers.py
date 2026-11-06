"""Retired automatic review dispatch; an old review-ready label is not independent candidate review or owner acceptance authority."""

from __future__ import annotations

from typing import Any

from .base import EventHandler, _parse_payload


class ReviewHandler(EventHandler):
    """Point the actual task to its owner without claiming a reviewer, launching inference or converting an old verdict into approval."""

    def execute(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Return only a scoped task hint; exact native candidate/finding review must be independently admitted through its specific entry."""
        from backend.runtime.legacy_handoff import legacy_event_handoff

        task_id = _parse_payload(event).get("task_id")
        return legacy_event_handoff(event["project_id"], task_id) if task_id is not None else None
