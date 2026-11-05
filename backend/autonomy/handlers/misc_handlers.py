"""Miscellaneous event handlers: messages, health checks, progress, rework."""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.base import AgentKilledError as _AgentKilledError

from .base import EventHandler, _parse_payload

logger = logging.getLogger(__name__)


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
    """Handles stagnation/health events -> Team Lead intervention."""

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
                from backend.engine import get_engine
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
                get_engine().execute(team_lead, task_prompt)

                log_flow_event(
                    project_id, "agent_loop_health_intervention",
                    "agent_loop", "task", task["id"],
                )
            except _AgentKilledError:
                logger.info(
                    "HealthCheckHandler: intervention for task %d interrupted (agent killed)",
                    task["id"],
                )
                raise
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
            # First: check if the stuck task's agent is actually dead.
            # If so, recover the task immediately instead of just sending messages.
            task_id = payload.get("task_id")
            if task_id:
                try:
                    self._try_recover_dead_task(project_id, task_id)
                except Exception:
                    logger.debug(
                        "ProgressEvalHandler: dead agent recovery failed for task %d",
                        task_id, exc_info=True,
                    )

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

    @staticmethod
    def _try_recover_dead_task(project_id: int, task_id: int) -> None:
        """If the task's assigned agent is dead, recover it to pending."""
        import sqlite3 as _sqlite3
        from backend.autonomy.db import execute_with_retry as _exec

        def _get_task(conn: _sqlite3.Connection) -> dict | None:
            row = conn.execute(
                "SELECT id, status, assigned_to FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

        task = _exec(_get_task)
        if not task or task["status"] != "in_progress" or not task["assigned_to"]:
            return

        from backend.autonomy.liveness import is_agent_dead, recover_dead_agent_task

        if is_agent_dead(task["assigned_to"]):
            recovered = recover_dead_agent_task(
                task_id, task["assigned_to"], reason="stagnation_dead_agent",
            )
            if recovered:
                logger.info(
                    "ProgressEvalHandler: recovered task %d from dead agent %s",
                    task_id, task["assigned_to"],
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
                # IDLE_OBJECTIVES_PENDING -- tasks done but objectives not met.
                # Launch evaluate_progress Crew for the team lead so it actually
                # creates new tickets (not just a chat message it ignores).
                self._run_evaluate_progress(project_id)

        except ImportError:
            # CompletionDetector may not exist yet -- fall back to evaluate
            self._run_evaluate_progress(project_id)

    def _run_evaluate_progress(self, project_id: int) -> None:
        """Spin up a Crew task for the team lead to evaluate progress and create tickets."""
        from backend.agents.registry import get_agent_by_role
        from backend.flows.helpers import log_flow_event
        from backend.flows.helpers.db_helpers import get_project_progress_summary
        from backend.engine import get_engine
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

            result_str = get_engine().execute(agent, (description, expected_output)).strip()

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
            # during the Crew task -- no additional action needed.

        except _AgentKilledError:
            logger.info("evaluate_progress interrupted for project %d (agent killed)", project_id)
            raise
        except Exception:
            logger.exception(
                "Failed to run evaluate_progress for project %d", project_id,
            )


class ReworkHandler(EventHandler):
    """Handles task_rejected events -> rework by the assigned developer/researcher."""

    def execute(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Return an owner hint for migrated/native work before any legacy claim or inference."""
        from backend.agents.registry import get_agent_by_role
        from backend.engine import get_engine
        from backend.flows.helpers import (
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

        from backend.runtime.legacy_handoff import legacy_event_handoff

        handoff = legacy_event_handoff(project_id, task_id)
        if handoff is not None:
            logger.info("Legacy event %s is an owner handoff for task %s; no work authorized", event["id"], task_id)
            return handoff

        task = get_task_by_id(task_id)
        if not task:
            logger.warning("ReworkHandler: task %d not found", task_id)
            return

        # Guard: only rework tasks that are still in 'rejected' status.
        # Stale events from earlier rejection cascades may arrive after
        # the developer has already reworked and moved the task forward.
        current_status = task.get("status", "")
        if current_status != "rejected":
            logger.info(
                "ReworkHandler: skipping stale task_rejected event %d for task %d "
                "(current status=%s, expected rejected)",
                event["id"], task_id, current_status,
            )
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

        # Transition rejected -> in_progress
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
            result = get_engine().execute(agent, task_prompt).strip()

            agent.complete_agent_run(run_id, status="completed", output_summary=result[:500])
            log_flow_event(
                project_id, f"rework_{task_type}_completed",
                "agent_loop", "task", task_id,
            )
        except _AgentKilledError:
            logger.info("ReworkHandler: rework for task %d interrupted (agent killed)", task_id)
            agent.complete_agent_run(run_id, status="interrupted")
            raise
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
        if task_type in ("research", "investigation"):
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
        elif task_type == "investigation":
            from backend.prompts.researcher import tasks as res_tasks
            return res_tasks.revise_investigation(
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
