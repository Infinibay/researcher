"""Compatibility entry for exploratory investigations now executed by the native owner.

Historical flow state and reports remain readable. Calling this adapter supplies
an owner hint only; it performs no inference, task claim, rescue or review.
"""

from __future__ import annotations

from typing import Any

from backend.flows.state_models import InvestigationState
from backend.runtime.legacy_handoff import legacy_event_handoff


class InvestigationFlow:
    """Keep the old kickoff entry as a read-only bridge to explicit native admission."""

    def __init__(self) -> None:
        """Retain a compatibility state object without initializing a legacy flow engine."""
        self.state = InvestigationState()

    def kickoff(self, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate actual project/task scope and return existing native references or the owner admission action."""
        inputs = inputs or {}
        result = legacy_event_handoff(inputs.get("project_id"), inputs.get("task_id"))
        if result is None:
            raise ValueError(
                "InvestigationFlow requires an owner-managed investigation task"
            )
        self.state.project_id = result["project_id"]
        self.state.task_id = result["task_id"]
        self.state.task_title = result["title"]
        return result
