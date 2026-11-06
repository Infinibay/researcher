"""Owner project metadata and operational labels, independent of agent flows; counts and labels never authorize native work or project completion."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.tools.base.db import execute_with_retry


def load_project_state(project_id: int) -> dict[str, Any] | None:
    """Read original project fields and project-local task/epic counts; status labels are observations, not runtime liveness or accepted results."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        """Collect stored metadata and aggregate only rows in the requested project."""
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            return None
        project = dict(row)

        # Count tasks by status
        task_counts = {}
        for r in conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM tasks WHERE project_id = ?
               GROUP BY status""",
            (project_id,),
        ):
            task_counts[r["status"]] = r["cnt"]
        project["task_counts"] = task_counts
        project["total_tasks"] = sum(task_counts.values())

        # Count epics
        epic_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM epics WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        project["total_epics"] = epic_row["cnt"] if epic_row else 0

        return project

    return execute_with_retry(_query)


def create_project(name: str, description: str = "") -> int:
    """Create a new project in the DB and return its id."""

    def _insert(conn: sqlite3.Connection) -> int:
        """Persist the original owner description alongside editable metadata, retaining the historical-schema fallback."""
        try:
            cursor = conn.execute(
                """INSERT INTO projects (name, description, original_description, status, created_at)
                   VALUES (?, ?, ?, 'new', CURRENT_TIMESTAMP)""",
                (name, description, description),
            )
        except sqlite3.OperationalError:
            # Fallback if original_description column not yet migrated
            cursor = conn.execute(
                """INSERT INTO projects (name, description, status, created_at)
                   VALUES (?, ?, 'new', CURRENT_TIMESTAMP)""",
                (name, description),
            )
        conn.commit()
        return cursor.lastrowid

    return execute_with_retry(_insert)


def update_project_status(project_id: int, status: str) -> None:
    """Update operational labels; completion requires an exact native report and a distinct owner decision."""
    if status == "completed":
        from backend.runtime.lifecycle import NativeOwnerRequired

        raise NativeOwnerRequired("Project completion requires explicit owner acceptance of the current whole-project report")

    def _update(conn: sqlite3.Connection) -> None:
        """Apply the permitted operational label without creating work or accepting a result."""
        if status == "completed":
            conn.execute(
                "UPDATE projects SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, project_id),
            )
        else:
            conn.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                (status, project_id),
            )
        conn.commit()

    execute_with_retry(_update)
