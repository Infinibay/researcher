"""Tool for reading comments on a task."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class ReadCommentsInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to read comments from")
    limit: int = Field(
        default=20,
        description="Maximum number of comments to return (newest first)",
    )


class ReadCommentsTool(InfinibayBaseTool):
    name: str = "read_comments"
    description: str = (
        "Read comments on a task. Returns the most recent comments first. "
        "Use this BEFORE posting a comment to check what has already been "
        "discussed and avoid duplicating information."
    )
    args_schema: Type[BaseModel] = ReadCommentsInput

    def _run(self, task_id: int, limit: int = 20) -> str:
        def _read(conn: sqlite3.Connection) -> dict:
            # Verify task exists
            row = conn.execute(
                "SELECT id, title FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found")

            total = conn.execute(
                "SELECT COUNT(*) FROM task_comments WHERE task_id = ?",
                (task_id,),
            ).fetchone()[0]

            comments = conn.execute(
                """SELECT id, author, comment_type, content, created_at
                   FROM task_comments
                   WHERE task_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (task_id, limit),
            ).fetchall()

            return {
                "task_id": task_id,
                "task_title": row["title"],
                "total_comments": total,
                "showing": len(comments),
                "comments": [dict(c) for c in comments],
            }

        try:
            result = execute_with_retry(_read)
        except ValueError as e:
            return self._error(str(e))

        return self._success(result)
