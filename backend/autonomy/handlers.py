"""Event handlers that bridge agent_events to existing sub-flows.

Each handler maps an event type to execution logic, reusing all existing
sub-flows (DevelopmentFlow, ResearchFlow, CodeReviewFlow) and the
``build_crew`` / ``dispatch_message`` infrastructure.

Import safety: all imports from backend.flows.* and backend.agents.* are
LAZY (inside method bodies) to avoid the circular import chain.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from backend.autonomy.events import update_event_status

logger = logging.getLogger(__name__)


def _parse_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Parse payload_json from an event dict."""
    raw = event.get("payload_json", "{}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


class EventHandler(ABC):
    """Base class for event handlers."""

    @abstractmethod
    def execute(self, event: dict[str, Any]) -> None:
        """Execute the work for this event."""
        ...

    def save_progress(self, event: dict[str, Any], progress: dict[str, Any]) -> None:
        """Save progress checkpoint for crash recovery."""
        update_event_status(event["id"], "in_progress", progress=progress)


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
                })
                log_flow_event(
                    project_id, "research_flow_completed",
                    "agent_loop", "task", task_id,
                )
            else:
                from backend.flows.development_flow import DevelopmentFlow
                flow = DevelopmentFlow()
                flow.kickoff(inputs={
                    "project_id": project_id,
                    "task_id": task_id,
                })
                log_flow_event(
                    project_id, "development_flow_completed",
                    "agent_loop", "task", task_id,
                )
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


