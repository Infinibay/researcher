"""Tool for an agent to take/claim a task."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class TakeTaskInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to take")


class TakeTaskTool(PabadaBaseTool):
    name: str = "take_task"
    description: str = (
        "Claim a task and set its status to in_progress. "
        "Only tasks in 'backlog' or 'pending' status can be taken."
    )
    args_schema: Type[BaseModel] = TakeTaskInput

    def _run(self, task_id: int) -> str:
        agent_id = self._validate_agent_context()

        def _take(conn: sqlite3.Connection) -> dict:
            row = conn.execute(
                "SELECT id, status, title, assigned_to FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if not row:
                raise ValueError(f"Task {task_id} not found")

            status = row["status"]
            if status not in ("backlog", "pending"):
                raise ValueError(
                    f"Task {task_id} cannot be taken: current status is '{status}' "
                    f"(must be 'backlog' or 'pending')"
                )

            if row["assigned_to"] and row["assigned_to"] != agent_id:
                raise ValueError(
                    f"Task {task_id} is already assigned to '{row['assigned_to']}'"
                )

            conn.execute(
                """UPDATE tasks
                   SET assigned_to = ?, status = 'in_progress'
                   WHERE id = ?""",
                (agent_id, task_id),
            )
            conn.commit()
            return {"title": row["title"]}

        try:
            result = execute_with_retry(_take)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(f"Took task #{task_id}: {result['title']}")
        return self._success({
            "task_id": task_id,
            "title": result["title"],
            "status": "in_progress",
            "assigned_to": agent_id,
        })
