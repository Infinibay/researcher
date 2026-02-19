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

from crewai import Crew, Task
from crewai.flow.flow import Flow, listen, or_, router, start
from crewai.flow.persistence import persist
from pydantic import BaseModel

from backend.agents.registry import get_agent_by_role, initialize_project_team
from backend.flows.helpers import (
    all_objectives_met,
    classify_approval_response,
    create_project,
    generate_final_report,
    get_completed_task_count,
    get_pending_tasks,
    load_project_state,
    log_flow_event,
    notify_team_lead,
    send_agent_message,
    update_project_status,
)
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

        # NEW or PLANNING → start planning
        return "new_project"

    # ── Requirements gathering ────────────────────────────────────────────

    @listen(or_("new_project", "handle_rejection"))
    def consult_project_lead(self):
        """Project Lead gathers and clarifies requirements with the user."""
        logger.info("MainProjectFlow: consult_project_lead")
        self.state.requirements_attempts += 1
        self.state.status = ProjectStatus.PLANNING
        update_project_status(self.state.project_id, "planning")

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
        desc, expected = pl_tasks.gather_requirements(
            self.state.project_name, self.state.project_id,
            existing_reqs, feedback_context,
            conversation_context=conv_ctx,
        )
        crew = Crew(
            agents=[project_lead.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=project_lead.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()
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
        logger.info("MainProjectFlow: create_plan")

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=team_lead.agent_id,
        )
        desc, expected = tl_tasks.create_plan(
            self.state.project_name, self.state.project_id,
            self.state.requirements,
            conversation_context=conv_ctx,
        )
        crew = Crew(
            agents=[team_lead.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=team_lead.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()
        self.state.plan = str(result)

        log_flow_event(
            self.state.project_id, "plan_created", "main_project_flow",
            "project", self.state.project_id,
        )

    # ── Plan approval ─────────────────────────────────────────────────────

    @router("create_plan")
    def plan_approval_router(self):
        """Project Lead presents the plan to the user for approval."""
        logger.info("MainProjectFlow: plan_approval_router")

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        desc, expected = pl_tasks.present_plan_for_approval(self.state.plan)
        crew = Crew(
            agents=[project_lead.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=project_lead.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = str(crew.kickoff()).strip()

        if classify_approval_response(result) == "approved":
            self.state.user_approved = True
            log_flow_event(
                self.state.project_id, "plan_approved", "main_project_flow",
                "project", self.state.project_id,
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

    @listen("rejected")
    def handle_rejection(self):
        """Clear plan and loop back to requirements gathering with feedback.

        Triggers "handle_rejection" → consult_project_lead via or_().
        If max_requirements_attempts reached, force approval with latest feedback.
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
            return

        self.state.plan = ""

    # ── Structure creation ────────────────────────────────────────────────

    @listen("approved")
    def create_structure(self):
        """Team Lead creates epics/milestones/tasks in the DB from the plan."""
        logger.info("MainProjectFlow: create_structure")

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        desc, expected = tl_tasks.create_structure(
            self.state.project_name, self.state.project_id,
            self.state.plan,
        )
        crew = Crew(
            agents=[team_lead.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=team_lead.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()

        self.state.status = ProjectStatus.EXECUTING
        update_project_status(self.state.project_id, "executing")

        log_flow_event(
            self.state.project_id, "structure_created", "main_project_flow",
            "project", self.state.project_id,
            {"result": str(result)[:500]},
        )

    # ── Task execution loop ───────────────────────────────────────────────

    @router(or_(
        "create_structure",
        "resume_execution",
        "check_pending_after_task",
        "after_brainstorm",
        "handle_stagnation",
    ))
    def check_and_launch_tasks(self):
        """Check for pending tasks and launch sub-flows.

        This router is triggered by multiple sources:
        - create_structure: after project structure is created
        - resume_execution: when resuming a paused project
        - check_pending_after_task: after a task completes (cycle)
        - after_brainstorm: after brainstorming creates new tasks
        - handle_stagnation: after stagnation intervention
        """
        return self._launch_pending_tasks()

    @listen("task_completed")
    def check_pending_after_task(self):
        """Handle task completion — update counters and trigger re-check.

        Triggers "check_pending_after_task" → check_and_launch_tasks via or_().
        """
        self.state.completed_tasks = get_completed_task_count(self.state.project_id)
        self.state.brainstorm_attempts = 0

    def _launch_pending_tasks(self) -> str:
        """Launch up to max_concurrent_tasks sub-flows and wait for any to finish.

        Returns "no_pending_tasks" or "task_completed" as routing signals.
        """
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

        # Wait for any sub-flow to finish
        def _on_task_done(event):
            if event.project_id == self.state.project_id:
                completion_event.set()

        event_bus.subscribe("task_done", _on_task_done)
        try:
            completion_event.wait(timeout=3600)
        finally:
            event_bus.unsubscribe("task_done", _on_task_done)

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
        """Check if project objectives are met or if brainstorming is needed."""
        if all_objectives_met(self.state.project_id):
            return "project_complete"
        return "not_complete"

    @router("not_complete")
    def trigger_brainstorming(self):
        """Launch BrainstormingFlow to generate new ideas and tasks."""
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

    @listen("project_complete")
    def finalize(self):
        """Mark project as completed and generate final report."""
        logger.info("MainProjectFlow: finalizing project %d", self.state.project_id)

        self.state.status = ProjectStatus.COMPLETED
        update_project_status(self.state.project_id, "completed")

        report = generate_final_report(self.state.project_id)

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        project_lead.activate_context()

        desc, expected = pl_tasks.write_final_report(report)
        crew = Crew(
            agents=[project_lead.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=project_lead.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        crew.kickoff()

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

        for task in stuck:
            task_id = task["id"]
            task_title = task.get("title", "")
            branch_name = task.get("branch_name", "")
            developer_id = task.get("assigned_to", "")

            desc, expected = tl_tasks.handle_escalation(
                task_id, task_title, branch_name, developer_id,
            )
            crew = Crew(
                agents=[team_lead.crewai_agent],
                tasks=[Task(
                    description=desc,
                    agent=team_lead.crewai_agent,
                    expected_output=expected,
                )],
                verbose=True,
            )
            try:
                crew.kickoff()
            except Exception:
                logger.exception(
                    "MainProjectFlow: Team Lead intervention failed for task %d",
                    task_id,
                )

            log_flow_event(
                self.state.project_id, "stagnation_intervention",
                "main_project_flow", "task", task_id,
            )
