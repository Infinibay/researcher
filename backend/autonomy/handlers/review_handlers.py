"""Review event handlers."""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.base import AgentKilledError as _AgentKilledError

from .base import EventHandler, _parse_payload

logger = logging.getLogger(__name__)


class ReviewHandler(EventHandler):
    """Handles review_ready events -> CodeReviewFlow or research peer review."""

    def execute(self, event: dict[str, Any]) -> None:
        from backend.flows.helpers import get_task_by_id, has_active_review_run

        payload = _parse_payload(event)
        task_id = payload.get("task_id")
        project_id = event["project_id"]
        agent_id = event["agent_id"]

        if task_id is None:
            logger.warning("ReviewHandler: no task_id in payload for event %d", event["id"])
            return

        if has_active_review_run(task_id):
            logger.info("ReviewHandler: review already active for task %d, skipping", task_id)
            return

        # Skip if the task was already reviewed recently (prevents duplicate
        # reviews when a flow like ResearchFlow manages its own review cycle).
        if self._has_recent_completed_review(task_id):
            logger.info("ReviewHandler: task %d was recently reviewed, skipping", task_id)
            return

        task = get_task_by_id(task_id)
        if not task:
            logger.warning("ReviewHandler: task %d not found", task_id)
            return

        # Skip if the task is no longer in review_ready (another handler or
        # flow may have already advanced it).
        if task.get("status") != "review_ready":
            logger.info(
                "ReviewHandler: task %d status is '%s' (not review_ready), skipping",
                task_id, task.get("status"),
            )
            return

        # Atomic claim -- prevents duplicate reviews (TOCTOU-safe)
        if not self._claim_review(task_id, agent_id):
            logger.info("ReviewHandler: agent %s lost review claim for task %d", agent_id, task_id)
            return

        task_type = task.get("type", "code")

        if task_type in ("research", "investigation"):
            self._run_research_review(event, project_id, task_id, task)
        else:
            self._run_code_review(project_id, task_id, task)

    @staticmethod
    def _claim_review(task_id: int, agent_id: str) -> bool:
        """Atomically claim a task for review. Returns True if this agent won."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _claim(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """UPDATE tasks SET reviewer = ?
                   WHERE id = ? AND status = 'review_ready'
                   AND (reviewer IS NULL OR reviewer = '' OR reviewer = ?)""",
                (agent_id, task_id, agent_id),
            )
            conn.commit()
            return cursor.rowcount > 0

        return execute_with_retry(_claim)

    @staticmethod
    def _release_review(task_id: int, agent_id: str) -> None:
        """Release the review claim if the reviewer fails or skips."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _release(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE tasks SET reviewer = NULL WHERE id = ? AND reviewer = ?",
                (task_id, agent_id),
            )
            conn.commit()

        try:
            execute_with_retry(_release)
        except Exception:
            pass

    @staticmethod
    def _has_recent_completed_review(task_id: int, window_minutes: int = 5) -> bool:
        """Check if a review was completed for this task within the time window."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _query(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM agent_runs
                   WHERE task_id = ?
                     AND role IN ('code_reviewer', 'research_reviewer')
                     AND status = 'completed'
                     AND completed_at >= datetime('now', ? || ' minutes')""",
                (task_id, f"-{window_minutes}"),
            ).fetchone()
            return row["cnt"] > 0 if row else False

        try:
            return execute_with_retry(_query)
        except Exception:
            return False

    def _run_code_review(self, project_id: int, task_id: int, task: dict[str, Any]) -> None:
        """Dispatch to CodeReviewFlow for non-research tasks."""
        from backend.flows.code_review_flow import CodeReviewFlow

        branch_name = task.get("branch_name") or ""
        reviewer_id = task.get("reviewer", "")

        logger.info(
            "ReviewHandler: starting CodeReviewFlow for task %d (project %d, reviewer=%s)",
            task_id, project_id, reviewer_id,
        )
        try:
            flow = CodeReviewFlow()
            flow.kickoff(inputs={
                "project_id": project_id,
                "task_id": task_id,
                "branch_name": branch_name,
                "reviewer_id": reviewer_id,
            })
        except Exception:
            self._release_review(task_id, reviewer_id)
            raise

    def _run_research_review(
        self, event: dict[str, Any], project_id: int, task_id: int, task: dict[str, Any],
    ) -> None:
        """Run standalone research peer review (mirrors ResearchFlow.request_peer_review)."""
        from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
        from backend.engine import get_engine
        from backend.flows.guardrails import validate_research_review_verdict
        from backend.flows.helpers import (
            get_project_name,
            log_flow_event,
            parse_review_result,
            update_task_status,
        )
        from backend.flows.helpers.db_helpers import update_task_status_safe
        from backend.knowledge import KnowledgeService
        from backend.prompts.research_reviewer import tasks as rr_tasks

        task_title = task.get("title", "")
        project_name = get_project_name(project_id)

        logger.info(
            "ReviewHandler: starting research peer review for task %d (project %d)",
            task_id, project_id,
        )

        try:
            knowledge_service = KnowledgeService()
        except Exception:
            knowledge_service = None

        agent_id = event.get("agent_id")
        try:
            if agent_id:
                reviewer = get_agent_by_role(
                    "research_reviewer", project_id,
                    agent_id=agent_id,
                    knowledge_service=knowledge_service,
                )
            else:
                reviewer = get_available_agent_by_role(
                    "research_reviewer", project_id,
                    knowledge_service=knowledge_service,
                )
        except Exception:
            logger.exception(
                "ReviewHandler: could not get research_reviewer for project %d", project_id,
            )
            self._release_review(task_id, agent_id or "")
            return

        reviewer.activate_context(task_id=task_id)
        run_id = reviewer.create_agent_run(task_id)

        task_type = task.get("type", "research")
        if task_type == "investigation":
            task_prompt = rr_tasks.investigation_review(
                task_id, task_title,
                project_id=project_id,
                project_name=project_name,
            )
        else:
            task_prompt = rr_tasks.peer_review(
                task_id, task_title,
                project_id=project_id,
                project_name=project_name,
            )
        try:
            result = get_engine().execute(
                reviewer, task_prompt,
                guardrail=validate_research_review_verdict,
            ).strip()
        except _AgentKilledError:
            logger.info("ReviewHandler: review for task %d interrupted (agent killed)", task_id)
            reviewer.complete_agent_run(run_id, status="interrupted")
            self._release_review(task_id, agent_id or "")
            raise
        except Exception as exc:
            logger.exception(
                "ReviewHandler: research peer review failed for task %d", task_id,
            )
            reviewer.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                project_id, "research_review_failed",
                "agent_loop", "task", task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(task_id, "failed")
            self._release_review(task_id, agent_id or "")
            raise

        reviewer.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        if parse_review_result(result, approve_keyword="VALIDATED") == "approved":
            # Ensure task goes through review_ready before done (the reviewer
            # agent may have already moved it via ApproveTaskTool, so use _safe)
            update_task_status_safe(task_id, "review_ready")
            update_task_status_safe(task_id, "done")
            log_flow_event(
                project_id, "research_review_approved",
                "agent_loop", "task", task_id,
            )
        else:
            update_task_status_safe(task_id, "review_ready")
            update_task_status_safe(task_id, "rejected")
            log_flow_event(
                project_id, "research_review_rejected",
                "agent_loop", "task", task_id,
            )
