"""Database helpers for PABADA flows — project/task CRUD and queries."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


# ── Project helpers ───────────────────────────────────────────────────────────


def load_project_state(project_id: int) -> dict[str, Any] | None:
    """Load full project state from DB, including counts."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
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


def get_project_name(project_id: int) -> str:
    """Return the project name for the given project_id, or '' if not found."""

    def _query(conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT name FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return row["name"] if row else ""

    return execute_with_retry(_query)


def update_project_status(project_id: int, status: str) -> None:
    """Update the status of a project."""

    def _update(conn: sqlite3.Connection) -> None:
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


# ── Task helpers ──────────────────────────────────────────────────────────────


def get_pending_tasks(project_id: int) -> list[dict[str, Any]]:
    """Get tasks with status in ('backlog', 'pending') ordered by priority.

    Only returns tasks whose dependencies are all 'done'.
    """

    def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT t.*
               FROM tasks t
               WHERE t.project_id = ?
                 AND t.status IN ('backlog', 'pending')
                 AND NOT EXISTS (
                     SELECT 1 FROM task_dependencies td
                     JOIN tasks dep ON dep.id = td.depends_on_task_id
                     WHERE td.task_id = t.id
                       AND td.dependency_type = 'blocks'
                       AND dep.status != 'done'
                 )
               ORDER BY t.priority ASC, t.id ASC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    return execute_with_retry(_query)


def get_task_by_id(task_id: int) -> dict[str, Any] | None:
    """Load a single task from DB."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    return execute_with_retry(_query)


def check_task_dependencies(task_id: int) -> bool:
    """Return True if all blocking dependencies of task_id are done."""

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as cnt
               FROM task_dependencies td
               JOIN tasks dep ON dep.id = td.depends_on_task_id
               WHERE td.task_id = ?
                 AND td.dependency_type = 'blocks'
                 AND dep.status != 'done'""",
            (task_id,),
        ).fetchone()
        return row["cnt"] == 0

    return execute_with_retry(_query)


