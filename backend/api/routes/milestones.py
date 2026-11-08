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
from backend.tools.base.db import execute_with_retry, get_db_path

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


def _records():
    """Bind owner metadata transactions to the same existing database as the current request."""
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.runtime.sqlite_runs import SQLiteRunStore

    return OwnerPlanningRecords(SQLiteRunStore(get_db_path()))


def _row_to_response(row: dict) -> MilestoneResponse:
    """Validate a stored milestone row against its public response shape."""
    return MilestoneResponse(**row)


@router.get("", response_model=list[MilestoneResponse])
def list_milestones(
    project_id: int = Query(...),
    epic_id: int | None = Query(default=None),
):
    """List milestones with task counts, optionally filtered by epic."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        """List scoped milestones and task counts, optionally filtering a group and ordering missing due dates last."""
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
def create_milestone(body: MilestoneCreate):
    """Create or recover one milestone in its original project and group."""
    return _row_to_response(_records().create_milestone(**body.model_dump()))


@router.get("/{milestone_id}", response_model=MilestoneResponse)
def get_milestone(milestone_id: int):
    """Get milestone details with task counts."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        """Read one milestone identity with stored task counts, returning no row when absent."""
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
def update_milestone(milestone_id: int, body: MilestoneUpdate):
    """Update a milestone."""

    def _update(conn: sqlite3.Connection) -> dict | None:
        """Write declared milestone metadata while retaining its immutable original creation response."""
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
def delete_milestone(milestone_id: int):
    """Retire a manual milestone only when no native history depends on its identity."""
    if not _records().delete_milestone(milestone_id):
        raise MilestoneNotFound(milestone_id)
