"""Task flow event handlers."""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.base import AgentKilledError as _AgentKilledError

from .base import EventHandler, _parse_payload

logger = logging.getLogger(__name__)


class TaskFlowHandler(EventHandler):
    """Handles task_available and task_resume events.

    Dispatches to DevelopmentFlow or ResearchFlow based on task type.
    """

    def execute(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Acknowledge owner-managed task hints without claiming them; dispatch remaining legacy tasks."""
        from backend.flows.helpers import log_flow_event

        payload = _parse_payload(event)
        task_id = payload.get("task_id")
        project_id = event["project_id"]
        agent_id = event["agent_id"]

        if task_id is None:
            logger.warning("TaskFlowHandler: no task_id in payload for event %d", event["id"])
            return

        from backend.runtime.legacy_handoff import legacy_event_handoff

        handoff = legacy_event_handoff(project_id, task_id)
        if handoff is not None:
            log_flow_event(project_id, "native_owner_handoff", "agent_loop", "task", task_id, handoff)
            return handoff
        task_type = self._get_task_type(task_id, project_id)

        # For task_available, attempt atomic claim
        if event["event_type"] == "task_available":
            if not self._claim_task(task_id, agent_id, project_id):
                logger.info(
                    "TaskFlowHandler: agent %s failed to claim task %d (already claimed)",
                    agent_id, task_id,
                )
                return

        logger.info(
            "TaskFlowHandler: running %s flow for task %d (agent=%s, project=%d)",
            task_type, task_id, agent_id, project_id,
        )

        try:
            if task_type == "research":
                from backend.flows.research_flow import ResearchFlow
                flow = ResearchFlow()
                handoff = flow.kickoff(inputs={
                    "project_id": project_id,
                    "task_id": task_id,
                    "researcher_id": agent_id,
                })
                log_flow_event(
                    project_id, "native_owner_handoff",
                    "agent_loop", "task", task_id, handoff,
                )
                return handoff
            else:
                from backend.flows.development_flow import DevelopmentFlow
                flow = DevelopmentFlow()
                flow.kickoff(inputs={
                    "project_id": project_id,
                    "task_id": task_id,
                    "developer_id": agent_id,
                })
                log_flow_event(
                    project_id, "development_flow_completed",
                    "agent_loop", "task", task_id,
                )
        except _AgentKilledError:
            logger.info(
                "TaskFlowHandler: task %d interrupted (agent %s killed)", task_id, agent_id,
            )
            raise
        except Exception:
            logger.exception(
                "TaskFlowHandler: flow failed for task %d (agent=%s)", task_id, agent_id,
            )
            log_flow_event(
                project_id, "agent_loop_flow_failed",
                "agent_loop", "task", task_id,
            )
            raise

    def _get_task_type(self, task_id: int, project_id: int) -> str:
        """Look up the task type from the DB."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _query(conn: sqlite3.Connection) -> str:
            """Read only the requested task inside its actual project."""
            row = conn.execute(
                "SELECT type FROM tasks WHERE id = ? AND project_id = ?", (task_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("Task not found in project scope")
            return row["type"]

        return execute_with_retry(_query)

    def _claim_task(self, task_id: int, agent_id: str, project_id: int) -> bool:
        """Atomically claim a task."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _claim(conn: sqlite3.Connection) -> bool:
            """Check ownership and claim eligible legacy work under the same write lock."""
            from backend.runtime.lifecycle import require_legacy_task

            conn.execute("BEGIN IMMEDIATE")
            require_legacy_task(conn, task_id)
            cursor = conn.execute(
                """UPDATE tasks SET assigned_to = ?, status = 'in_progress'
                   WHERE id = ? AND project_id = ? AND status IN ('backlog', 'pending')
                   AND (assigned_to IS NULL OR assigned_to = '' OR assigned_to = ?)""",
                (agent_id, task_id, project_id, agent_id),
            )
            conn.commit()
            return cursor.rowcount > 0

        return execute_with_retry(_claim)
