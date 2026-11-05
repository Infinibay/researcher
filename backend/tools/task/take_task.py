"""Tool for an agent to take/claim a task."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry


class TakeTaskInput(BaseModel):
    """Identify the task within the tool's already-bound project."""

    task_id: int = Field(..., description="ID of the task to take")


class TakeTaskTool(InfinibayBaseTool):
    """Claim remaining legacy tasks or return a read-only native owner hint."""

    name: str = "take_task"
    description: str = (
        "Claim a task and set its status to in_progress. "
        "Only tasks in 'backlog' or 'pending' status can be taken. "
        "Before calling this tool, verify the task status with GetTaskTool "
        "or ReadTasksTool — do NOT attempt to take tasks that are already "
        "'in_progress', 'done', or assigned to another agent."
    )
    args_schema: Type[BaseModel] = TakeTaskInput

    def _run(self, task_id: int) -> str:
        """Scope every read/claim to the bound project and never claim owner-managed work."""
        agent_id = self._validate_agent_context()
        project_id = self._validate_project_context()

        def _take(conn: sqlite3.Connection) -> dict:
            """Resolve the owner boundary and claim remaining work in one write transaction."""
            from backend.runtime.legacy_handoff import native_owner_handoff

            conn.execute("BEGIN IMMEDIATE")
            handoff = native_owner_handoff(conn, project_id, task_id)
            if handoff is not None:
                conn.rollback()
                return handoff
            row = conn.execute(
                "SELECT id, status, title, assigned_to FROM tasks WHERE id = ? AND project_id = ?",
                (task_id, project_id),
            ).fetchone()

            if not row:
                raise ValueError("Task not found in the bound project")

            status = row["status"]
            if status not in ("backlog", "pending"):
                # Show other available tasks so the agent can pick one
                available = conn.execute(
                    """SELECT id, title FROM tasks
                       WHERE project_id = ?
                       AND status IN ('backlog', 'pending')
                       ORDER BY priority DESC, id
                       LIMIT 10""",
                    (project_id,),
                ).fetchall()
                alt = ""
                if available:
                    ids = ", ".join(f"#{r['id']}" for r in available)
                    alt = f" Available tasks: {ids}."
                raise ValueError(
                    f"Task {task_id} cannot be taken: current status is '{status}' "
                    f"(must be 'backlog' or 'pending').{alt}"
                )

            if row["assigned_to"] and row["assigned_to"] != agent_id:
                raise ValueError(
                    f"Task {task_id} is already assigned to '{row['assigned_to']}'"
                )

            conn.execute(
                """UPDATE tasks
                   SET assigned_to = ?, status = 'in_progress'
                   WHERE id = ? AND project_id = ? AND status IN ('backlog','pending')""",
                (agent_id, task_id, project_id),
            )
            conn.commit()
            return {"title": row["title"]}

        try:
            result = execute_with_retry(_take)
        except ValueError as e:
            return self._error(str(e))

        if result.get("delivery") == "native_owner_handoff":
            self._log_tool_usage(f"Owner handoff for task #{task_id}; no task claim")
            return self._success(result)
        self._log_tool_usage(f"Took task #{task_id}: {result['title']}")
        return self._success({
            "task_id": task_id,
            "title": result["title"],
            "status": "in_progress",
            "assigned_to": agent_id,
        })
