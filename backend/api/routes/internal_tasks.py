"""Internal API endpoints for task approval and rejection.

These endpoints are called by the ``infinibay`` CLI and the INFINIBAY MCP server
running inside sandbox containers, providing task review operations.
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter
from pydantic import BaseModel

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal-tasks"])


# ── Request/Response models ──────────────────────────────────────────────

class TaskApproveRequest(BaseModel):
    agent_id: str
    comment: str | None = None


class TaskRejectRequest(BaseModel):
    agent_id: str
    reason: str


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: int, req: TaskApproveRequest):
    """Approve a task in review_ready status, moving it to done."""

    def _approve(conn: sqlite3.Connection) -> dict:
        row = conn.execute(
            "SELECT id, status, title, assigned_to FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")
        if row["status"] != "review_ready":
            raise ValueError(
                f"Task {task_id} is not in 'review_ready' status "
                f"(current: '{row['status']}')"
            )
        conn.execute(
            """UPDATE tasks
               SET status = 'done', completed_at = CURRENT_TIMESTAMP, reviewer = ?
               WHERE id = ?""",
            (req.agent_id, task_id),
        )
        approval_text = req.comment or "Task approved."
        conn.execute(
            """INSERT INTO task_comments
               (task_id, author, comment_type, content)
               VALUES (?, ?, 'approval', ?)""",
            (task_id, req.agent_id, approval_text),
        )
        conn.commit()
        return {"title": row["title"], "assigned_to": row["assigned_to"]}

    try:
        result = execute_with_retry(_approve)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "task_id": task_id,
        "title": result["title"],
        "status": "done",
        "approved_by": req.agent_id,
    }


@router.post("/tasks/{task_id}/reject")
async def reject_task(task_id: int, req: TaskRejectRequest):
    """Reject a task in review_ready status, sending it back with feedback."""

    def _reject(conn: sqlite3.Connection) -> dict:
        row = conn.execute(
            "SELECT id, status, title, retry_count FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")
        if row["status"] != "review_ready":
            raise ValueError(
                f"Task {task_id} is not in 'review_ready' status "
                f"(current: '{row['status']}')"
            )
        new_retry = row["retry_count"] + 1
        conn.execute(
            """UPDATE tasks
               SET status = 'rejected', retry_count = ?, reviewer = ?
               WHERE id = ?""",
            (new_retry, req.agent_id, task_id),
        )
        conn.execute(
            """INSERT INTO task_comments
               (task_id, author, comment_type, content)
               VALUES (?, ?, 'change_request', ?)""",
            (task_id, req.agent_id, req.reason),
        )
        conn.commit()
        return {"title": row["title"], "retry_count": new_retry}

    try:
        result = execute_with_retry(_reject)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "task_id": task_id,
        "title": result["title"],
        "status": "rejected",
        "rejected_by": req.agent_id,
        "retry_count": result["retry_count"],
    }
