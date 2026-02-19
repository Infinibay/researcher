"""Tool for getting detailed task information."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class GetTaskInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to retrieve")
    include_comments: bool = Field(
        default=False, description="Include task comments"
    )
    include_dependencies: bool = Field(
        default=False, description="Include task dependencies"
    )


class GetTaskTool(PabadaBaseTool):
    name: str = "get_task"
    description: str = (
        "Get detailed information about a specific task, "
        "optionally including comments and dependencies."
    )
    args_schema: Type[BaseModel] = GetTaskInput

    def _run(
        self,
        task_id: int,
        include_comments: bool = False,
        include_dependencies: bool = False,
    ) -> str:
        def _get(conn: sqlite3.Connection) -> dict:
            row = conn.execute(
                """SELECT t.*,
                          e.title AS epic_title,
                          m.title AS milestone_title
                   FROM tasks t
                   LEFT JOIN epics e ON t.epic_id = e.id
                   LEFT JOIN milestones m ON t.milestone_id = m.id
                   WHERE t.id = ?""",
                (task_id,),
            ).fetchone()

            if not row:
                raise ValueError(f"Task {task_id} not found")

            task = dict(row)

            if include_comments:
                comments = conn.execute(
                    """SELECT id, author, comment_type, content, created_at
                       FROM task_comments
                       WHERE task_id = ?
                       ORDER BY created_at ASC""",
                    (task_id,),
                ).fetchall()
                task["comments"] = [dict(c) for c in comments]

            if include_dependencies:
                # Tasks this depends on
                deps = conn.execute(
                    """SELECT td.depends_on_task_id, td.dependency_type,
                              t.title, t.status
                       FROM task_dependencies td
                       JOIN tasks t ON td.depends_on_task_id = t.id
                       WHERE td.task_id = ?""",
                    (task_id,),
                ).fetchall()
                task["depends_on"] = [dict(d) for d in deps]

                # Tasks that depend on this
                blocked = conn.execute(
                    """SELECT td.task_id, td.dependency_type,
                              t.title, t.status
                       FROM task_dependencies td
                       JOIN tasks t ON td.task_id = t.id
                       WHERE td.depends_on_task_id = ?""",
                    (task_id,),
                ).fetchall()
                task["blocks"] = [dict(b) for b in blocked]

            return task

        try:
            result = execute_with_retry(_get)
        except ValueError as e:
            return self._error(str(e))

        return self._success(result)