def update_task_status(task_id: int, status: str) -> None:
    """Update a task's status with state machine validation.

    When a task transitions to ``done``, dependents that are fully unblocked
    are automatically promoted from ``backlog`` to ``pending``.
    """
    from backend.state.machine import TaskStateMachine

    def _update(conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Task {task_id} not found")
        current = row["status"] if isinstance(row, sqlite3.Row) else row[0]
        if current == status:
            return  # no-op
        TaskStateMachine.validate_transition(current, status)

        if status in ("done", "failed"):
            conn.execute(
                "UPDATE tasks SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, task_id),
            )
        else:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
        conn.commit()

    execute_with_retry(_update)

    # After committing to done, promote any dependents that are now unblocked
    if status == "done":
        promote_unblocked_dependents(task_id)

    # Create persistent agent_events for the status change
    _create_events_for_status_change(task_id, status)


def update_task_status_safe(task_id: int, status: str) -> None:
    """Update a task's status, ignoring errors if task doesn't exist."""
    try:
        update_task_status(task_id, status)
    except Exception:
        logger.warning("Could not update task %d to status '%s'", task_id, status)


def get_task_branch(task_id: int) -> str | None:
    """Get the branch_name for a task."""

    def _query(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT branch_name FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row["branch_name"] if row and row["branch_name"] else None

    return execute_with_retry(_query)


def set_task_branch(task_id: int, branch_name: str) -> None:
    """Set the branch_name on a task."""

    def _update(conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE tasks SET branch_name = ? WHERE id = ?",
            (branch_name, task_id),
        )
        conn.commit()

    execute_with_retry(_update)


def increment_task_retry(task_id: int) -> int:
    """Increment retry_count on a task and return the new count."""

    def _update(conn: sqlite3.Connection) -> int:
        conn.execute(
            "UPDATE tasks SET retry_count = retry_count + 1 WHERE id = ?",
            (task_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT retry_count FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row["retry_count"]

    return execute_with_retry(_update)


def get_task_count(project_id: int) -> int:
    """Return total number of tasks for a project (any status)."""

    def _query(conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    return execute_with_retry(_query)


# ── Objective verification ────────────────────────────────────────────────────


def get_repo_path_for_task(task_id: int) -> str | None:
    """Get the active repository local_path for the project owning a task."""

    def _query(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            """SELECT r.local_path FROM repositories r
               JOIN tasks t ON t.project_id = r.project_id
               WHERE t.id = ? AND r.status = 'active'
               LIMIT 1""",
            (task_id,),
        ).fetchone()
        return row["local_path"] if row and row["local_path"] else None

    return execute_with_retry(_query)


def get_active_epic_count(project_id: int) -> dict[str, int]:
    """Return counts of open/completed epics for a project."""

    def _query(conn: sqlite3.Connection) -> dict[str, int]:
        row = conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) as open,
                 SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
               FROM epics WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        return {
            "total": row["total"] or 0,
            "open": row["open"] or 0,
            "completed": row["completed"] or 0,
        }

    return execute_with_retry(_query)


def all_objectives_met(project_id: int) -> bool:
    """Check if all epics in the project are completed."""

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
               FROM epics WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        if row is None or row["total"] == 0:
            return False
        return row["completed"] == row["total"]

    return execute_with_retry(_query)


def get_project_progress_summary(project_id: int) -> str:
    """Build a text summary of the project's current progress for the Team Lead.

    Returns a structured string with completed tasks, open epics/milestones,
    and task breakdowns that the TL can use to decide next steps.
    """

    def _query(conn: sqlite3.Connection) -> str:
        # Project info
        project = conn.execute(
            "SELECT name, description FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if project is None:
            return "Project not found."

        lines: list[str] = [
            f"## Project: {project['name']}",
            f"**Description**: {project['description'] or 'N/A'}",
            "",
        ]

        # Epics status
        epics = conn.execute(
            "SELECT id, title, status FROM epics WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        lines.append("## Epics")
        for epic in epics:
            lines.append(f"- [{epic['status']}] {epic['title']} (epic_id={epic['id']})")
        if not epics:
            lines.append("- No epics found.")
        lines.append("")

        # Task summary by status
        task_counts = conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM tasks WHERE project_id = ?
               GROUP BY status ORDER BY status""",
            (project_id,),
        ).fetchall()
        lines.append("## Task Summary by Status")
        for row in task_counts:
            lines.append(f"- {row['status']}: {row['cnt']}")
        lines.append("")

        # In-progress tasks (what agents are working on RIGHT NOW)
        active_tasks = conn.execute(
            """SELECT id, title, type, assigned_to
               FROM tasks WHERE project_id = ? AND status = 'in_progress'
               ORDER BY id""",
            (project_id,),
        ).fetchall()
        if active_tasks:
            lines.append("## In-Progress Tasks (currently being worked on)")
            for t in active_tasks:
                assignee = t["assigned_to"] or "unassigned"
                lines.append(f"- [#{t['id']}] ({t['type']}) {t['title']} — assigned to: {assignee}")
            lines.append("")

        # Pending/backlog tasks (next up in the queue)
        pending_tasks = conn.execute(
            """SELECT id, title, type, priority, status
               FROM tasks WHERE project_id = ? AND status IN ('pending', 'backlog')
               ORDER BY priority ASC, id ASC LIMIT 15""",
            (project_id,),
        ).fetchall()
        if pending_tasks:
            lines.append("## Pending/Backlog Tasks (ready or waiting)")
            for t in pending_tasks:
                lines.append(f"- [#{t['id']}] ({t['status']}) ({t['type']}) P{t['priority'] or '?'}: {t['title']}")
            lines.append("")

        # Review-ready tasks
        review_tasks = conn.execute(
            """SELECT id, title, type, assigned_to
               FROM tasks WHERE project_id = ? AND status = 'review_ready'
               ORDER BY id""",
            (project_id,),
        ).fetchall()
        if review_tasks:
            lines.append("## Tasks Awaiting Review")
            for t in review_tasks:
                lines.append(f"- [#{t['id']}] ({t['type']}) {t['title']}")
            lines.append("")

        # Recently completed tasks (last 10, not all 20)
        done_tasks = conn.execute(
            """SELECT id, title, type, completed_at
               FROM tasks WHERE project_id = ? AND status = 'done'
               ORDER BY completed_at DESC LIMIT 10""",
            (project_id,),
        ).fetchall()
        lines.append("## Recently Completed Tasks")
        for t in done_tasks:
            lines.append(f"- [#{t['id']}] ({t['type']}) {t['title']}")
        if not done_tasks:
            lines.append("- No completed tasks yet.")
        lines.append("")

        # Research findings summary (completed research tasks)
        research_tasks = conn.execute(
            """SELECT id, title, description
               FROM tasks WHERE project_id = ? AND type = 'research' AND status = 'done'
               ORDER BY completed_at DESC LIMIT 5""",
            (project_id,),
        ).fetchall()
        if research_tasks:
            lines.append("## Recent Research Completed")
            for t in research_tasks:
                desc_preview = (t["description"] or "")[:200]
                lines.append(f"- [#{t['id']}] {t['title']}: {desc_preview}")
            lines.append("")

        # Failed/cancelled/blocked tasks
        problem_tasks = conn.execute(
            """SELECT id, title, status, type
               FROM tasks WHERE project_id = ? AND status IN ('failed', 'cancelled', 'blocked')
               ORDER BY id""",
            (project_id,),
        ).fetchall()
        if problem_tasks:
            lines.append("## Failed/Cancelled/Blocked Tasks")
            for t in problem_tasks:
                lines.append(f"- [#{t['id']}] ({t['status']}) ({t['type']}) {t['title']}")
            lines.append("")

        return "\n".join(lines)

    return execute_with_retry(_query)


# ── Dependency promotion ─────────────────────────────────────────────────────


def _create_events_for_status_change(task_id: int, new_status: str) -> None:
    """Create persistent agent_events when a task status changes.

    Called after update_task_status commits. Creates events so
    the AgentLoop can pick up the work.
    """
    try:
        from backend.autonomy.events import create_task_event

        # Get task details for routing
        task = get_task_by_id(task_id)
        if not task:
            return
        project_id = task["project_id"]
        task_type = task.get("type", "code")
        assigned_to = task.get("assigned_to")

        if new_status == "review_ready":
            # Skip if there's already an unprocessed review_ready event for
            # this task — prevents duplicate reviews when a flow (e.g.
            # ResearchFlow) already manages its own review cycle.
            from backend.autonomy.events import has_pending_review_event

            if has_pending_review_event(project_id, task_id):
                logger.debug(
                    "Skipping review_ready event for task %d — pending event exists",
                    task_id,
                )
            elif task_type == "research":
                create_task_event(
                    project_id, task_id, "review_ready",
                    target_role="research_reviewer",
                    source="task_trigger",
                )
            else:
                create_task_event(
                    project_id, task_id, "review_ready",
                    target_role="code_reviewer",
                    source="task_trigger",
                )
        elif new_status == "blocked":
            # Notify the project lead to review the blocker
            create_task_event(
                project_id, task_id, "task_blocked",
                target_role="project_lead",
                source="task_trigger",
            )
        elif new_status == "rejected":
            # Notify the assigned developer (or all developers)
            create_task_event(
                project_id, task_id, "task_rejected",
                target_agent_id=assigned_to,
                target_role="developer" if not assigned_to else None,
                source="task_trigger",
            )
        elif new_status == "pending":
            # Task became available — notify appropriate role
            if task_type == "research":
                create_task_event(
                    project_id, task_id, "task_available",
                    target_role="researcher",
                    source="task_trigger",
                    extra_payload={"task_type": task_type, "task_priority": task.get("priority", 2)},
                )
            elif task_type == "review":
                create_task_event(
                    project_id, task_id, "task_available",
                    target_role="code_reviewer",
                    source="task_trigger",
                    extra_payload={"task_type": task_type, "task_priority": task.get("priority", 2)},
                )
            else:
                create_task_event(
                    project_id, task_id, "task_available",
                    target_role="developer",
                    source="task_trigger",
                    extra_payload={"task_type": task_type, "task_priority": task.get("priority", 2)},
                )
    except Exception:
        logger.debug("Could not create agent events for task %d status change", task_id, exc_info=True)


def atomic_claim_task(task_id: int, agent_id: str) -> bool:
    """Atomically claim a task. Returns True if successful.

    The conditional UPDATE is atomic in SQLite, preventing two agents from
    claiming the same task.
    """

    def _claim(conn: sqlite3.Connection) -> bool:
        cursor = conn.execute(
            """UPDATE tasks SET assigned_to = ?, status = 'in_progress'
               WHERE id = ? AND status IN ('backlog', 'pending')
               AND (assigned_to IS NULL OR assigned_to = '' OR assigned_to = ?)""",
            (agent_id, task_id, agent_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    return execute_with_retry(_claim)


def promote_unblocked_dependents(task_id: int) -> list[int]:
    """Promote dependents of *task_id* from ``backlog`` to ``pending``.

    For each task that depends on *task_id* and is still in ``backlog``,
    check whether **all** of its blocking dependencies are ``done``.
    If so, move it to ``pending``.

    Returns the list of promoted task IDs.  Idempotent — calling twice
    with the same *task_id* is safe and returns an empty list on the
    second call.
    """

    def _promote(conn: sqlite3.Connection) -> list[int]:
        # Find backlog tasks that depend on the completed task
        candidates = conn.execute(
            """SELECT DISTINCT td.task_id
               FROM task_dependencies td
               JOIN tasks t ON t.id = td.task_id
               WHERE td.depends_on_task_id = ?
                 AND td.dependency_type = 'blocks'
                 AND t.status = 'backlog'""",
            (task_id,),
        ).fetchall()

        promoted: list[int] = []
        for row in candidates:
            candidate_id = row["task_id"] if isinstance(row, sqlite3.Row) else row[0]

            # Check that ALL blocking deps of this candidate are done
            unmet = conn.execute(
                """SELECT COUNT(*) as cnt
                   FROM task_dependencies td
                   JOIN tasks dep ON dep.id = td.depends_on_task_id
                   WHERE td.task_id = ?
                     AND td.dependency_type = 'blocks'
                     AND dep.status != 'done'""",
                (candidate_id,),
            ).fetchone()

            if (unmet["cnt"] if isinstance(unmet, sqlite3.Row) else unmet[0]) == 0:
                conn.execute(
                    "UPDATE tasks SET status = 'pending' WHERE id = ? AND status = 'backlog'",
                    (candidate_id,),
                )
                promoted.append(candidate_id)

        if promoted:
            conn.commit()
            logger.info(
                "Promoted %d tasks from backlog to pending after task %d completed: %s",
                len(promoted), task_id, promoted,
            )
        return promoted

    return execute_with_retry(_promote)
