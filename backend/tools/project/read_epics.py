"""Tool for reading/listing epics with filters."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class ReadEpicsInput(BaseModel):
    status: str | None = Field(
        default=None,
        description=(
            "Filter by status (open, in_progress, completed, cancelled). "
            "Omit to show all statuses."
        ),
    )
    epic_id: int | None = Field(
        default=None,
        description="Get a single epic by ID. Omit to list all epics.",
    )


class ReadEpicsTool(InfinibayBaseTool):
    name: str = "read_epics"
    description: str = (
        "List epics with optional status filter, including task and milestone "
        "counts per epic. Use this to discover epic IDs before creating "
        "milestones or tasks."
    )
    args_schema: Type[BaseModel] = ReadEpicsInput

    _PASSTHROUGH = {"all", "any", "none", "null", "*", ""}

    def _run(
        self,
        status: str | None = None,
        epic_id: int | None = None,
    ) -> str:
        project_id = self._validate_project_context()

        if status and status.strip().lower() in self._PASSTHROUGH:
            status = None

        def _read(conn: sqlite3.Connection) -> list[dict]:
            conditions = ["e.project_id = ?"]
            params: list = [project_id]

            if epic_id is not None:
                conditions.append("e.id = ?")
                params.append(epic_id)
            if status:
                conditions.append("e.status = ?")
                params.append(status)

            where = " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT e.id, e.title, e.description, e.status,
                           e.priority, e.created_by, e.created_at,
                           e.completed_at,
                           (SELECT COUNT(*) FROM milestones m
                            WHERE m.epic_id = e.id) AS milestone_count,
                           (SELECT COUNT(*) FROM tasks t
                            WHERE t.epic_id = e.id) AS task_count,
                           (SELECT COUNT(*) FROM tasks t
                            WHERE t.epic_id = e.id
                              AND t.status = 'done') AS tasks_done
                    FROM epics e
                    WHERE {where}
                    ORDER BY e.priority DESC, e.created_at ASC""",
                params,
            ).fetchall()

            return [dict(r) for r in rows]

        try:
            epics = execute_with_retry(_read)
        except ValueError as e:
            return self._error(str(e))

        return self._success({"epics": epics, "count": len(epics)})
