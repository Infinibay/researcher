"""Read-only compatibility entry for scientific research now owned by the native runtime.

Historical state/reports remain readable. Legacy kickoff is an owner hint, not
admission, independent review, revision, scientific validation or acceptance.
"""

from __future__ import annotations

from typing import Any

from backend.flows.state_models import ResearchState
from backend.runtime.legacy_handoff import legacy_event_handoff


class ResearchFlow:
    """Resolve an old scientific entry to the actual scoped owner workspace without selecting agents or executing a legacy stage."""

    def __init__(self) -> None:
        """Retain historical state shape without initializing CrewAI, services or a model loop."""
        self.state = ResearchState()

    def kickoff(self, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return original native references or explicit owner admission; old review/revision labels confer no authority."""
        inputs = inputs or {}
        result = legacy_event_handoff(inputs.get("project_id"), inputs.get("task_id"))
        if result is None:
            raise ValueError("Scientific research requires an owner-managed task")
        self.state.project_id = result["project_id"]
        self.state.task_id = result["task_id"]
        self.state.task_title = result["title"]
        return result
