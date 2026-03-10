"""Tool for approving tasks after review."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class ApproveTaskInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to approve")
    comment: str | None = Field(
        default=None, description="Optional approval comment"
    )


class ApproveTaskTool(InfinibayBaseTool):
    name: str = "approve_task"
    description: str = (
        "Approve a task that is in review_ready status, moving it to done. "
        "Only reviewers should use this tool."
    )
    args_schema: Type[BaseModel] = ApproveTaskInput

    def _run(self, task_id: int, comment: str | None = None) -> str:
        agent_id = self._validate_agent_context()

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

            # Update task to done
            conn.execute(
                """UPDATE tasks
                   SET status = 'done', completed_at = CURRENT_TIMESTAMP, reviewer = ?
                   WHERE id = ?""",
                (agent_id, task_id),
            )

            # Add approval comment
            approval_text = comment or "Task approved."
            conn.execute(
                """INSERT INTO task_comments
                   (task_id, author, comment_type, content)
                   VALUES (?, ?, 'approval', ?)""",
                (task_id, agent_id, approval_text),
            )

            conn.commit()
            return {"title": row["title"], "assigned_to": row["assigned_to"]}

        try:
            result = execute_with_retry(_approve)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(f"Approved task #{task_id}: {result['title']}")
        return self._success({
            "task_id": task_id,
            "title": result["title"],
            "status": "done",
            "approved_by": agent_id,
        })
