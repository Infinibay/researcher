"""Old task events produce scoped owner references, never work claims or automatic native commands."""

from __future__ import annotations

from typing import Any

from .base import EventHandler, _parse_payload


class TaskFlowHandler(EventHandler):
    """Acknowledge task availability/resume as historical context without assigning an agent or replaying execution."""

    def execute(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve the actual event project/task or leave a missing task unidentified; ambient role and context cannot supply it."""
        from backend.runtime.legacy_handoff import legacy_event_handoff

        task_id = _parse_payload(event).get("task_id")
        return legacy_event_handoff(event["project_id"], task_id) if task_id is not None else None
