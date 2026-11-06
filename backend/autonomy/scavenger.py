"""Compatibility hook for retired idle task recovery.

Every persisted task category now requires explicit native owner admission. Idle
polling cannot reconstruct work authority from missing events or delete an old
worktree that may contain unimported files. Project-level producer retirement and
physical closure are separate; returning zero proves neither has happened.
"""

from __future__ import annotations


class Scavenger:
    """Keep the old scheduler hook without creating task events, claiming work, running inference or cleaning up files."""

    def __init__(self, agent_id: str, project_id: int, role: str) -> None:
        """Retain the historical caller identity as data; no role authorizes recovery."""
        self.agent_id = agent_id
        self.project_id = project_id
        self.role = role

    def scavenge(self) -> int:
        """Return zero created events; the owner workspace is the only task execution entry, including before first admission."""
        return 0
