"""Epic CRUD endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Query

from backend.api.exceptions import EpicNotFound, ProjectNotFound
from backend.api.models.epic import EpicCreate, EpicResponse, EpicUpdate
from backend.flows.helpers import load_project_state
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/epics", tags=["epics"])


def _row_to_response(row: dict) -> EpicResponse:
    return EpicResponse(**row)


@router.get("", response_model=list[EpicResponse])
async def list_epics(project_id: int = Query(...)):
    """List epics for a project with task and milestone counts."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT e.*,
                      COALESCE(tc.task_count, 0) as task_count,
                      COALESCE(tc.tasks_done, 0) as tasks_done,
                      COALESCE(mc.milestone_count, 0) as milestone_count
               FROM epics e
               LEFT JOIN (
                   SELECT epic_id,
                          COUNT(*) as task_count,
                          SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as tasks_done
                   FROM tasks
                   GROUP BY epic_id
               ) tc ON tc.epic_id = e.id
               LEFT JOIN (
                   SELECT epic_id, COUNT(*) as milestone_count
                   FROM milestones
                   GROUP BY epic_id
               ) mc ON mc.epic_id = e.id
               WHERE e.project_id = ?
               ORDER BY e.priority ASC, e.id ASC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    epics = execute_with_retry(_query)
    return [_row_to_response(e) for e in epics]


@router.post("", response_model=EpicResponse, status_code=201)
async def create_epic(body: EpicCreate):
    """Create a new epic."""
    # Validate project exists
    state = load_project_state(body.project_id)
    if not state:
        raise ProjectNotFound(body.project_id)

    def _create(conn: sqlite3.Connection) -> dict:
        cursor = conn.execute(
            """INSERT INTO epics
               (project_id, title, description, status, priority, created_by)
               VALUES (?, ?, ?, 'open', ?, 'api')""",
            (body.project_id, body.title, body.description, body.priority),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM epics WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    epic = execute_with_retry(_create)
    return _row_to_response({**epic, "task_count": 0, "tasks_done": 0, "milestone_count": 0})


@router.get("/{epic_id}", response_model=EpicResponse)
async def get_epic(epic_id: int):
    """Get epic details with task and milestone counts."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            """SELECT e.*,
                      COALESCE(tc.task_count, 0) as task_count,
                      COALESCE(tc.tasks_done, 0) as tasks_done,
                      COALESCE(mc.milestone_count, 0) as milestone_count
               FROM epics e
               LEFT JOIN (
                   SELECT epic_id,
                          COUNT(*) as task_count,
                          SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as tasks_done
                   FROM tasks
                   GROUP BY epic_id
               ) tc ON tc.epic_id = e.id
               LEFT JOIN (
                   SELECT epic_id, COUNT(*) as milestone_count
                   FROM milestones
                   GROUP BY epic_id
               ) mc ON mc.epic_id = e.id
               WHERE e.id = ?""",
            (epic_id,),
        ).fetchone()
        return dict(row) if row else None

    epic = execute_with_retry(_query)
    if not epic:
        raise EpicNotFound(epic_id)
    return _row_to_response(epic)


@router.put("/{epic_id}", response_model=EpicResponse)
async def update_epic(epic_id: int, body: EpicUpdate):
    """Update an epic."""

    def _update(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute("SELECT * FROM epics WHERE id = ?", (epic_id,)).fetchone()
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
        if body.priority is not None:
            updates.append("priority = ?")
            params.append(body.priority)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(epic_id)
            conn.execute(
                f"UPDATE epics SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        row = conn.execute("SELECT * FROM epics WHERE id = ?", (epic_id,)).fetchone()
        return dict(row)

    epic = execute_with_retry(_update)
    if not epic:
        raise EpicNotFound(epic_id)
    return _row_to_response({**epic, "task_count": 0, "tasks_done": 0, "milestone_count": 0})


@router.delete("/{epic_id}", status_code=204)
async def delete_epic(epic_id: int):
    """Delete an epic and its milestones."""

    def _delete(conn: sqlite3.Connection) -> bool:
        row = conn.execute("SELECT id FROM epics WHERE id = ?", (epic_id,)).fetchone()
        if not row:
            return False

        # Check for in-progress tasks
        in_progress = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE epic_id = ? AND status = 'in_progress'",
            (epic_id,),
        ).fetchone()
        if in_progress and in_progress["cnt"] > 0:
            raise ValueError(f"Epic {epic_id} has {in_progress['cnt']} tasks in progress")

        conn.execute("DELETE FROM milestones WHERE epic_id = ?", (epic_id,))
        conn.execute("DELETE FROM epics WHERE id = ?", (epic_id,))
        conn.commit()
        return True

    found = execute_with_retry(_delete)
    if not found:
        raise EpicNotFound(epic_id)
