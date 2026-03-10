"""Stagnation detection helpers for INFINIBAY flows."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def detect_stagnation(project_id: int, cycles_threshold: int = 3) -> bool:
    """Detect if the project is stagnating.

    Criteria:
    - No tasks completed in the last N agent runs
    - 2+ tasks stuck in 'in_progress' or 'rejected'
    """

    def _query(conn: sqlite3.Connection) -> bool:
        # Check if there are recent agent runs (activity exists)
        recent_runs = conn.execute(
            """SELECT COUNT(*) as cnt FROM agent_runs
               WHERE project_id = ?
                 AND started_at >= datetime('now', ? || ' minutes')""",
            (project_id, f"-{cycles_threshold * 20}"),
        ).fetchone()

        # Check for task completions among those recent runs
        recent_completions = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE project_id = ? AND status = 'done'
                 AND completed_at >= datetime('now', ? || ' minutes')""",
            (project_id, f"-{cycles_threshold * 20}"),
        ).fetchone()

        stuck_tasks = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE project_id = ?
                 AND status IN ('in_progress', 'rejected')
                 AND created_at <= datetime('now', '-30 minutes')""",
            (project_id,),
        ).fetchone()

        has_activity = recent_runs and recent_runs["cnt"] > 0
        no_completions = recent_completions and recent_completions["cnt"] == 0
        many_stuck = stuck_tasks and stuck_tasks["cnt"] >= 2

        return has_activity and no_completions and many_stuck

    return execute_with_retry(_query)


def get_stuck_tasks(
    project_id: int, threshold_minutes: int = 30
) -> list[dict[str, Any]]:
    """Get tasks stuck in 'in_progress' or 'rejected' beyond threshold."""

    def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE project_id = ?
                 AND status IN ('in_progress', 'rejected')
                 AND created_at <= datetime('now', ? || ' minutes')
               ORDER BY created_at ASC""",
            (project_id, f"-{threshold_minutes}"),
        ).fetchall()
        return [dict(r) for r in rows]

    return execute_with_retry(_query)


def get_completed_task_count(project_id: int) -> int:
    """Count tasks with status 'done' for a project."""

    def _query(conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE project_id = ? AND status = 'done'",
            (project_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    return execute_with_retry(_query)


def has_active_review_run(task_id: int) -> bool:
    """Check if there is already a running reviewer agent_run for this task.

    Checks both code_reviewer and research_reviewer roles.
    """

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM agent_runs
               WHERE task_id = ?
                 AND role IN ('code_reviewer', 'research_reviewer')
                 AND status = 'running'""",
            (task_id,),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    return execute_with_retry(_query)
