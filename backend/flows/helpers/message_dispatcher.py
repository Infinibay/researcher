"""Retired message-to-model activation entry; stored messages remain attributed data and only an explicit native owner request starts work."""

from __future__ import annotations


def dispatch_message(
    project_id: int,
    agent_id: str,
    from_agent: str,
    content: str,
    thread_id: str | None = None,
) -> dict:
    """Return the actual project owner entry without resolving role aliases, constructing agents, inferring replies or treating a sender label as permission."""
    from backend.runtime.legacy_handoff import legacy_project_handoff

    return legacy_project_handoff(project_id)
