"""Tool for rejecting tasks after review."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class RejectTaskInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to reject")
    reason: str = Field(..., description="Reason for rejection / change request")


class RejectTaskTool(InfinibayBaseTool):
    name: str = "reject_task"
    description: str = (
        "Reject a task that is in review_ready status, sending it back "
        "to in_progress with a change request comment."
    )
    args_schema: Type[BaseModel] = RejectTaskInput

    def _run(self, task_id: int, reason: str) -> str:
        agent_id = self._validate_agent_context()

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

            # Update task to rejected
            conn.execute(
                """UPDATE tasks
                   SET status = 'rejected', retry_count = ?, reviewer = ?
                   WHERE id = ?""",
                (new_retry, agent_id, task_id),
            )

            # Add change_request comment
            conn.execute(
                """INSERT INTO task_comments
                   (task_id, author, comment_type, content)
                   VALUES (?, ?, 'change_request', ?)""",
                (task_id, agent_id, reason),
            )

            conn.commit()
            return {"title": row["title"], "retry_count": new_retry}

        try:
            result = execute_with_retry(_reject)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(
            f"Rejected task #{task_id} (retry #{result['retry_count']})"
        )
        return self._success({
            "task_id": task_id,
            "title": result["title"],
            "status": "rejected",
            "rejected_by": agent_id,
            "retry_count": result["retry_count"],
        })
