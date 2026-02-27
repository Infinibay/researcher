"""MainProjectFlow — root orchestrator for the PABADA project lifecycle.

Manages: project creation → requirements → planning → approval → execution → completion.
Delegates work to DevelopmentFlow, ResearchFlow, and BrainstormingFlow.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method named "X" completes, OR when a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes the next trigger
- Return values from non-router methods are DATA, not event triggers
- Router chains work via the _execute_listeners while loop (router → router)
- Router results trigger non-router listeners via all_triggers dispatch
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from crewai.flow.flow import Flow, listen, or_, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, initialize_project_team
from backend.config.settings import settings
from backend.flows.guardrails import (
    validate_plan_output,
    validate_requirements_output,
)
from backend.flows.helpers import (
    build_crew,
    classify_approval_response,
    create_project,
    generate_final_report,
    get_completed_task_count,
    get_pending_tasks,
    get_project_progress_summary,
    get_task_count,
    load_project_state,
    log_flow_event,
    notify_team_lead,
    send_agent_message,
    update_project_status,
)
from backend.flows.snapshot_service import save_snapshot
from backend.flows.state_models import ProjectState, ProjectStatus, TaskType
from backend.prompts.project_lead import tasks as pl_tasks
from backend.prompts.team import build_conversation_context
from backend.prompts.team_lead import tasks as tl_tasks

logger = logging.getLogger(__name__)


@persist()
class MainProjectFlow(Flow[ProjectState]):
    """Orchestrates the complete project lifecycle using event-driven flows."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def initialize_project(self):
        """Load or create a project and store state for routing."""
        logger.info("MainProjectFlow: initialize_project (project_id=%d)", self.state.project_id)

        if self.state.project_id > 0:
            project = load_project_state(self.state.project_id)
            if project is None:
                logger.error("Project %d not found in DB", self.state.project_id)
                self.state.status = ProjectStatus.CANCELLED
                return

            initialize_project_team(self.state.project_id)
            self.state.project_name = project.get("name", "")
            if not self.state.requirements and project.get("description"):
                self.state.requirements = project["description"]
            db_status = project.get("status", "new")

            if db_status in ("executing", "paused"):
                has_work = (
                    project.get("total_tasks", 0) > 0
                    or project.get("total_epics", 0) > 0
                )
                if has_work:
                    self.state.status = ProjectStatus.EXECUTING
                    # Ensure DB reflects executing so agent loops can process events
                    if db_status != "executing":
                        update_project_status(self.state.project_id, "executing")
                else:
                    # Paused/executing but no work created yet → restart planning
                    logger.info(
                        "MainProjectFlow: project %d is %s but has no tasks/epics — "
                        "restarting from planning phase",
                        self.state.project_id, db_status,
                    )
                    self.state.status = ProjectStatus.NEW
                    update_project_status(self.state.project_id, "new")
                return

            if db_status == "completed":
                self.state.status = ProjectStatus.COMPLETED
                return

            self.state.status = ProjectStatus(db_status)
        else:
            if self.state.project_name:
                self.state.project_id = create_project(self.state.project_name)
            else:
                self.state.project_id = create_project("Untitled Project")

            initialize_project_team(self.state.project_id)
            self.state.status = ProjectStatus.NEW
            log_flow_event(
                self.state.project_id, "project_created", "main_project_flow",
                "project", self.state.project_id,
            )

    @router("initialize_project")
    def route_initialization(self):
        """Route based on project status determined by initialize_project."""
        logger.info(
            "MainProjectFlow: route_initialization (status=%s)", self.state.status,
        )

        if self.state.status == ProjectStatus.CANCELLED:
            return "error"

        if self.state.status == ProjectStatus.EXECUTING:
            log_flow_event(
                self.state.project_id, "flow_resumed", "main_project_flow",
                "project", self.state.project_id,
            )
            return "resume_execution"

        if self.state.status == ProjectStatus.COMPLETED:
            return "already_complete"

        # Step-aware resume: if we have a saved current_step from a snapshot,
        # jump directly to the interrupted step instead of restarting.
        if (
            self.state.status == ProjectStatus.PLANNING
            and self.state.current_step
        ):
            step = self.state.current_step
            logger.info(
                "MainProjectFlow: resuming PLANNING from step '%s'", step,
            )
            step_to_event = {
                "consult_project_lead": "start_planning",
                "create_plan": "consult_project_lead",
                "plan_approval_router": "resume_plan_approval",
                "setup_repository": "approved",
                "create_structure": "setup_repository",
                "check_and_launch_tasks": "resume_execution",
            }
            resume_event = step_to_event.get(step)
            if resume_event:
                log_flow_event(
                    self.state.project_id, "flow_resumed", "main_project_flow",
                    "project", self.state.project_id,
                    {"resumed_from_step": step},
                )
                return resume_event

        # NEW or PLANNING → start planning
        return "start_planning"

    # ── Requirements gathering ────────────────────────────────────────────

    @listen("start_planning")
    def consult_project_lead(self):
        """Project Lead gathers and clarifies requirements with the user."""
        self.state.current_step = "consult_project_lead"
        self.state.status = ProjectStatus.PLANNING
        update_project_status(self.state.project_id, "planning")
        save_snapshot(self.state.project_id, "main_project_flow", "consult_project_lead", self.state)
        logger.info("MainProjectFlow: consult_project_lead")
        self.state.requirements_attempts += 1

        # Cap requirements gathering iterations
        if self.state.requirements_attempts > self.state.max_requirements_attempts:
            logger.warning(
                "MainProjectFlow: requirements attempts exhausted (%d/%d) for project %d — "
                "proceeding with current requirements",
                self.state.requirements_attempts,
                self.state.max_requirements_attempts,
                self.state.project_id,
            )
            # Append unresolved feedback to requirements and proceed
            if self.state.feedback:
                self.state.requirements += (
                    f"\n\n[UNRESOLVED FEEDBACK — auto-proceeding after "
                    f"{self.state.max_requirements_attempts} attempts]: "
                    f"{self.state.feedback}"
                )
            self.state.user_approved = True
            log_flow_event(
                self.state.project_id, "requirements_cap_reached",
                "main_project_flow", "project", self.state.project_id,
                {"attempts": self.state.requirements_attempts},
            )
            return

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        existing_reqs = self.state.requirements or "No requirements provided yet."
        feedback_context = ""
        if self.state.feedback:
            feedback_context = (
                f"\n\nThe user previously rejected the plan with this feedback: "
                f"{self.state.feedback}\n"
                "Please adjust the requirements accordingly."
            )

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=project_lead.agent_id,
        )
        task_prompt = pl_tasks.gather_requirements(
            self.state.project_name, self.state.project_id,
            existing_reqs, feedback_context,
            conversation_context=conv_ctx,
        )
        from backend.tools import get_tools_for_task_type
        result = build_crew(
            project_lead, task_prompt,
            guardrail=validate_requirements_output,
            task_tools=get_tools_for_task_type("requirements"),
        ).kickoff()
        self.state.requirements = str(result)

        log_flow_event(
            self.state.project_id, "requirements_gathered", "main_project_flow",
            "project", self.state.project_id,
            {"requirements_length": len(self.state.requirements)},
        )

    # ── Plan creation ─────────────────────────────────────────────────────

    @listen("consult_project_lead")
    def create_plan(self):
        """Team Lead creates a detailed plan with epics, milestones, and tasks."""
        self.state.current_step = "create_plan"
        save_snapshot(self.state.project_id, "main_project_flow", "create_plan", self.state)
        logger.info("MainProjectFlow: create_plan")

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=team_lead.agent_id,
        )
        task_prompt = tl_tasks.create_plan(
            self.state.project_name, self.state.project_id,
            self.state.requirements,
            conversation_context=conv_ctx,
            planning_iteration=self.state.planning_iteration,
        )
        from backend.tools import get_tools_for_task_type
        result = build_crew(
            team_lead, task_prompt,
            guardrail=validate_plan_output,
            task_tools=get_tools_for_task_type("plan"),
        ).kickoff()
        self.state.plan = str(result)

        log_flow_event(
            self.state.project_id, "plan_created", "main_project_flow",
            "project", self.state.project_id,
        )

    # ── Plan approval ─────────────────────────────────────────────────────

    @router(or_("create_plan", "resume_plan_approval"))
    def plan_approval_router(self):
        """Project Lead presents the plan to the user for approval."""
        self.state.current_step = "plan_approval_router"
        save_snapshot(self.state.project_id, "main_project_flow", "plan_approval_router", self.state)
        logger.info("MainProjectFlow: plan_approval_router")

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=project_lead.agent_id,
        )
        task_prompt = pl_tasks.present_plan_for_approval(
            self.state.plan,
            project_name=self.state.project_name,
            project_id=self.state.project_id,
            requirements=self.state.requirements,
            conversation_context=conv_ctx,
        )
        result = str(build_crew(project_lead, task_prompt).kickoff()).strip()

        if classify_approval_response(result) == "approved":
            self.state.user_approved = True
            log_flow_event(
                self.state.project_id, "plan_approved", "main_project_flow",
                "project", self.state.project_id,
                {"project_name": self.state.project_name},
            )
            return "approved"
        else:
            feedback = result
            if ":" in result:
                feedback = result.split(":", 1)[1].strip()
            self.state.feedback = feedback
            self.state.user_approved = False
            log_flow_event(
                self.state.project_id, "plan_rejected", "main_project_flow",
                "project", self.state.project_id,
                {"feedback": feedback},
            )
            return "rejected"

    @router("rejected")
    def handle_rejection(self):
        """Clear plan and loop back to requirements gathering with feedback.

        Returns "start_planning" → consult_project_lead.
        Returns "approved" if max_requirements_attempts reached (force-proceed).
        """
        logger.info("MainProjectFlow: handle_rejection (feedback=%s)", self.state.feedback)

        if self.state.requirements_attempts >= self.state.max_requirements_attempts:
            logger.warning(
                "MainProjectFlow: forcing approval after %d requirements attempts",
                self.state.requirements_attempts,
            )
            # Incorporate feedback into requirements and force proceed
            if self.state.feedback:
                self.state.requirements += (
                    f"\n\n[FINAL FEEDBACK — incorporated after "
                    f"{self.state.requirements_attempts} attempts]: "
                    f"{self.state.feedback}"
                )
            self.state.user_approved = True
            log_flow_event(
                self.state.project_id, "rejection_cap_reached",
                "main_project_flow", "project", self.state.project_id,
                {"attempts": self.state.requirements_attempts},
            )
            return "approved"

        self.state.plan = ""
        return "start_planning"

    # ── Repository setup ─────────────────────────────────────────────────

    @listen("approved")
    def setup_repository(self):
        """Create a git repository for the project after plan approval.

        This is a system-level step (no LLM call needed). The repo name is
        derived from the project name by slugifying it.
        """
        self.state.current_step = "setup_repository"
        save_snapshot(self.state.project_id, "main_project_flow", "setup_repository", self.state)

        import re

        from backend.config.settings import settings
        from backend.git.repository_manager import RepositoryManager

        logger.info("MainProjectFlow: setup_repository for project %d", self.state.project_id)

        # Slugify project name → repo name
        slug = self.state.project_name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:40]
        if len(slug) < 2:
            slug = f"project-{self.state.project_id}"
        self.state.repo_name = slug

        local_path = (
            f"{settings.WORKSPACE_BASE_DIR}/projects/"
            f"{self.state.project_id}/{slug}"
        )

        repo_manager = RepositoryManager()
        try:
            repo = repo_manager.init_repo(
                project_id=self.state.project_id,
                name=slug,
                local_path=local_path,
            )
            log_flow_event(
                self.state.project_id, "repo_created", "project_lead",
                "project", self.state.project_id,
                {"repo_name": slug, "local_path": local_path,
                 "remote_url": repo.get("remote_url", "")},
            )
            logger.info(
                "MainProjectFlow: repository '%s' created at %s",
                slug, local_path,
            )
        except Exception:
            logger.exception(
                "MainProjectFlow: failed to create repository for project %d",
                self.state.project_id,
            )
            # Non-fatal — project can still proceed without a repo
            log_flow_event(
                self.state.project_id, "repo_creation_failed", "main_project_flow",
                "project", self.state.project_id,
                {"repo_name": slug, "error": "see logs"},
            )

    # ── Structure creation ────────────────────────────────────────────────

    @listen("setup_repository")
    def create_structure(self):
        """Delegate to TicketCreationFlow for iterative ticket creation.

        Launches TicketCreationFlow in a background thread and waits only
        for the first ticket to be created before returning, so
        _launch_pending_tasks can start developers while tickets are still
        being created.
        """
        self.state.current_step = "create_structure"
        save_snapshot(self.state.project_id, "main_project_flow", "create_structure", self.state)
        logger.info("MainProjectFlow: create_structure (delegating to TicketCreationFlow)")

        from backend.flows.event_listeners import event_bus
        from backend.flows.ticket_creation_flow import TicketCreationFlow

        first_ticket_event = threading.Event()
        no_tickets_event = threading.Event()

        def _on_first_ticket(event):
            if event.project_id == self.state.project_id:
                first_ticket_event.set()

        def _on_no_tickets(event):
            if event.project_id == self.state.project_id:
                no_tickets_event.set()

        event_bus.subscribe("task_available", _on_first_ticket)
        event_bus.subscribe("no_tickets_in_plan", _on_no_tickets)

        flow = TicketCreationFlow()
        ticket_thread = threading.Thread(
            target=flow.kickoff,
            kwargs={"inputs": {
                "project_id": self.state.project_id,
                "project_name": self.state.project_name,
                "plan": self.state.plan,
            }},
            name=f"TicketCreation-p{self.state.project_id}",
            daemon=True,
        )
        ticket_thread.start()

        try:
            if not first_ticket_event.wait(timeout=600):
                if no_tickets_event.is_set():
                    logger.warning(
                        "MainProjectFlow: TicketCreationFlow found 0 tasks in plan (project %d)",
                        self.state.project_id,
                    )
                else:
                    logger.warning(
                        "MainProjectFlow: timed out waiting for first ticket (project %d)",
                        self.state.project_id,
                    )
        finally:
            event_bus.unsubscribe("task_available", _on_first_ticket)
            event_bus.unsubscribe("no_tickets_in_plan", _on_no_tickets)

        self.state.status = ProjectStatus.EXECUTING
        update_project_status(self.state.project_id, "executing")

        log_flow_event(
            self.state.project_id, "structure_created", "main_project_flow",
            "project", self.state.project_id,
            {"project_name": self.state.project_name},
        )

    # ── Task execution loop ───────────────────────────────────────────────

    @router(or_(
        "create_structure",
        "resume_execution",
        "check_pending_after_task",
        "after_brainstorm",
        "handle_stagnation",
        "create_additional_tickets",
    ))
    def check_and_launch_tasks(self):
        """Check for pending tasks and launch sub-flows.

        This router is triggered by multiple sources:
        - create_structure: after project structure is created
        - resume_execution: when resuming a paused project
        - check_pending_after_task: after a task completes (cycle)
        - after_brainstorm: after brainstorming creates new tasks
        - handle_stagnation: after stagnation intervention

        When AUTONOMY_ENABLED, delegates to a passive wait while agents
        autonomously pick up work. Otherwise falls back to centralized dispatch.
        """
        if settings.AUTONOMY_ENABLED:
            return self._wait_for_autonomous_completion()
        return self._launch_pending_tasks()

    @listen("task_completed")
    def check_pending_after_task(self):
        """Handle task completion — update counters and trigger re-check.

        Triggers "check_pending_after_task" → check_and_launch_tasks via or_().
        """
        self.state.completed_tasks = get_completed_task_count(self.state.project_id)
        self.state.brainstorm_attempts = 0
        self.state.evaluate_progress_attempts = 0

    def _wait_for_autonomous_completion(self) -> str:
        """Wait passively while agents autonomously pick up work.

        Agents driven by AutonomyScheduler heartbeats observe DB state, claim
        tasks, and launch sub-flows.  This method simply waits for either
        all_tasks_done or task_available events, rechecking each time.
        """
        self.state.current_step = "autonomous_execution"
        save_snapshot(
            self.state.project_id, "main_project_flow",
            "autonomous_execution", self.state,
        )

        from backend.flows.event_listeners import event_bus

        # Reset tasks stuck in in_progress from a previous crash
        self._reset_stale_in_progress_tasks()

        pending = get_pending_tasks(self.state.project_id)
        if not pending:
            # No pending tasks at all — might be done
            logger.info("MainProjectFlow: no pending tasks, checking completion")
            return "no_pending_tasks"

        # Ensure agent_events exist for all pending tasks so agent loops
        # can pick them up.  After a restart, ephemeral EventBus events are
        # lost and the DB may have zero pending agent_events.
        self._ensure_task_events(pending)

        log_flow_event(
            self.state.project_id, "autonomous_execution_started",
            "main_project_flow", "project", self.state.project_id,
            {"pending_count": len(pending)},
        )

        completion_event = threading.Event()

        def _on_all_done(event):
            if event.project_id == self.state.project_id:
                completion_event.set()

        def _on_task_available(event):
            """New tasks created (e.g. by TicketCreationFlow) — re-check."""
            if event.project_id == self.state.project_id:
                completion_event.set()

        event_bus.subscribe("all_tasks_done", _on_all_done)
        event_bus.subscribe("task_available", _on_task_available)
        try:
            while True:
                completion_event.wait(timeout=3600)  # 1h max between checks
                completion_event.clear()

                # Re-check: are there still pending/running tasks?
                remaining = get_pending_tasks(self.state.project_id)
                running = self._count_running_tasks()
                if not remaining and running == 0:
                    break

                # If only new tasks appeared (task_available), agents will pick
                # them up autonomously — just keep waiting
        finally:
            event_bus.unsubscribe("all_tasks_done", _on_all_done)
            event_bus.unsubscribe("task_available", _on_task_available)

        self.state.completed_tasks = get_completed_task_count(self.state.project_id)
        return "no_pending_tasks"

    def _reset_stale_in_progress_tasks(self) -> None:
        """Reset tasks stuck in in_progress from a previous crash back to pending.

        When the system is killed (Ctrl+C), tasks that were being worked on
        remain in 'in_progress' with no agent actually processing them.
        """
        from backend.tools.base.db import execute_with_retry

        def _reset(conn):
            cursor = conn.execute(
                """UPDATE tasks SET status = 'pending', assigned_to = NULL
                   WHERE project_id = ? AND status = 'in_progress'""",
                (self.state.project_id,),
            )
            conn.commit()
            return cursor.rowcount

        count = execute_with_retry(_reset)
        if count:
            logger.info(
                "MainProjectFlow: reset %d stale in_progress tasks to pending "
                "for project %d",
                count, self.state.project_id,
            )

    def _ensure_task_events(self, pending_tasks: list[dict]) -> None:
        """Create task_available agent_events for pending tasks that lack them.

        After a restart, the persistent agent_events table may be empty even
        though tasks exist in backlog/pending.  This method fills the gap so
        agent loops can discover work.
        """
        from backend.autonomy.events import create_task_event
        from backend.tools.base.db import execute_with_retry

        def _tasks_with_pending_events(conn):
            """Return set of task_ids that already have a pending task_available event."""
            rows = conn.execute(
                """SELECT DISTINCT
                       json_extract(payload_json, '$.task_id') as task_id
                   FROM agent_events
                   WHERE project_id = ? AND event_type = 'task_available'
                     AND status = 'pending'""",
                (self.state.project_id,),
            ).fetchall()
            return {r["task_id"] for r in rows if r["task_id"] is not None}

        existing = execute_with_retry(_tasks_with_pending_events)
        created = 0

        for task in pending_tasks:
            task_id = task["id"]
            if task_id in existing:
                continue

            task_type = task.get("type", "development")
            if task_type == "research":
                target_role = "researcher"
            elif task_type == "review":
                target_role = "code_reviewer"
            else:
                target_role = "developer"

            ids = create_task_event(
                self.state.project_id, task_id, "task_available",
                target_role=target_role,
                source="resume_recovery",
                extra_payload={
                    "task_type": task_type,
                    "task_priority": task.get("priority", 2),
                },
            )
            created += len(ids)

        if created:
            logger.info(
                "MainProjectFlow: created %d task_available agent_events "
                "for project %d on resume",
                created, self.state.project_id,
            )

    def _count_running_tasks(self) -> int:
        """Count tasks currently in_progress or review_ready for this project."""
        from backend.tools.base.db import execute_with_retry

        def _query(conn):
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM tasks
                   WHERE project_id = ?
                     AND status IN ('in_progress', 'review_ready')""",
                (self.state.project_id,),
            ).fetchone()
            return row["cnt"] if row else 0

        return execute_with_retry(_query)

    def _launch_pending_tasks(self) -> str:
        """Launch up to max_concurrent_tasks sub-flows and wait for any to finish.

        Returns "no_pending_tasks" or "task_completed" as routing signals.
        """
        self.state.current_step = "check_and_launch_tasks"
        save_snapshot(self.state.project_id, "main_project_flow", "check_and_launch_tasks", self.state)

        from backend.flows.event_listeners import event_bus

        # Clean running_task_ids — remove any tasks that are already done
        self.state.running_task_ids = [
            tid for tid in self.state.running_task_ids
            if self._is_task_still_running(tid)
        ]

        available_slots = self.state.max_concurrent_tasks - len(self.state.running_task_ids)
        pending = get_pending_tasks(self.state.project_id)
        pending = [t for t in pending if t["id"] not in self.state.running_task_ids]
        self.state.total_tasks = len(pending) + len(self.state.running_task_ids)

        if not pending and not self.state.running_task_ids:
            logger.info("MainProjectFlow: no pending or running tasks")
            return "no_pending_tasks"

        # Launch new tasks up to available slots
        tasks_to_launch = pending[:available_slots]
        completion_event = threading.Event()

        for task_data in tasks_to_launch:
            task_id = task_data["id"]
            task_type = task_data.get("type", "development")
            self.state.running_task_ids.append(task_id)

            logger.info(
                "MainProjectFlow: launching sub-flow for task %d (type=%s, running=%d)",
                task_id, task_type, len(self.state.running_task_ids),
            )

            thread = threading.Thread(
                target=self._run_sub_flow,
                args=(task_id, task_type, completion_event),
                name=f"SubFlow-task{task_id}",
                daemon=True,
            )
            thread.start()

        if not tasks_to_launch and self.state.running_task_ids:
            logger.info(
                "MainProjectFlow: all %d slots occupied, waiting for completion",
                len(self.state.running_task_ids),
            )

        if not self.state.running_task_ids:
            return "no_pending_tasks"

        # Wait for any sub-flow to finish or new ticket to arrive
        def _on_task_done(event):
            if event.project_id == self.state.project_id:
                completion_event.set()

        def _on_task_available(event):
            if event.project_id == self.state.project_id:
                completion_event.set()

        event_bus.subscribe("task_done", _on_task_done)
        event_bus.subscribe("task_available", _on_task_available)
        try:
            completion_event.wait(timeout=3600)
        finally:
            event_bus.unsubscribe("task_done", _on_task_done)
            event_bus.unsubscribe("task_available", _on_task_available)

        # Remove finished tasks from running list
        self.state.running_task_ids = [
            tid for tid in self.state.running_task_ids
            if self._is_task_still_running(tid)
        ]

        return "task_completed"

    def _run_sub_flow(
        self,
        task_id: int,
        task_type: str,
        completion_event: threading.Event,
    ) -> None:
        """Run a sub-flow in a background thread and signal completion."""
        dev_types = {"development", "bug_fix", "test", "integration", "design", "documentation"}

        try:
            if task_type == "research":
                from backend.flows.research_flow import ResearchFlow
                flow = ResearchFlow()
                flow.kickoff(inputs={
                    "project_id": self.state.project_id,
                    "task_id": task_id,
                })
                log_flow_event(
                    self.state.project_id, "research_flow_completed",
                    "main_project_flow", "task", task_id,
                )
            elif task_type in dev_types:
                from backend.flows.development_flow import DevelopmentFlow
                flow = DevelopmentFlow()
                flow.kickoff(inputs={
                    "project_id": self.state.project_id,
                    "task_id": task_id,
                })
                log_flow_event(
                    self.state.project_id, "development_flow_completed",
                    "main_project_flow", "task", task_id,
                )
            else:
                from backend.flows.development_flow import DevelopmentFlow
                flow = DevelopmentFlow()
                flow.kickoff(inputs={
                    "project_id": self.state.project_id,
                    "task_id": task_id,
                })
                log_flow_event(
                    self.state.project_id, "development_flow_completed",
                    "main_project_flow", "task", task_id,
                )
        except Exception:
            logger.exception(
                "MainProjectFlow: sub-flow failed for task %d", task_id,
            )
            log_flow_event(
                self.state.project_id, "sub_flow_failed",
                "main_project_flow", "task", task_id,
            )
        finally:
            completion_event.set()

    @staticmethod
    def _is_task_still_running(task_id: int) -> bool:
        """Check if a task is still in a running state."""
        from backend.flows.helpers import get_task_by_id
        task = get_task_by_id(task_id)
        if task is None:
            return False
        return task.get("status") in ("in_progress", "pending", "review_ready", "backlog")

    # ── Completion check ──────────────────────────────────────────────────

    @router("no_pending_tasks")
    def completion_router(self):
        """Check if project has tasks or needs evaluation.

        Always routes to evaluate_progress so the TL reviews the state
        and decides — including whether to declare the project complete
        or plan more epics.
        """
        if get_task_count(self.state.project_id) == 0:
            logger.warning(
                "completion_router: project %d has 0 tasks — reverting to planning",
                self.state.project_id,
            )
            return "no_structure"
        # Always let the Team Lead evaluate — even if all epics look done,
        # TL decides whether the project objectives are truly met or if
        # more epics are needed.
        return "not_complete"

    @listen("no_structure")
    def handle_no_structure(self):
        """No tasks created — revert to planning."""
        logger.warning(
            "MainProjectFlow: no tasks for project %d — reverting to planning",
            self.state.project_id,
        )
        self.state.plan = ""
        self.state.status = ProjectStatus.PLANNING
        self.state.user_approved = False
        update_project_status(self.state.project_id, "planning")
        log_flow_event(
            self.state.project_id, "no_structure_detected", "main_project_flow",
            "project", self.state.project_id,
        )

    @router("handle_no_structure")
    def route_no_structure(self):
        """Route back to planning after no_structure detection."""
        return "start_planning"

    @router("not_complete")
    def evaluate_progress(self):
        """Team Lead evaluates current project state and decides next steps.

        Instead of jumping directly to brainstorming, the TL first reviews
        completed work (especially research findings) and decides whether to
        create new tickets or trigger brainstorming.
        """
        self.state.evaluate_progress_attempts += 1
        if self.state.evaluate_progress_attempts > self.state.max_evaluate_progress_attempts:
            logger.warning(
                "MainProjectFlow: evaluation attempts exhausted (%d/%d) for project %d",
                self.state.evaluate_progress_attempts,
                self.state.max_evaluate_progress_attempts,
                self.state.project_id,
            )
            return "evaluation_exhausted"

        logger.info(
            "MainProjectFlow: Team Lead evaluating progress (attempt %d/%d)",
            self.state.evaluate_progress_attempts,
            self.state.max_evaluate_progress_attempts,
        )

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        progress_summary = get_project_progress_summary(self.state.project_id)

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=team_lead.agent_id,
        )
        task_prompt = tl_tasks.evaluate_progress(
            self.state.project_id, self.state.project_name,
            progress_summary, self.state.plan,
            conversation_context=conv_ctx,
        )
        result = str(build_crew(team_lead, task_prompt).kickoff()).strip()

        log_flow_event(
            self.state.project_id, "progress_evaluated", "main_project_flow",
            "project", self.state.project_id,
            {"attempt": self.state.evaluate_progress_attempts,
             "decision": result[:100]},
        )

        # Parse TL decision
        self.state.planning_iteration += 1

        if result.upper().startswith("PROJECT_COMPLETE"):
            log_flow_event(
                self.state.project_id, "project_complete_by_tl",
                "main_project_flow", "project", self.state.project_id,
                {"planning_iteration": self.state.planning_iteration},
            )
            return "project_complete"
        elif result.upper().startswith("NEW_TICKETS"):
            self.state.plan = result
            return "create_new_tickets"
        elif result.upper().startswith("BRAINSTORM_NEEDED"):
            return "needs_brainstorming"
        else:
            # Default: TL provided a plan without the prefix — treat as new tickets
            self.state.plan = result
            return "create_new_tickets"

    @listen("create_new_tickets")
    def create_additional_tickets(self):
        """Create new tickets based on Team Lead's evaluation.

        Launches TicketCreationFlow in a background thread and waits only
        for the first ticket before returning, so the task loop can start
        processing new work immediately.
        Triggers "create_additional_tickets" → check_and_launch_tasks via or_().
        """
        logger.info(
            "MainProjectFlow: creating additional tickets based on TL evaluation",
        )

        from backend.flows.event_listeners import event_bus
        from backend.flows.ticket_creation_flow import TicketCreationFlow

        first_ticket_event = threading.Event()

        def _on_first_ticket(event):
            if event.project_id == self.state.project_id:
                first_ticket_event.set()

        event_bus.subscribe("task_available", _on_first_ticket)

        flow = TicketCreationFlow()
        ticket_thread = threading.Thread(
            target=flow.kickoff,
            kwargs={"inputs": {
                "project_id": self.state.project_id,
                "project_name": self.state.project_name,
                "plan": self.state.plan,
            }},
            name=f"TicketCreation-p{self.state.project_id}",
            daemon=True,
        )
        ticket_thread.start()

        try:
            if not first_ticket_event.wait(timeout=600):
                logger.warning(
                    "MainProjectFlow: timed out waiting for first additional ticket (project %d)",
                    self.state.project_id,
                )
        finally:
            event_bus.unsubscribe("task_available", _on_first_ticket)

        # Only reset evaluation counter if new tasks were actually created
        pending = get_pending_tasks(self.state.project_id)
        if pending:
            self.state.evaluate_progress_attempts = 0
            log_flow_event(
                self.state.project_id, "additional_tickets_created",
                "main_project_flow", "project", self.state.project_id,
                {"new_tasks": len(pending)},
            )
        else:
            logger.warning(
                "MainProjectFlow: TicketCreationFlow produced no tasks for project %d",
                self.state.project_id,
            )
            log_flow_event(
                self.state.project_id, "additional_tickets_empty",
                "main_project_flow", "project", self.state.project_id,
            )

    @router("needs_brainstorming")
    def trigger_brainstorming(self):
        """Launch BrainstormingFlow when TL decides brainstorming is needed."""
        from backend.flows.brainstorming_flow import BrainstormingFlow

        self.state.brainstorm_attempts += 1
        if self.state.brainstorm_attempts > self.state.max_brainstorm_attempts:
            logger.warning(
                "MainProjectFlow: brainstorm attempts exhausted (%d/%d) for project %d",
                self.state.brainstorm_attempts, self.state.max_brainstorm_attempts,
                self.state.project_id,
            )
            return "brainstorm_exhausted"

        logger.info(
            "MainProjectFlow: triggering brainstorming session (attempt %d/%d)",
            self.state.brainstorm_attempts, self.state.max_brainstorm_attempts,
        )

        brainstorm_flow = BrainstormingFlow()
        brainstorm_flow.kickoff(inputs={
            "project_id": self.state.project_id,
        })

        log_flow_event(
            self.state.project_id, "brainstorming_completed",
            "main_project_flow", "project", self.state.project_id,
        )
        return "brainstorm_done"

    @listen("brainstorm_done")
    def after_brainstorm(self):
        """Signal to re-check tasks after brainstorming.

        Triggers "after_brainstorm" → check_and_launch_tasks via or_().
        """
        logger.info("MainProjectFlow: after_brainstorm — re-checking pending tasks")

    @listen("brainstorm_exhausted")
    def handle_brainstorm_exhausted(self):
        """Escalate to user after exhausting brainstorming attempts."""
        logger.warning(
            "MainProjectFlow: all brainstorm attempts exhausted for project %d",
            self.state.project_id,
        )

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        send_agent_message(
            project_id=self.state.project_id,
            from_agent="system",
            to_agent=None,
            to_role="project_lead",
            message=(
                f"Project {self.state.project_id} has exhausted all brainstorming attempts "
                f"({self.state.max_brainstorm_attempts}) without meeting objectives. "
                f"Manual intervention is required."
            ),
        )

        log_flow_event(
            self.state.project_id, "brainstorm_exhausted", "main_project_flow",
            "project", self.state.project_id,
            {"attempts": self.state.brainstorm_attempts},
        )

    @listen("evaluation_exhausted")
    def handle_evaluation_exhausted(self):
        """Escalate to user after exhausting evaluation attempts."""
        logger.warning(
            "MainProjectFlow: all evaluation attempts exhausted for project %d",
            self.state.project_id,
        )

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        send_agent_message(
            project_id=self.state.project_id,
            from_agent="system",
            to_agent=None,
            to_role="project_lead",
            message=(
                f"Project {self.state.project_id} has exhausted all progress evaluation "
                f"attempts ({self.state.max_evaluate_progress_attempts}) without being "
                f"able to define next steps. Manual intervention is required."
            ),
        )

        log_flow_event(
            self.state.project_id, "evaluation_exhausted", "main_project_flow",
            "project", self.state.project_id,
            {"attempts": self.state.evaluate_progress_attempts},
        )

    @listen("project_complete")
    def finalize(self):
        """Mark project as completed and generate final report."""
        self.state.current_step = "finalize"
        save_snapshot(self.state.project_id, "main_project_flow", "finalize", self.state)
        logger.info("MainProjectFlow: finalizing project %d", self.state.project_id)

        self.state.status = ProjectStatus.COMPLETED
        update_project_status(self.state.project_id, "completed")

        report = generate_final_report(self.state.project_id)

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=project_lead.agent_id,
        )
        task_prompt = pl_tasks.write_final_report(
            report,
            project_name=self.state.project_name,
            project_id=self.state.project_id,
            requirements=self.state.requirements,
            conversation_context=conv_ctx,
        )
        build_crew(project_lead, task_prompt).kickoff()

        log_flow_event(
            self.state.project_id, "project_completed", "main_project_flow",
            "project", self.state.project_id,
        )

    @listen("already_complete")
    def handle_already_complete(self):
        """Handle case where project was already completed."""
        logger.info("MainProjectFlow: project %d is already complete", self.state.project_id)

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: log and notify."""
        logger.error(
            "MainProjectFlow: error state reached (project_id=%d)",
            self.state.project_id,
        )
        log_flow_event(
            self.state.project_id, "flow_error", "main_project_flow",
            "project", self.state.project_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"MainProjectFlow error for project {self.state.project_id}. "
            f"Please investigate.",
        )

    # ── External event handlers ───────────────────────────────────────────

    @listen("stagnation_detected")
    def handle_stagnation(self):
        """Analyze stuck tasks and attempt to unblock them.

        Triggers "handle_stagnation" → check_and_launch_tasks via or_().
        """
        from backend.flows.helpers import get_stuck_tasks

        logger.warning(
            "MainProjectFlow: stagnation detected for project %d",
            self.state.project_id,
        )
        log_flow_event(
            self.state.project_id, "stagnation_detected", "main_project_flow",
            "project", self.state.project_id,
        )

        stuck = get_stuck_tasks(self.state.project_id)
        if not stuck:
            logger.info("MainProjectFlow: no stuck tasks found, re-checking pending")
            return

        logger.info(
            "MainProjectFlow: %d stuck tasks found, Team Lead intervening",
            len(stuck),
        )

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=team_lead.agent_id,
        )

        for task in stuck:
            task_id = task["id"]
            task_title = task.get("title", "")
            branch_name = task.get("branch_name", "")
            developer_id = task.get("assigned_to", "")

            task_prompt = tl_tasks.handle_escalation(
                task_id, task_title, branch_name, developer_id,
                project_id=self.state.project_id,
                project_name=self.state.project_name,
                conversation_context=conv_ctx,
            )
            try:
                build_crew(team_lead, task_prompt).kickoff()
            except Exception:
                logger.exception(
                    "MainProjectFlow: Team Lead intervention failed for task %d",
                    task_id,
                )

            log_flow_event(
                self.state.project_id, "stagnation_intervention",
                "main_project_flow", "task", task_id,
            )
