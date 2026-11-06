"""Legacy message, health, progress and rejection events are owner hints; they never dispatch models, reconstruct tasks or infer project completion."""

from __future__ import annotations

from typing import Any

from .base import EventHandler, _parse_payload


class MessageHandler(EventHandler):
    """Keep old agent messages documentary; a sender name, acknowledgement or prior thread does not authorize a new model turn."""

    def execute(self, event: dict[str, Any]) -> dict[str, Any]:
        """Resolve the actual project without replying, forwarding an instruction or erasing stored conversation."""
        from backend.runtime.legacy_handoff import legacy_project_handoff

        return legacy_project_handoff(event["project_id"])


class HealthCheckHandler(MessageHandler):
    """Expose the owner entry for old stagnation hints without reassigning tasks or spending an intervention turn."""


class ProgressEvalHandler(MessageHandler):
    """Expose the owner entry for old progress/all-done hints without model classification, report generation or project completion."""


class ReworkHandler(EventHandler):
    """Keep rejection/feedback as context for the owner instead of an unbounded automatic repair loop."""

    def execute(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Identify the actual task without changing its status, assignee, revision count or original review evidence."""
        from backend.runtime.legacy_handoff import legacy_event_handoff

        task_id = _parse_payload(event).get("task_id")
        return legacy_event_handoff(event["project_id"], task_id) if task_id is not None else None
