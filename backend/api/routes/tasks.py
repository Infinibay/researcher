"""Task CRUD endpoints with comments and dependencies."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Query

from backend.api.exceptions import TaskNotFound
from backend.api.models.task import (
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskDependencyCreate,
    TaskDependencyResponse,
    TaskResponse,
    TaskUpdate,
)
from backend.flows.helpers import log_flow_event
from backend.state.dependency_validator import DependencyValidator
from backend.state.machine import TaskStateMachine
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _row_to_response(row: dict) -> TaskResponse:
    return TaskResponse(**row)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: int = Query(...),
    status: str | None = Query(default=None),
    epic_id: int | None = Query(default=None),
    milestone_id: int | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
):
    """List tasks with optional filters."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        where = ["t.project_id = ?"]
        params: list = [project_id]

        if status is not None:
            where.append("t.status = ?")
            params.append(status)
        if epic_id is not None:
            where.append("t.epic_id = ?")
            params.append(epic_id)
        if milestone_id is not None:
            where.append("t.milestone_id = ?")
            params.append(milestone_id)
        if assigned_to is not None:
            where.append("t.assigned_to = ?")
            params.append(assigned_to)

        where_clause = " AND ".join(where)
        rows = conn.execute(
            f"""SELECT t.* FROM tasks t
                WHERE {where_clause}
                ORDER BY t.priority ASC, t.created_at DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    tasks = execute_with_retry(_query)
    return [_row_to_response(t) for t in tasks]


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(body: TaskCreate):
    """Create a new task with optional dependencies."""

    def _create(conn: sqlite3.Connection) -> dict:
        project_id = body.project_id

        # If no project_id, try to get it from epic or milestone
        if project_id is None and body.epic_id is not None:
            epic = conn.execute(
                "SELECT project_id FROM epics WHERE id = ?", (body.epic_id,)
            ).fetchone()
            if epic:
                project_id = epic["project_id"]

        if project_id is None and body.milestone_id is not None:
            ms = conn.execute(
                "SELECT project_id FROM milestones WHERE id = ?", (body.milestone_id,)
            ).fetchone()
            if ms:
                project_id = ms["project_id"]

        if project_id is None:
            raise ValueError("project_id is required (directly or via epic_id/milestone_id)")

        # Validate epic/milestone
        if body.epic_id is not None:
            row = conn.execute("SELECT id FROM epics WHERE id = ?", (body.epic_id,)).fetchone()
            if not row:
                raise ValueError(f"Epic {body.epic_id} not found")

        if body.milestone_id is not None:
            row = conn.execute(
                "SELECT id FROM milestones WHERE id = ?", (body.milestone_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Milestone {body.milestone_id} not found")

        # Validate dependencies
        for dep_id in body.depends_on:
            row = conn.execute("SELECT id FROM tasks WHERE id = ?", (dep_id,)).fetchone()
            if not row:
                raise ValueError(f"Dependency task {dep_id} not found")

        cursor = conn.execute(
            """INSERT INTO tasks
               (project_id, epic_id, milestone_id, type, status, title,
                description, priority, estimated_complexity, created_by)
               VALUES (?, ?, ?, ?, 'backlog', ?, ?, ?, ?, 'api')""",
            (project_id, body.epic_id, body.milestone_id, body.type,
             body.title, body.description, body.priority, body.complexity),
        )
        task_id = cursor.lastrowid

        # Create dependencies
        for dep_id in body.depends_on:
            conn.execute(
                """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
                   VALUES (?, ?, 'blocks')""",
                (task_id, dep_id),
            )

        conn.commit()

        # Log event
        try:
            conn.execute(
                """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type, entity_id, event_data_json, created_at)
                   VALUES (?, 'task_created', 'api', 'task', ?, ?, CURRENT_TIMESTAMP)""",
                (project_id, task_id, json.dumps({"title": body.title})),
            )
            conn.commit()
        except Exception:
            pass

        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row)

    task = execute_with_retry(_create)
    return _row_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    """Get task details."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    task = execute_with_retry(_query)
    if not task:
        raise TaskNotFound(task_id)
    return _row_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, body: TaskUpdate):
    """Update a task. Emits status_changed events when status changes."""

    # ── Pre-DB validation (Comments 1 & 3) ────────────────────────────
    # Fetch current status to validate before entering the DB callback.
    def _fetch_current(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT id, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    current = execute_with_retry(_fetch_current)
    if not current:
        raise TaskNotFound(task_id)

    old_status = current["status"]

    if body.status is not None and body.status != old_status:
        # Validate state transition — return 400 on invalid transitions
        try:
            TaskStateMachine.validate_transition(old_status, body.status)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Block transition to in_progress if dependencies are not met
        if body.status == "in_progress" and not DependencyValidator.can_start(task_id):
            unmet = DependencyValidator.get_unmet_dependencies(task_id)
            blockers = ", ".join(
                f"#{d['id']} {d['title']} ({d['status']})" for d in unmet
            )
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} cannot start — blocked by: {blockers}",
            )

    # ── Apply update ──────────────────────────────────────────────────
    def _update(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None

        updates = []
        params = []

        if body.title is not None:
            updates.append("title = ?")
            params.append(body.title)
        if body.description is not None:
            updates.append("description = ?")
            params.append(body.description)
        if body.status is not None:
            updates.append("status = ?")
            params.append(body.status)
            if body.status in ("done", "cancelled"):
                updates.append("completed_at = CURRENT_TIMESTAMP")
        if body.assigned_to is not None:
            updates.append("assigned_to = ?")
            params.append(body.assigned_to)
        if body.reviewer is not None:
            updates.append("reviewer = ?")
            params.append(body.reviewer)
        if body.branch_name is not None:
            updates.append("branch_name = ?")
            params.append(body.branch_name)
        if body.priority is not None:
            updates.append("priority = ?")
            params.append(body.priority)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        # Emit status change event
        if body.status is not None and body.status != old_status:
            project_id = row["project_id"]
            try:
                conn.execute(
                    """INSERT INTO events_log
                       (project_id, event_type, event_source, entity_type,
                        entity_id, event_data_json, created_at)
                       VALUES (?, 'task_status_changed', 'api', 'task', ?, ?, CURRENT_TIMESTAMP)""",
                    (project_id, task_id,
                     json.dumps({"old_status": old_status, "new_status": body.status})),
                )
                conn.commit()
            except Exception:
                pass

        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row)

    task = execute_with_retry(_update)
    if not task:
        raise TaskNotFound(task_id)
    return _row_to_response(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int):
    """Delete a task (only if backlog, pending, or cancelled)."""

    def _delete(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT id, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            return False

        if row["status"] not in ("backlog", "pending", "cancelled"):
            raise ValueError(
                f"Cannot delete task in status '{row['status']}'. "
                f"Only backlog, pending, or cancelled tasks can be deleted."
            )

        conn.execute("DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?",
                      (task_id, task_id))
        conn.execute("DELETE FROM task_comments WHERE task_id = ?", (task_id,))
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return True

    found = execute_with_retry(_delete)
    if not found:
        raise TaskNotFound(task_id)


# ── Comments ──────────────────────────────────────────────────────────────────


@router.get("/{task_id}/comments", response_model=list[TaskCommentResponse])
async def list_task_comments(task_id: int):
    """List comments for a task."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        # Verify task exists
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")

        rows = conn.execute(
            """SELECT * FROM task_comments
               WHERE task_id = ?
               ORDER BY created_at ASC""",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    comments = execute_with_retry(_query)
    return [TaskCommentResponse(**c) for c in comments]


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
async def add_task_comment(task_id: int, body: TaskCommentCreate):
    """Add a comment to a task."""

    def _create(conn: sqlite3.Connection) -> dict:
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")

        cursor = conn.execute(
            """INSERT INTO task_comments (task_id, author, comment_type, content)
               VALUES (?, ?, ?, ?)""",
            (task_id, body.author, body.comment_type, body.content),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_comments WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    comment = execute_with_retry(_create)
    return TaskCommentResponse(**comment)


# ── Dependencies ──────────────────────────────────────────────────────────────


@router.get("/{task_id}/dependencies", response_model=list[TaskDependencyResponse])
async def list_task_dependencies(task_id: int):
    """List dependencies for a task."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT task_id, depends_on_task_id, dependency_type
               FROM task_dependencies
               WHERE task_id = ?""",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    deps = execute_with_retry(_query)
    return [TaskDependencyResponse(**d) for d in deps]


@router.post("/{task_id}/dependencies", response_model=list[TaskDependencyResponse], status_code=201)
async def set_task_dependencies(task_id: int, body: TaskDependencyCreate):
    """Set dependencies for a task."""

    def _set(conn: sqlite3.Connection) -> list[dict]:
        # Validate task exists
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")

        # Validate dependencies
        for dep_id in body.depends_on:
            if dep_id == task_id:
                raise ValueError("A task cannot depend on itself")
            row = conn.execute("SELECT id FROM tasks WHERE id = ?", (dep_id,)).fetchone()
            if not row:
                raise ValueError(f"Dependency task {dep_id} not found")

        # Remove existing of same type and re-insert
        conn.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? AND dependency_type = ?",
            (task_id, body.dependency_type),
        )

        results = []
        for dep_id in body.depends_on:
            conn.execute(
                """INSERT OR IGNORE INTO task_dependencies
                   (task_id, depends_on_task_id, dependency_type)
                   VALUES (?, ?, ?)""",
                (task_id, dep_id, body.dependency_type),
            )
            results.append({
                "task_id": task_id,
                "depends_on_task_id": dep_id,
                "dependency_type": body.dependency_type,
            })

        conn.commit()
        return results

    deps = execute_with_retry(_set)
    return [TaskDependencyResponse(**d) for d in deps]
