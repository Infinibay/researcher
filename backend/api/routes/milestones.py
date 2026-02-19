"""Milestone CRUD endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Query

from backend.api.exceptions import EpicNotFound, MilestoneNotFound
from backend.api.models.milestone import (
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
)
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


def _row_to_response(row: dict) -> MilestoneResponse:
    return MilestoneResponse(**row)


@router.get("", response_model=list[MilestoneResponse])
async def list_milestones(
    project_id: int = Query(...),
    epic_id: int | None = Query(default=None),
):
    """List milestones with task counts, optionally filtered by epic."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        where = "m.project_id = ?"
        params: list = [project_id]
        if epic_id is not None:
            where += " AND m.epic_id = ?"
            params.append(epic_id)

        rows = conn.execute(
            f"""SELECT m.*,
                       COALESCE(tc.task_count, 0) as task_count,
                       COALESCE(tc.tasks_done, 0) as tasks_done
                FROM milestones m
                LEFT JOIN (
                    SELECT milestone_id,
                           COUNT(*) as task_count,
                           SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as tasks_done
                    FROM tasks
                    GROUP BY milestone_id
                ) tc ON tc.milestone_id = m.id
                WHERE {where}
                ORDER BY m.due_date ASC NULLS LAST, m.id ASC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    milestones = execute_with_retry(_query)
    return [_row_to_response(m) for m in milestones]


@router.post("", response_model=MilestoneResponse, status_code=201)
async def create_milestone(body: MilestoneCreate):
    """Create a new milestone under an epic."""

    def _create(conn: sqlite3.Connection) -> dict:
        # Validate epic exists and get project_id
        epic = conn.execute(
            "SELECT id, project_id FROM epics WHERE id = ?", (body.epic_id,)
        ).fetchone()
        if not epic:
            raise ValueError(f"Epic {body.epic_id} not found")

        cursor = conn.execute(
            """INSERT INTO milestones
               (project_id, epic_id, title, description, status, due_date)
               VALUES (?, ?, ?, ?, 'open', ?)""",
            (epic["project_id"], body.epic_id, body.title, body.description, body.due_date),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM milestones WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    milestone = execute_with_retry(_create)
    return _row_to_response({**milestone, "task_count": 0, "tasks_done": 0})


@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone(milestone_id: int):
    """Get milestone details with task counts."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            """SELECT m.*,
                      COALESCE(tc.task_count, 0) as task_count,
                      COALESCE(tc.tasks_done, 0) as tasks_done
               FROM milestones m
               LEFT JOIN (
                   SELECT milestone_id,
                          COUNT(*) as task_count,
                          SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as tasks_done
                   FROM tasks
                   GROUP BY milestone_id
               ) tc ON tc.milestone_id = m.id
               WHERE m.id = ?""",
            (milestone_id,),
        ).fetchone()
        return dict(row) if row else None

    milestone = execute_with_retry(_query)
    if not milestone:
        raise MilestoneNotFound(milestone_id)
    return _row_to_response(milestone)


@router.put("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(milestone_id: int, body: MilestoneUpdate):
    """Update a milestone."""

    def _update(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
        ).fetchone()
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
        if body.due_date is not None:
            updates.append("due_date = ?")
            params.append(body.due_date)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(milestone_id)
            conn.execute(
                f"UPDATE milestones SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        row = conn.execute(
            "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
        ).fetchone()
        return dict(row)

    milestone = execute_with_retry(_update)
    if not milestone:
        raise MilestoneNotFound(milestone_id)
    return _row_to_response({**milestone, "task_count": 0, "tasks_done": 0})


@router.delete("/{milestone_id}", status_code=204)
async def delete_milestone(milestone_id: int):
    """Delete a milestone."""

    def _delete(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT id FROM milestones WHERE id = ?", (milestone_id,)
        ).fetchone()
        if not row:
            return False

        in_progress = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE milestone_id = ? AND status = 'in_progress'""",
            (milestone_id,),
        ).fetchone()
        if in_progress and in_progress["cnt"] > 0:
            raise ValueError(
                f"Milestone {milestone_id} has {in_progress['cnt']} tasks in progress"
            )

        conn.execute("DELETE FROM milestones WHERE id = ?", (milestone_id,))
        conn.commit()
        return True

    found = execute_with_retry(_delete)
    if not found:
        raise MilestoneNotFound(milestone_id)
