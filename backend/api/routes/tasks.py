"""Task CRUD endpoints with comments and dependencies."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request

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
from backend.state.machine import TaskStateMachine
from backend.tools.base.db import execute_with_retry
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _row_to_response(row: dict) -> TaskResponse:
    return TaskResponse(**row)


@router.get("", response_model=list[TaskResponse])
def list_tasks(
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
def create_task(body: TaskCreate):
    """Create or recover exact owner task metadata and dependencies without launching native work."""
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import get_db_path

    return _row_to_response(OwnerPlanningRecords(SQLiteRunStore(get_db_path())).create_task(**body.model_dump()))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, project_id: int | None = Query(default=None, gt=0)):
    """Read a task, rejecting mismatched project-scoped report/deep links.

    Omitting project_id preserves compatibility with existing task consumers.
    """

    def _query(conn: sqlite3.Connection) -> dict | None:
        """Return the task only when its optional project constraint matches."""
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND (? IS NULL OR project_id = ?)",
            (task_id, project_id, project_id),
        ).fetchone()
        return dict(row) if row else None

    task = execute_with_retry(_query)
    if not task:
        raise TaskNotFound(task_id)
    return _row_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, body: TaskUpdate, request: Request):
    """Edit versioned task inputs; native completion requires a separate owner acceptance."""

    def _update(conn: sqlite3.Connection) -> tuple[dict, bool] | None:
        """Version edited inputs atomically and refuse generic lifecycle overrides for native-owned tasks."""
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None

        def context_version():
            """Read the version under this edit's transaction before notifying the local runtime."""
            context = conn.execute(
                "SELECT version FROM task_contexts WHERE task_id=?", (task_id,)
            ).fetchone()
            return context[0] if context is not None else 1

        from backend.runtime.task_profiles import OWNER_ONLY_LEGACY_TASK_TYPES

        if body.status is not None and body.status != row["status"] and (
            row["type"] in OWNER_ONLY_LEGACY_TASK_TYPES
            or conn.execute("SELECT 1 FROM runtime_runs WHERE task_id=? LIMIT 1", (task_id,)).fetchone()
        ):
            raise HTTPException(409, "Use native task acceptance, stop or context-correction controls to change this task's lifecycle")
        if body.status is not None and body.status != row["status"]:
            TaskStateMachine.validate_transition(row["status"], body.status)
        previous_version = context_version()

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
            if body.status in ("done", "cancelled", "failed"):
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
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row), context_version() != previous_version

    task = await run_in_threadpool(execute_with_retry, _update)
    if not task:
        raise TaskNotFound(task_id)
    task, inputs_changed = task
    runtime = request.app.state.runtime_service
    if inputs_changed and runtime is not None:
        runtime.task_inputs_changed(task["project_id"], task_id)
    return _row_to_response(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int):
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
def list_task_comments(task_id: int):
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
def add_task_comment(task_id: int, body: TaskCommentCreate):
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
def list_task_dependencies(task_id: int):
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
def set_task_dependencies(task_id: int, body: TaskDependencyCreate):
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
