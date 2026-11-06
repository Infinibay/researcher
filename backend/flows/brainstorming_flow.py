"""Read-only compatibility entry for retired project orchestration; native planning preserves attributed historical material without replaying old execution or approval."""

from __future__ import annotations

from typing import Any

from backend.flows.state_models import BrainstormState
from backend.runtime.legacy_handoff import legacy_project_handoff


class BrainstormingFlow:
    """Point an actual project to explicit native planning and owner controls without creating agents, tasks, repositories or project completion."""

    def __init__(self) -> None:
        """Keep historical state readable; constructing a compatibility object creates no runtime authority."""
        self.state = BrainstormState()

    def kickoff(self, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Resolve only actual project scope; old plan text, snapshots and approval flags remain data rather than start or acceptance commands."""
        inputs = inputs or {}
        hint = legacy_project_handoff(inputs.get("project_id"))
        self.state.project_id = hint["project_id"]
        self.state.project_name = hint["project_name"]
        return hint
