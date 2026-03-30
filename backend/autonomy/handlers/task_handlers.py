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

    def execute(self, event: dict[str, Any]) -> None:
        from backend.flows.helpers import log_flow_event

        payload = _parse_payload(event)
        task_id = payload.get("task_id")
        project_id = event["project_id"]
        agent_id = event["agent_id"]

        if task_id is None:
            logger.warning("TaskFlowHandler: no task_id in payload for event %d", event["id"])
            return

        # Get task type to determine which flow to run
        task_type = self._get_task_type(task_id)

        # For task_available, attempt atomic claim
        if event["event_type"] == "task_available":
            if not self._claim_task(task_id, agent_id):
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
                flow.kickoff(inputs={
                    "project_id": project_id,
                    "task_id": task_id,
                    "researcher_id": agent_id,
                })
                log_flow_event(
                    project_id, "research_flow_completed",
                    "agent_loop", "task", task_id,
                )
            elif task_type == "investigation":
                from backend.flows.investigation_flow import InvestigationFlow
                flow = InvestigationFlow()
                flow.kickoff(inputs={
                    "project_id": project_id,
                    "task_id": task_id,
                    "researcher_id": agent_id,
                })
                log_flow_event(
                    project_id, "investigation_flow_completed",
                    "agent_loop", "task", task_id,
                )
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

    def _get_task_type(self, task_id: int) -> str:
        """Look up the task type from the DB."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _query(conn: sqlite3.Connection) -> str:
            row = conn.execute(
                "SELECT type FROM tasks WHERE id = ?", (task_id,),
            ).fetchone()
            return row["type"] if row else "code"

        return execute_with_retry(_query)

    def _claim_task(self, task_id: int, agent_id: str) -> bool:
        """Atomically claim a task."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _claim(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """UPDATE tasks SET assigned_to = ?, status = 'in_progress'
                   WHERE id = ? AND status IN ('backlog', 'pending')
                   AND (assigned_to IS NULL OR assigned_to = '' OR assigned_to = ?)""",
                (agent_id, task_id, agent_id),
            )
            conn.commit()
            return cursor.rowcount > 0

        return execute_with_retry(_claim)
