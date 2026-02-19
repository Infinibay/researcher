"""Tool for creating milestones."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class CreateMilestoneInput(BaseModel):
    title: str = Field(..., description="Milestone title")
    description: str = Field(..., description="Milestone description")
    epic_id: int = Field(..., description="Parent epic ID")
    due_date: str | None = Field(
        default=None, description="Due date in YYYY-MM-DD format"
    )


class CreateMilestoneTool(PabadaBaseTool):
    name: str = "create_milestone"
    description: str = (
        "Create a new milestone within an epic. "
        "Milestones track progress toward epic completion."
    )
    args_schema: Type[BaseModel] = CreateMilestoneInput

    def _run(
        self,
        title: str,
        description: str,
        epic_id: int,
        due_date: str | None = None,
    ) -> str:
        project_id = self._validate_project_context()

        def _create(conn: sqlite3.Connection) -> int:
            # Verify epic exists
            row = conn.execute(
                "SELECT id, project_id FROM epics WHERE id = ?", (epic_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Epic {epic_id} not found")
            if row["project_id"] != project_id:
                raise ValueError(f"Epic {epic_id} does not belong to current project")

            cursor = conn.execute(
                """INSERT INTO milestones
                   (project_id, epic_id, title, description, status, due_date)
                   VALUES (?, ?, ?, ?, 'open', ?)""",
                (project_id, epic_id, title, description, due_date),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            milestone_id = execute_with_retry(_create)
        except ValueError as e:
            return self._error(str(e))
        except Exception as e:
            return self._error(f"Failed to create milestone: {e}")

        self._log_tool_usage(f"Created milestone #{milestone_id}: {title}")
        return self._success({
            "milestone_id": milestone_id,
            "title": title,
            "epic_id": epic_id,
            "status": "open",
            "due_date": due_date,
        })
