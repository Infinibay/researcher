"""Tool for reading/listing milestones with filters."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class ReadMilestonesInput(BaseModel):
    epic_id: int | None = Field(
        default=None,
        description="Filter by parent epic ID. Omit to show all milestones.",
    )
    status: str | None = Field(
        default=None,
        description=(
            "Filter by status (open, in_progress, completed, cancelled). "
            "Omit to show all statuses."
        ),
    )
    milestone_id: int | None = Field(
        default=None,
        description="Get a single milestone by ID. Omit to list all milestones.",
    )


class ReadMilestonesTool(PabadaBaseTool):
    name: str = "read_milestones"
    description: str = (
        "List milestones with optional filters for epic or status, including "
        "task counts per milestone. Use this to discover milestone IDs before "
        "creating tasks."
    )
    args_schema: Type[BaseModel] = ReadMilestonesInput

    _PASSTHROUGH = {"all", "any", "none", "null", "*", ""}

    def _run(
        self,
        epic_id: int | None = None,
        status: str | None = None,
        milestone_id: int | None = None,
    ) -> str:
        project_id = self._validate_project_context()

        if status and status.strip().lower() in self._PASSTHROUGH:
            status = None

        def _read(conn: sqlite3.Connection) -> list[dict]:
            conditions = ["m.project_id = ?"]
            params: list = [project_id]

            if milestone_id is not None:
                conditions.append("m.id = ?")
                params.append(milestone_id)
            if epic_id is not None:
                conditions.append("m.epic_id = ?")
                params.append(epic_id)
            if status:
                conditions.append("m.status = ?")
                params.append(status)

            where = " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT m.id, m.epic_id, m.title, m.description,
                           m.status, m.due_date, m.created_at,
                           m.completed_at,
                           e.title AS epic_title,
                           (SELECT COUNT(*) FROM tasks t
                            WHERE t.milestone_id = m.id) AS task_count,
                           (SELECT COUNT(*) FROM tasks t
                            WHERE t.milestone_id = m.id
                              AND t.status = 'done') AS tasks_done
                    FROM milestones m
                    LEFT JOIN epics e ON m.epic_id = e.id
                    WHERE {where}
                    ORDER BY m.epic_id, m.order_index, m.created_at ASC""",
                params,
            ).fetchall()

            return [dict(r) for r in rows]

        try:
            milestones = execute_with_retry(_read)
        except ValueError as e:
            return self._error(str(e))

        return self._success({"milestones": milestones, "count": len(milestones)})
