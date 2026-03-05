"""Tool for checking task dependency status."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class CheckDependenciesInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to check dependencies for")


class CheckDependenciesTool(PabadaBaseTool):
    name: str = "check_dependencies"
    description: str = (
        "Check what blocks a task and what it would unblock. Shows "
        "dependency status, whether the task can start, and a "
        "human-readable summary."
    )
    args_schema: Type[BaseModel] = CheckDependenciesInput

    def _run(self, task_id: int) -> str:
        def _query(conn: sqlite3.Connection) -> dict:
            # What blocks this task (tasks it depends on)
            blocked_by = conn.execute(
                """\
                SELECT dep.id, dep.title, dep.status, td.dependency_type
                FROM task_dependencies td
                JOIN tasks dep ON dep.id = td.depends_on_task_id
                WHERE td.task_id = ?
                ORDER BY dep.id
                """,
                (task_id,),
            ).fetchall()

            # What this task unblocks (tasks depending on it)
            unblocks = conn.execute(
                """\
                SELECT t.id, t.title, t.status, td.dependency_type
                FROM task_dependencies td
                JOIN tasks t ON t.id = td.task_id
                WHERE td.depends_on_task_id = ?
                ORDER BY t.id
                """,
                (task_id,),
            ).fetchall()

            blocked_by_list = [dict(r) for r in blocked_by]
            unblocks_list = [dict(r) for r in unblocks]

            return {
                "blocked_by": blocked_by_list,
                "unblocks": unblocks_list,
            }

        result = _query_result = execute_with_retry(_query)

        # Use DependencyValidator for can_start check (lazy import)
        from backend.state.dependency_validator import DependencyValidator
        can_start = DependencyValidator.can_start(task_id)

        # Build human-readable summary
        blocked_by = result["blocked_by"]
        unblocks = result["unblocks"]
        summary_parts = []

        if not blocked_by and not unblocks:
            summary_parts.append(f"Task #{task_id} has no dependencies.")
        else:
            if blocked_by:
                blocking = [
                    b for b in blocked_by
                    if b["dependency_type"] == "blocks"
                    and b["status"] not in ("done", "cancelled")
                ]
                if blocking:
                    names = ", ".join(
                        f"#{b['id']} ({b['title']}, {b['status']})"
                        for b in blocking
                    )
                    summary_parts.append(f"BLOCKED by: {names}")
                else:
                    summary_parts.append("All blocking dependencies are resolved.")

            if unblocks:
                waiting = [
                    u for u in unblocks
                    if u["status"] not in ("done", "cancelled")
                ]
                if waiting:
                    names = ", ".join(
                        f"#{u['id']} ({u['title']})" for u in waiting
                    )
                    summary_parts.append(f"Completing this would unblock: {names}")

        summary = " ".join(summary_parts)

        output = {
            "task_id": task_id,
            "can_start": can_start,
            "blocked_by": blocked_by,
            "unblocks": unblocks,
            "summary": summary,
        }

        self._log_tool_usage(
            f"Checked dependencies for task #{task_id} (can_start={can_start})"
        )
        return self._success(output)
