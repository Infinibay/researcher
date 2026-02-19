"""Tool for creating tasks."""

import json
import sqlite3
from typing import Literal, Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry

TASK_TYPES = (
    "plan", "research", "code", "review", "test",
    "design", "integrate", "documentation", "bug_fix",
)
COMPLEXITY_LEVELS = ("trivial", "low", "medium", "high", "very_high")


class CreateTaskInput(BaseModel):
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    type: str = Field(..., description=f"Task type: {', '.join(TASK_TYPES)}")
    milestone_id: int | None = Field(default=None, description="Associated milestone ID")
    epic_id: int | None = Field(default=None, description="Associated epic ID")
    priority: int = Field(default=2, ge=1, le=5, description="Priority 1 (lowest) to 5 (highest)")
    complexity: str = Field(default="medium", description=f"Complexity: {', '.join(COMPLEXITY_LEVELS)}")
    depends_on: list[int] = Field(default_factory=list, description="List of task IDs this depends on")


class CreateTaskTool(PabadaBaseTool):
    name: str = "create_task"
    description: str = (
        "Create a new task in the project. "
        "Specify type, priority, complexity, and optional dependencies."
    )
    args_schema: Type[BaseModel] = CreateTaskInput

    def _run(
        self,
        title: str,
        description: str,
        type: str,
        milestone_id: int | None = None,
        epic_id: int | None = None,
        priority: int = 2,
        complexity: str = "medium",
        depends_on: list[int] | None = None,
    ) -> str:
        if depends_on is None:
            depends_on = []

        if type not in TASK_TYPES:
            return self._error(f"Invalid task type '{type}'. Must be one of: {', '.join(TASK_TYPES)}")
        if complexity not in COMPLEXITY_LEVELS:
            return self._error(f"Invalid complexity '{complexity}'. Must be one of: {', '.join(COMPLEXITY_LEVELS)}")

        project_id = self._validate_project_context()
        created_by = self.agent_id or "unknown"

        def _create(conn: sqlite3.Connection) -> dict:
            # Validate epic/milestone exist if provided
            if epic_id is not None:
                row = conn.execute("SELECT id FROM epics WHERE id = ?", (epic_id,)).fetchone()
                if not row:
                    raise ValueError(f"Epic {epic_id} not found")

            if milestone_id is not None:
                row = conn.execute("SELECT id FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
                if not row:
                    raise ValueError(f"Milestone {milestone_id} not found")

            # Validate dependencies exist
            for dep_id in depends_on:
                row = conn.execute("SELECT id FROM tasks WHERE id = ?", (dep_id,)).fetchone()
                if not row:
                    raise ValueError(f"Dependency task {dep_id} not found")

            cursor = conn.execute(
                """INSERT INTO tasks
                   (project_id, epic_id, milestone_id, type, status, title,
                    description, priority, estimated_complexity, created_by)
                   VALUES (?, ?, ?, ?, 'backlog', ?, ?, ?, ?, ?)""",
                (project_id, epic_id, milestone_id, type, title,
                 description, priority, complexity, created_by),
            )
            task_id = cursor.lastrowid

            # Create dependencies
            for dep_id in depends_on:
                conn.execute(
                    """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
                       VALUES (?, ?, 'blocks')""",
                    (task_id, dep_id),
                )

            conn.commit()
            return {"task_id": task_id}

        try:
            result = execute_with_retry(_create)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(f"Created task #{result['task_id']}: {title}")
        return self._success({
            "task_id": result["task_id"],
            "title": title,
            "type": type,
            "status": "backlog",
            "priority": priority,
            "complexity": complexity,
            "dependencies": depends_on,
        })
