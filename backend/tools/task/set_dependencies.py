"""Tool for setting task dependencies with cycle detection."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class SetTaskDependenciesInput(BaseModel):
    task_id: int = Field(..., description="ID of the dependent task")
    depends_on: list[int] = Field(
        ..., description="List of task IDs this task depends on"
    )
    dependency_type: str = Field(
        default="blocks", description="Type: 'blocks', 'related_to', or 'parent_of'"
    )


class SetTaskDependenciesTool(PabadaBaseTool):
    name: str = "set_task_dependencies"
    description: str = (
        "Set dependencies for a task. Validates that no circular dependencies "
        "are created (DAG enforcement)."
    )
    args_schema: Type[BaseModel] = SetTaskDependenciesInput

    def _run(
        self,
        task_id: int,
        depends_on: list[int],
        dependency_type: str = "blocks",
    ) -> str:
        valid_types = ("blocks", "related_to", "parent_of")
        if dependency_type not in valid_types:
            return self._error(
                f"Invalid dependency_type '{dependency_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        def _set_deps(conn: sqlite3.Connection) -> dict:
            # Verify task exists
            row = conn.execute(
                "SELECT id FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found")

            # Verify all dependency targets exist
            for dep_id in depends_on:
                if dep_id == task_id:
                    raise ValueError("A task cannot depend on itself")
                row = conn.execute(
                    "SELECT id FROM tasks WHERE id = ?", (dep_id,)
                ).fetchone()
                if not row:
                    raise ValueError(f"Dependency task {dep_id} not found")

            # Check for cycles using BFS
            if dependency_type == "blocks":
                for dep_id in depends_on:
                    if _would_create_cycle(conn, task_id, dep_id):
                        raise ValueError(
                            f"Adding dependency {task_id} -> {dep_id} would create a cycle"
                        )

            # Remove existing dependencies of same type and re-insert
            conn.execute(
                """DELETE FROM task_dependencies
                   WHERE task_id = ? AND dependency_type = ?""",
                (task_id, dependency_type),
            )

            for dep_id in depends_on:
                conn.execute(
                    """INSERT OR IGNORE INTO task_dependencies
                       (task_id, depends_on_task_id, dependency_type)
                       VALUES (?, ?, ?)""",
                    (task_id, dep_id, dependency_type),
                )

            conn.commit()
            return {"count": len(depends_on)}

        try:
            result = execute_with_retry(_set_deps)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(
            f"Set {result['count']} dependencies for task #{task_id}"
        )
        return self._success({
            "task_id": task_id,
            "depends_on": depends_on,
            "dependency_type": dependency_type,
        })


def _would_create_cycle(
    conn: sqlite3.Connection, task_id: int, new_dep_id: int
) -> bool:
    """Check if adding task_id -> new_dep_id would create a cycle.

    Uses BFS from new_dep_id following existing dependencies.
    If we reach task_id, a cycle would be created.
    """
    visited = set()
    queue = [new_dep_id]

    while queue:
        current = queue.pop(0)
        if current == task_id:
            return True
        if current in visited:
            continue
        visited.add(current)

        rows = conn.execute(
            """SELECT depends_on_task_id FROM task_dependencies
               WHERE task_id = ? AND dependency_type = 'blocks'""",
            (current,),
        ).fetchall()
        for row in rows:
            queue.append(row["depends_on_task_id"])

    return False
