"""Expose scoped owner policy from retained project entries without admitting native work.

A documentary hint is not a native command, acceptance, reconstructed session or
proof that an external historical worker has stopped.
"""

from __future__ import annotations

import sqlite3
from typing import Any



def native_project_handoff(
    conn: sqlite3.Connection, project_id: int
) -> dict[str, Any] | None:
    """Return a project-only exclusion hint from actual native admission history; do not guess a task, grant authority or infer legacy process closure."""
    if type(project_id) is not int or project_id <= 0:
        raise ValueError("Project identifier must be a positive integer")
    project = conn.execute(
        "SELECT name FROM projects WHERE id=?", (project_id,)
    ).fetchone()
    if project is None:
        raise ValueError("Project not found in the specified scope")
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_runs'"
        ).fetchone()
        is None
    ):
        return None
    admission = conn.execute(
        "SELECT id FROM runtime_runs WHERE project_id=? ORDER BY created_at,id LIMIT 1",
        (project_id,),
    ).fetchone()
    if admission is None:
        return None
    return {
        "delivery": "native_owner_handoff",
        "scope": "project",
        "project_id": project_id,
        "project_name": project[0],
        "native_admission_run_id": admission[0],
        "event_authorizes_work": False,
        "inference_started_by_handoff": False,
        "legacy_execution_closure": "not_assessed",
        "next_action": "inspect_native_project_workspace",
        "explanation": "This project has native admission history. Inspect the current owner workspace; a legacy message, health check or recovery does not authorize work, select a task or prove that old workers stopped.",
    }


def project_owner_entry(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    """Resolve every actual project to native owner policy while keeping evidence of prior admission distinct from the policy itself."""
    hint = native_project_handoff(conn, project_id)
    if hint is not None:
        return hint
    project = conn.execute("SELECT name FROM projects WHERE id=?", (project_id,)).fetchone()
    return {
        "delivery": "native_owner_handoff",
        "scope": "project",
        "project_id": project_id,
        "project_name": project[0],
        "native_admission_run_id": None,
        "event_authorizes_work": False,
        "inference_started_by_handoff": False,
        "legacy_execution_closure": "not_assessed",
        "next_action": "inspect_native_project_workspace",
        "explanation": "Project work requires explicit native owner admission, including before the first run. Inspect stored requirements, plans, ideas and current work in the owner workspace. This policy hint does not authorize execution, infer project acceptance, recreate old sessions or prove old workers have stopped.",
    }


def legacy_project_handoff(project_id: int) -> dict[str, Any]:
    """Return an actual scoped owner entry before any old activation; no native history is fabricated when it is absent."""
    from backend.tools.base.db import execute_with_retry

    return execute_with_retry(lambda conn: project_owner_entry(conn, project_id))




