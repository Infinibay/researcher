"""Tool for creating epics."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class CreateEpicInput(BaseModel):
    title: str = Field(..., description="Epic title")
    description: str = Field(..., description="Epic description")
    priority: int = Field(default=2, ge=1, le=5, description="Priority 1-5")


class CreateEpicTool(PabadaBaseTool):
    name: str = "create_epic"
    description: str = (
        "Create a new epic for organizing related tasks. "
        "Epics group milestones and provide high-level project structure."
    )
    args_schema: Type[BaseModel] = CreateEpicInput

    def _run(self, title: str, description: str, priority: int = 2) -> str:
        project_id = self._validate_project_context()
        created_by = self.agent_id or "orchestrator"

        def _create(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                """INSERT INTO epics
                   (project_id, title, description, status, priority, created_by)
                   VALUES (?, ?, ?, 'open', ?, ?)""",
                (project_id, title, description, priority, created_by),
            )
            conn.commit()
            return cursor.lastrowid

        try:
            epic_id = execute_with_retry(_create)
        except Exception as e:
            return self._error(f"Failed to create epic: {e}")

        self._log_tool_usage(f"Created epic #{epic_id}: {title}")
        return self._success({
            "epic_id": epic_id,
            "title": title,
            "status": "open",
            "priority": priority,
        })
