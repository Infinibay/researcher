"""Tool for reading/listing tasks with filters."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReadTasksInput(BaseModel):
    status: str | None = Field(default=None, description="Filter by status")
    type: str | None = Field(default=None, description="Filter by task type")
    assignee: str | None = Field(default=None, description="Filter by assigned agent")
    epic_id: int | None = Field(default=None, description="Filter by epic ID")
    milestone_id: int | None = Field(default=None, description="Filter by milestone ID")
    limit: int = Field(default=50, ge=1, le=200, description="Max results to return")


class ReadTasksTool(PabadaBaseTool):
    name: str = "read_tasks"
    description: str = (
        "List tasks with optional filters for status, type, assignee, "
        "epic, or milestone. Ordered by priority (high first)."
    )
    args_schema: Type[BaseModel] = ReadTasksInput

    def _run(
        self,
        status: str | None = None,
        type: str | None = None,
        assignee: str | None = None,
        epic_id: int | None = None,
        milestone_id: int | None = None,
        limit: int = 50,
    ) -> str:
        project_id = self._validate_project_context()

        def _read(conn: sqlite3.Connection) -> list[dict]:
            conditions = ["t.project_id = ?"]
            params: list = [project_id]

            if status:
                conditions.append("t.status = ?")
                params.append(status)
            if type:
                conditions.append("t.type = ?")
                params.append(type)
            if assignee:
                conditions.append("t.assigned_to = ?")
                params.append(assignee)
            if epic_id is not None:
                conditions.append("t.epic_id = ?")
                params.append(epic_id)
            if milestone_id is not None:
                conditions.append("t.milestone_id = ?")
                params.append(milestone_id)

            where = " AND ".join(conditions)
            params.append(limit)

            rows = conn.execute(
                f"""SELECT t.id, t.title, t.type, t.status, t.priority,
                           t.estimated_complexity, t.assigned_to, t.reviewer,
                           t.branch_name, t.retry_count,
                           t.created_at, t.completed_at,
                           e.title AS epic_title,
                           m.title AS milestone_title
                    FROM tasks t
                    LEFT JOIN epics e ON t.epic_id = e.id
                    LEFT JOIN milestones m ON t.milestone_id = m.id
                    WHERE {where}
                    ORDER BY t.priority DESC, t.created_at ASC
                    LIMIT ?""",
                params,
            ).fetchall()

            return [dict(r) for r in rows]

        try:
            tasks = execute_with_retry(_read)
        except ValueError as e:
            return self._error(str(e))

        return self._success({"tasks": tasks, "count": len(tasks)})
