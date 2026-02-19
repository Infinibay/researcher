"""Tool for adding comments to tasks."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry

COMMENT_TYPES = ("comment", "change_request", "approval", "question", "answer")


class AddCommentInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to comment on")
    comment: str = Field(..., description="Comment content")
    comment_type: str = Field(
        default="comment",
        description=f"Comment type: {', '.join(COMMENT_TYPES)}",
    )


class AddCommentTool(PabadaBaseTool):
    name: str = "add_comment"
    description: str = (
        "Add a comment to a task. Use different comment types for "
        "change requests, approvals, questions, or general comments."
    )
    args_schema: Type[BaseModel] = AddCommentInput

    def _run(
        self, task_id: int, comment: str, comment_type: str = "comment"
    ) -> str:
        if comment_type not in COMMENT_TYPES:
            return self._error(
                f"Invalid comment_type '{comment_type}'. "
                f"Must be one of: {', '.join(COMMENT_TYPES)}"
            )

        agent_id = self._validate_agent_context()

        def _add(conn: sqlite3.Connection) -> dict:
            # Verify task exists
            row = conn.execute(
                "SELECT id, title FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found")

            cursor = conn.execute(
                """INSERT INTO task_comments
                   (task_id, author, comment_type, content)
                   VALUES (?, ?, ?, ?)""",
                (task_id, agent_id, comment_type, comment),
            )
            conn.commit()
            return {"comment_id": cursor.lastrowid, "title": row["title"]}

        try:
            result = execute_with_retry(_add)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(
            f"Comment on task #{task_id} ({comment_type})"
        )
        return self._success({
            "comment_id": result["comment_id"],
            "task_id": task_id,
            "comment_type": comment_type,
            "author": agent_id,
        })
