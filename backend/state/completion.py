"""Project completion state detection."""

import logging
import sqlite3
from enum import Enum

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class CompletionState(str, Enum):
    ACTIVE = "active"
    WAITING_FOR_RESEARCH = "waiting_for_research"
    IDLE_OBJECTIVES_MET = "idle_objectives_met"
    IDLE_OBJECTIVES_PENDING = "idle_objectives_pending"


class CompletionDetector:
    """Determines the completion state of a project."""

    @staticmethod
    def detect(project_id: int) -> CompletionState:
        def _query(conn: sqlite3.Connection) -> CompletionState:
            # Check for in-progress tasks
            ip_rows = conn.execute(
                """SELECT id, type FROM tasks
                   WHERE project_id = ? AND status = 'in_progress'""",
                (project_id,),
            ).fetchall()

            if ip_rows:
                types = {r["type"] for r in ip_rows}
                dev_types = types - {"research", "investigation"}
                if not dev_types:
                    return CompletionState.WAITING_FOR_RESEARCH
                return CompletionState.ACTIVE

            # No tasks in progress — check objectives
            row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                   FROM epics WHERE project_id = ?""",
                (project_id,),
            ).fetchone()

            if row and row["total"] > 0 and row["completed"] == row["total"]:
                return CompletionState.IDLE_OBJECTIVES_MET
            return CompletionState.IDLE_OBJECTIVES_PENDING

        return execute_with_retry(_query)

    @staticmethod
    def notify_user_if_idle(project_id: int, notifier) -> None:
        """Send a user-facing notification based on the current completion state."""
        state = CompletionDetector.detect(project_id)

        messages = {
            CompletionState.IDLE_OBJECTIVES_MET: (
                f"All tasks for project {project_id} are complete "
                f"and all objectives have been met. Please finalize the project."
            ),
            CompletionState.IDLE_OBJECTIVES_PENDING: (
                f"All current tasks for project {project_id} are done, "
                f"but not all objectives are met. "
                f"Consider creating additional tasks or starting a brainstorming session."
            ),
            CompletionState.WAITING_FOR_RESEARCH: (
                f"Project {project_id} is waiting for research tasks to complete. "
                f"Please review the findings once research is done and decide on next steps."
            ),
        }

        message = messages.get(state)
        if message:
            notifier.notify_user(
                project_id=project_id,
                from_agent="system",
                message=message,
            )
