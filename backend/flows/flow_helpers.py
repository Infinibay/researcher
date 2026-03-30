"""Standalone helper functions for MainProjectFlow.

These are module-level utilities extracted from main_project_flow.py
to keep that module focused on the flow class itself.
"""

from __future__ import annotations


def _pause_agent_loops(project_id: int) -> None:
    """Pause all agent loops so the flow can drive agents without interference."""
    from backend.autonomy.agent_loop import get_loop_manager

    mgr = get_loop_manager(project_id)
    if mgr:
        mgr.pause_all()


def _resume_agent_loops(project_id: int) -> None:
    """Resume agent loops for autonomous execution."""
    from backend.autonomy.agent_loop import get_loop_manager

    mgr = get_loop_manager(project_id)
    if mgr:
        mgr.resume_all()