class ReviewHandler(EventHandler):
    """Handles review_ready events → CodeReviewFlow or research peer review."""

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

        # Atomic claim — prevents duplicate reviews (TOCTOU-safe)
        if not self._claim_review(task_id, agent_id):
            logger.info("ReviewHandler: agent %s lost review claim for task %d", agent_id, task_id)
            return

        task_type = task.get("type", "code")

        if task_type == "research":
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
            "ReviewHandler: starting CodeReviewFlow for task %d (project %d)",
            task_id, project_id,
        )
        try:
            flow = CodeReviewFlow()
            flow.kickoff(inputs={
                "project_id": project_id,
                "task_id": task_id,
                "branch_name": branch_name,
            })
        except Exception:
            self._release_review(task_id, reviewer_id)
            raise

    def _run_research_review(
        self, event: dict[str, Any], project_id: int, task_id: int, task: dict[str, Any],
    ) -> None:
        """Run standalone research peer review (mirrors ResearchFlow.request_peer_review)."""
        from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
        from backend.flows.guardrails import validate_research_review_verdict
        from backend.flows.helpers import (
            build_crew,
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

        task_prompt = rr_tasks.peer_review(
            task_id, task_title,
            project_id=project_id,
            project_name=project_name,
        )
        crew = build_crew(reviewer, task_prompt, guardrail=validate_research_review_verdict)

        try:
            from backend.flows.helpers.reporting import kickoff_with_retry
            result = str(kickoff_with_retry(crew)).strip()
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


class MessageHandler(EventHandler):
    """Handles message_received and user_message_received events."""

    def execute(self, event: dict[str, Any]) -> None:
        from backend.flows.helpers.message_dispatcher import dispatch_message

        payload = _parse_payload(event)
        project_id = event["project_id"]
        agent_id = event["agent_id"]
        from_agent = payload.get("from_agent", "unknown")
        message = payload.get("message", "")
        thread_id = payload.get("thread_id")

        logger.info(
            "MessageHandler: dispatching message to %s from %s (project %d)",
            agent_id, from_agent, project_id,
        )
        dispatch_message(project_id, agent_id, from_agent, message, thread_id)


class HealthCheckHandler(EventHandler):
    """Handles stagnation/health events → Team Lead intervention."""

    def execute(self, event: dict[str, Any]) -> None:
        from backend.flows.helpers import log_flow_event
        from backend.flows.helpers.stagnation import get_stuck_tasks

        project_id = event["project_id"]
        agent_id = event["agent_id"]

        logger.info(
            "HealthCheckHandler: running health check (agent=%s, project=%d)",
            agent_id, project_id,
        )

        stuck = get_stuck_tasks(project_id)
        if not stuck:
            logger.info("HealthCheckHandler: no stuck tasks found")
            return

        # Limit intervention to 3 tasks per cycle
        for task in stuck[:3]:
            try:
                from backend.agents.registry import get_agent_by_role
                from backend.flows.helpers import build_crew
                from backend.prompts.team import build_conversation_context
                from backend.prompts.team_lead import tasks as tl_tasks

                team_lead = get_agent_by_role("team_lead", project_id, agent_id=agent_id)
                team_lead.activate_context()

                conv_ctx = build_conversation_context(
                    project_id=project_id,
                    agent_id=agent_id,
                )

                task_prompt = tl_tasks.handle_escalation(
                    task["id"],
                    task.get("title", ""),
                    task.get("branch_name", ""),
                    task.get("assigned_to", ""),
                    project_id=project_id,
                    project_name="",
                    conversation_context=conv_ctx,
                )
                from backend.flows.helpers.reporting import kickoff_with_retry
                kickoff_with_retry(build_crew(team_lead, task_prompt))

                log_flow_event(
                    project_id, "agent_loop_health_intervention",
                    "agent_loop", "task", task["id"],
                )
            except Exception:
                logger.exception(
                    "HealthCheckHandler: intervention failed for task %d", task["id"],
                )


class ProgressEvalHandler(EventHandler):
    """Handles evaluate_progress and all_tasks_done events."""

    def execute(self, event: dict[str, Any]) -> None:
        from backend.flows.helpers import send_agent_message

        payload = _parse_payload(event)
        project_id = event["project_id"]
        event_type = event["event_type"]

        if event_type == "all_tasks_done":
            self._handle_all_tasks_done(project_id)
        elif event_type == "waiting_for_research":
            send_agent_message(
                project_id=project_id,
                from_agent="system",
                to_agent=None,
                to_role="project_lead",
                message=(
                    f"Project {project_id} is waiting for research tasks to complete. "
                    f"Please review the findings once research is done."
                ),
            )
        elif event_type == "stagnation_detected":
            # Dedup: skip if a stagnation message was sent recently (10 min)
            import sqlite3 as _sqlite3
            from backend.autonomy.db import execute_with_retry as _exec

            def _has_recent(conn: _sqlite3.Connection) -> bool:
                row = conn.execute(
                    """SELECT COUNT(*) as cnt FROM chat_messages
                       WHERE project_id = ?
                         AND from_agent = 'system'
                         AND message LIKE '%Stagnation detected%'
                         AND created_at > datetime('now', '-10 minutes')""",
                    (project_id,),
                ).fetchone()
                return (row["cnt"] if row else 0) > 0

            try:
                already_sent = _exec(_has_recent)
            except Exception:
                already_sent = False

            if not already_sent:
                send_agent_message(
                    project_id=project_id,
                    from_agent="system",
                    to_agent=None,
                    to_role="team_lead",
                    message=(
                        f"Stagnation detected for project {project_id}: "
                        f"{payload.get('stuck_tasks', '?')} tasks stuck with no "
                        f"recent completions. Please analyze and unblock."
                    ),
                )

    def _handle_all_tasks_done(self, project_id: int) -> None:
        """Check completion state and act: finalize, wait, or evaluate progress."""
        from backend.flows.helpers import send_agent_message

        try:
            from backend.state.completion import CompletionDetector, CompletionState

            state = CompletionDetector.detect(project_id)

            if state == CompletionState.IDLE_OBJECTIVES_MET:
                send_agent_message(
                    project_id=project_id,
                    from_agent="system",
                    to_agent=None,
                    to_role="project_lead",
                    message=(
                        f"All tasks for project {project_id} are complete "
                        f"and all objectives have been met. "
                        f"Please finalize the project."
                    ),
                )
            elif state == CompletionState.WAITING_FOR_RESEARCH:
                send_agent_message(
                    project_id=project_id,
                    from_agent="system",
                    to_agent=None,
                    to_role="project_lead",
                    message=(
                        f"Project {project_id} is waiting for research tasks to complete."
                    ),
                )
            else:
                # IDLE_OBJECTIVES_PENDING — tasks done but objectives not met.
                # Launch evaluate_progress Crew for the team lead so it actually
                # creates new tickets (not just a chat message it ignores).
                self._run_evaluate_progress(project_id)

        except ImportError:
            # CompletionDetector may not exist yet — fall back to evaluate
            self._run_evaluate_progress(project_id)

    def _run_evaluate_progress(self, project_id: int) -> None:
        """Spin up a Crew task for the team lead to evaluate progress and create tickets."""
        from backend.agents.registry import get_agent_by_role
        from backend.flows.helpers import log_flow_event
        from backend.flows.helpers.db_helpers import get_project_progress_summary
        from backend.flows.helpers.reporting import build_crew, kickoff_with_retry
        from backend.prompts.team_lead import tasks as tl_tasks

        try:
            agent = get_agent_by_role("team_lead", project_id)
            agent.activate_context()

            # Build progress summary
            progress = get_project_progress_summary(project_id)
            if not progress:
                progress = "No progress summary available."

            # Get project name
            from backend.flows.helpers import get_project_name
            project_name = get_project_name(project_id)

            # Build the evaluate_progress prompt
            description, expected_output = tl_tasks.evaluate_progress(
                project_id=project_id,
                project_name=project_name,
                progress_summary=progress,
            )

            crew = build_crew(agent, (description, expected_output))
            result = kickoff_with_retry(crew)
            result_str = str(result).strip()

            logger.info(
                "evaluate_progress completed for project %d: %s",
                project_id, result_str[:200],
            )
            log_flow_event(
                project_id, "evaluate_progress_completed", "autonomy",
                "project", project_id,
                {"result_preview": result_str[:300]},
            )

            # Parse TL decision and act on it
            upper = result_str.upper()
            if upper.startswith("BRAINSTORM_NEEDED"):
                from backend.communication.brainstorm_coordinator import BrainstormingCoordinator
                coordinator = BrainstormingCoordinator()
                coordinator.start_session(project_id, topic=result_str[:500])
                log_flow_event(
                    project_id, "brainstorm_triggered_by_eval", "autonomy",
                    "project", project_id,
                )
            elif upper.startswith("PROJECT_COMPLETE"):
                from backend.flows.helpers import send_agent_message
                send_agent_message(
                    project_id=project_id,
                    from_agent="system",
                    to_agent=None,
                    to_role="project_lead",
                    message=(
                        "Team Lead has evaluated the project as complete. "
                        "Please verify and finalize."
                    ),
                )
            # NEW_TICKETS / default: TL already created tickets via tools
            # during the Crew task — no additional action needed.

        except Exception:
            logger.exception(
                "Failed to run evaluate_progress for project %d", project_id,
            )


class ReworkHandler(EventHandler):
    """Handles task_rejected events → rework by the assigned developer/researcher."""

    def execute(self, event: dict[str, Any]) -> None:
        from backend.agents.registry import get_agent_by_role
        from backend.flows.helpers import (
            build_crew,
            get_project_name,
            get_task_by_id,
            increment_task_retry,
            log_flow_event,
            update_task_status,
        )

        payload = _parse_payload(event)
        task_id = payload.get("task_id")
        project_id = event["project_id"]
        agent_id = event["agent_id"]

        if task_id is None:
            logger.warning("ReworkHandler: no task_id in payload for event %d", event["id"])
            return

        task = get_task_by_id(task_id)
        if not task:
            logger.warning("ReworkHandler: task %d not found", task_id)
            return

        task_type = task.get("type", "code")
        task_title = task.get("title", "")
        task_description = task.get("description", "")
        branch_name = task.get("branch_name", "")
        project_name = get_project_name(project_id)

        # Get latest reviewer feedback from task_comments
        feedback = self._get_latest_feedback(task_id)

        # Increment rejection counter
        rejection_count = increment_task_retry(task_id)

        # Transition rejected → in_progress
        try:
            update_task_status(task_id, "in_progress")
        except ValueError:
            logger.warning(
                "ReworkHandler: could not transition task %d to in_progress (current status: %s)",
                task_id, task.get("status"),
            )
            return

        logger.info(
            "ReworkHandler: starting %s rework for task %d (agent=%s, attempt=%d)",
            task_type, task_id, agent_id, rejection_count,
        )

        try:
            agent = get_agent_by_role(
                self._role_for_type(task_type), project_id, agent_id=agent_id,
            )
            agent.activate_context(task_id=task_id)
            run_id = agent.create_agent_run(task_id)

            task_prompt = self._build_rework_prompt(
                task_type, task_id, task_title, task_description,
                feedback, branch_name, rejection_count,
                project_id, project_name,
            )
            crew = build_crew(agent, task_prompt)
            from backend.flows.helpers.reporting import kickoff_with_retry
            result = str(kickoff_with_retry(crew)).strip()

            agent.complete_agent_run(run_id, status="completed", output_summary=result[:500])
            log_flow_event(
                project_id, f"rework_{task_type}_completed",
                "agent_loop", "task", task_id,
            )
        except Exception as exc:
            logger.exception(
                "ReworkHandler: rework failed for task %d (agent=%s)", task_id, agent_id,
            )
            log_flow_event(
                project_id, "rework_failed",
                "agent_loop", "task", task_id, {"error": str(exc)[:300]},
            )
            raise

    @staticmethod
    def _role_for_type(task_type: str) -> str:
        if task_type == "research":
            return "researcher"
        return "developer"

    @staticmethod
    def _build_rework_prompt(
        task_type: str,
        task_id: int,
        task_title: str,
        task_description: str,
        feedback: str,
        branch_name: str,
        rejection_count: int,
        project_id: int,
        project_name: str,
    ) -> tuple[str, str]:
        if task_type == "research":
            from backend.prompts.researcher import tasks as res_tasks
            return res_tasks.revise_research(
                task_id,
                reviewer_feedback=feedback,
                project_id=project_id,
                project_name=project_name,
            )
        else:
            from backend.prompts.developer import tasks as dev_tasks
            return dev_tasks.rework_code(
                task_id,
                rejection_count=rejection_count,
                latest_feedback=feedback,
                branch_name=branch_name,
                project_id=project_id,
                project_name=project_name,
            )

    @staticmethod
    def _get_latest_feedback(task_id: int) -> str:
        """Get the most recent change_request comment for a task."""
        from backend.autonomy.db import execute_with_retry
        import sqlite3

        def _query(conn: sqlite3.Connection) -> str:
            row = conn.execute(
                """SELECT content FROM task_comments
                   WHERE task_id = ? AND comment_type = 'change_request'
                   ORDER BY id DESC LIMIT 1""",
                (task_id,),
            ).fetchone()
            return row["content"] if row else ""

        return execute_with_retry(_query)


# -- Handler registry -------------------------------------------------------

_HANDLER_MAP: dict[str, type[EventHandler]] = {
    "task_available": TaskFlowHandler,
    "task_resume": TaskFlowHandler,
    "review_ready": ReviewHandler,
    "task_rejected": ReworkHandler,
    "message_received": MessageHandler,
    "user_message_received": MessageHandler,
    "health_check": HealthCheckHandler,
    "stagnation_detected": ProgressEvalHandler,
    "all_tasks_done": ProgressEvalHandler,
    "waiting_for_research": ProgressEvalHandler,
    "evaluate_progress": ProgressEvalHandler,
}


def build_handler_map() -> dict[str, EventHandler]:
    """Return a dict of event_type -> handler instance."""
    return {etype: cls() for etype, cls in _HANDLER_MAP.items()}
