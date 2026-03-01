"""Tool for updating task status with state machine validation."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.state.dependency_validator import DependencyValidator
from backend.state.machine import TASK_STATUSES, VALID_TRANSITIONS
from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


def _auto_complete_parent(
    conn: sqlite3.Connection,
    table: str,
    fk_column: str,
    parent_id: int,
) -> None:
    """Auto-complete an epic or milestone when all its tasks are resolved."""
    row = conn.execute(
        f"""SELECT COUNT(*) as pending
            FROM tasks
            WHERE {fk_column} = ?
              AND status NOT IN ('done', 'cancelled', 'failed')""",
        (parent_id,),
    ).fetchone()

    if row["pending"] == 0:
        # All tasks resolved — mark parent as completed if it isn't already
        current = conn.execute(
            f"SELECT status FROM {table} WHERE id = ?", (parent_id,)
        ).fetchone()
        if current and current["status"] != "completed":
            conn.execute(
                f"UPDATE {table} SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (parent_id,),
            )
            conn.commit()


class UpdateTaskStatusInput(BaseModel):
    task_id: int = Field(..., description="ID of the task to update")
    status: str = Field(..., description=f"New status: {', '.join(TASK_STATUSES)}")
    comment: str | None = Field(
        default=None, description="Optional comment explaining the status change"
    )
    branch_name: str | None = Field(
        default=None,
        description="Optional branch name to set on the task (fallback if GitBranchTool didn't auto-set it)",
    )
    pr_url: str | None = Field(
        default=None,
        description="Optional PR URL to set on the task (fallback if CreatePRTool didn't auto-set it)",
    )


class UpdateTaskStatusTool(PabadaBaseTool):
    name: str = "update_task_status"
    description: str = (
        "Update the status of a task. Validates state transitions "
        "(e.g., can only go from in_progress to review_ready). "
        "You must use a real task ID — call read_tasks first if you "
        "don't know which IDs exist."
    )
    args_schema: Type[BaseModel] = UpdateTaskStatusInput

    def _run(
        self,
        task_id: int,
        status: str,
        comment: str | None = None,
        branch_name: str | None = None,
        pr_url: str | None = None,
    ) -> str:
        if status not in VALID_TRANSITIONS:
            return self._error(f"Invalid status '{status}'. Must be one of: {', '.join(TASK_STATUSES)}")

        agent_id = self.agent_id or "unknown"

        def _update(conn: sqlite3.Connection) -> dict:
            row = conn.execute(
                "SELECT id, status, title, type FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if not row:
                raise ValueError(f"Task {task_id} not found")

            current = row["status"]
            allowed = VALID_TRANSITIONS.get(current, set())
            if status not in allowed:
                raise ValueError(
                    f"Invalid transition: '{current}' -> '{status}'. "
                    f"Allowed transitions from '{current}': {allowed or 'none (terminal state)'}"
                )

            # Block transition to in_progress if dependencies are not met
            if status == "in_progress" and not DependencyValidator.can_start(task_id):
                unmet = DependencyValidator.get_unmet_dependencies(task_id)
                blockers = ", ".join(
                    f"#{d['id']} {d['title']} ({d['status']})" for d in unmet
                )
                raise ValueError(
                    f"Task {task_id} cannot start — blocked by: {blockers}"
                )

            # For code tasks transitioning to done, require an approved code review
            if status == "done" and row["type"] in ("code", "bug_fix"):
                review = conn.execute(
                    """SELECT id FROM code_reviews
                       WHERE task_id = ? AND status = 'approved'
                       LIMIT 1""",
                    (task_id,),
                ).fetchone()
                if not review:
                    # Also check by branch name as fallback
                    branch = conn.execute(
                        "SELECT branch_name FROM tasks WHERE id = ?",
                        (task_id,),
                    ).fetchone()
                    if branch and branch["branch_name"]:
                        review = conn.execute(
                            """SELECT id FROM code_reviews
                               WHERE branch = ? AND status = 'approved'
                               LIMIT 1""",
                            (branch["branch_name"],),
                        ).fetchone()
                    if not review:
                        raise ValueError(
                            f"Task {task_id} (type='{row['type']}') cannot move to 'done' "
                            f"without an approved code review"
                        )

            # Update task — build SET clause dynamically
            set_parts = ["status = ?"]
            params_list: list = [status]

            if status in ("done", "cancelled", "failed"):
                set_parts.append("completed_at = CURRENT_TIMESTAMP")

            if branch_name is not None:
                set_parts.append("branch_name = ?")
                params_list.append(branch_name)
            if pr_url is not None:
                set_parts.append("pr_url = ?")
                params_list.append(pr_url)

            params_list.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?",
                params_list,
            )

            # Add comment if provided
            if comment:
                conn.execute(
                    """INSERT INTO task_comments (task_id, author, comment_type, content)
                       VALUES (?, ?, 'comment', ?)""",
                    (task_id, agent_id, comment),
                )

            conn.commit()

            # Auto-complete epic/milestone when all tasks are resolved
            if status in ("done", "cancelled", "failed"):
                task_row = conn.execute(
                    "SELECT epic_id, milestone_id FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()

                if task_row and task_row["epic_id"]:
                    _auto_complete_parent(
                        conn, "epics", "epic_id", task_row["epic_id"]
                    )
                if task_row and task_row["milestone_id"]:
                    _auto_complete_parent(
                        conn, "milestones", "milestone_id", task_row["milestone_id"]
                    )

            return {"title": row["title"], "old_status": current}

        try:
            result = execute_with_retry(_update)
        except ValueError as e:
            return self._error(str(e))

        self._log_tool_usage(
            f"Task #{task_id} status: {result['old_status']} -> {status}"
        )
        return self._success({
            "task_id": task_id,
            "title": result["title"],
            "old_status": result["old_status"],
            "new_status": status,
        })
