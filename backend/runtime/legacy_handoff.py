"""Expose documentary next actions from legacy task hints without admitting native work.

A processed legacy event is not a native command, an acceptance or proof that
legacy workers have stopped. Existing run identities are references only.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.runtime.task_profiles import OWNER_ONLY_LEGACY_TASK_TYPES


def native_owner_handoff(
    conn: sqlite3.Connection, project_id: int, task_id: int
) -> dict[str, Any] | None:
    """Return an owner hint for migrated/native-owned tasks, or None for remaining legacy work; reject missing and foreign task scope."""
    if any(type(value) is not int or value <= 0 for value in (project_id, task_id)):
        raise ValueError("Task and project identifiers must be positive integers")
    task = conn.execute(
        "SELECT type,status,title FROM tasks WHERE project_id=? AND id=?",
        (project_id, task_id),
    ).fetchone()
    if task is None:
        raise ValueError("Task not found in the specified project scope")
    native_runs = []
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_runs'"
    ).fetchone():
        native_runs = [
            {"run_id": row[0], "status": row[1], "context_version": row[2]}
            for row in conn.execute(
                "SELECT id,status,context_version FROM runtime_runs WHERE project_id=? AND task_id=? ORDER BY created_at,id",
                (project_id, task_id),
            )
        ]
    if task[0] not in OWNER_ONLY_LEGACY_TASK_TYPES and not native_runs:
        return None
    return {
        "delivery": "native_owner_handoff",
        "project_id": project_id,
        "task_id": task_id,
        "title": task[2],
        "status": task[1],
        "native_runs": native_runs,
        "inference_started_by_handoff": False,
        "event_authorizes_work": False,
        "next_action": "inspect_native_task_workspace"
        if native_runs
        else "owner_admit_in_task_workspace",
        "explanation": "Open the task workspace to inspect the current context and explicitly authorize work. This hint does not start, resume, review or accept it.",
    }


def legacy_event_handoff(project_id: int, task_id: int) -> dict[str, Any] | None:
    """Resolve a legacy event in its project, without selecting agents or changing task state."""
    from backend.autonomy.db import execute_with_retry

    return execute_with_retry(
        lambda conn: native_owner_handoff(conn, project_id, task_id)
    )
