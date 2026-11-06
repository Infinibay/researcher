"""Read-only compatibility entry for retired task execution; historical state is not native admission, CI, review, owner acceptance or publication authority."""

from __future__ import annotations

from typing import Any

from backend.flows.state_models import DevelopmentState
from backend.runtime.legacy_handoff import legacy_event_handoff


class DevelopmentFlow:
    """Resolve the actual scoped task to its native owner without initializing agents, model loops, checks or PR services."""

    def __init__(self) -> None:
        """Keep historical snapshot fields readable without recreating old execution authority."""
        self.state = DevelopmentState()

    def kickoff(self, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a scoped owner hint; caller-supplied branches, approvals and actor labels cannot claim or complete work."""
        inputs = inputs or {}
        result = legacy_event_handoff(inputs.get("project_id"), inputs.get("task_id"))
        if result is None:
            raise ValueError("Task execution requires the native owner task workspace")
        self.state.project_id = result["project_id"]
        self.state.task_id = result["task_id"]
        self.state.task_title = result["title"]
        return result
