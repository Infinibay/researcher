"""DevelopmentFlow — handles task assignment, implementation, and review handoff.

Lifecycle: assign → checkin → approve → implement → code review → escalation (if needed).
Post-escalation: TL decides → READY_FOR_MERGE (done) or NEEDS_REVIEW → rework → re-review.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method "X" completes or a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes next trigger
- Non-router return values are DATA only, not triggers
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from crewai import Crew, Task
from crewai.flow.flow import Flow, listen, or_, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.communication.protocol import TicketProtocol
from backend.flows.helpers import (
    check_task_dependencies,
    detect_tech_hints,
    get_task_by_id,
    log_flow_event,
    notify_team_lead,
    set_task_branch,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.state_models import DevelopmentState, ReviewStatus
from backend.prompts.developer import tasks as dev_tasks
from backend.prompts.team import build_conversation_context
from backend.prompts.team_lead import tasks as tl_tasks

logger = logging.getLogger(__name__)


@persist()
class DevelopmentFlow(Flow[DevelopmentState]):
    """Manages the development lifecycle for a single task."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def assign_task(self):
        """Load task, verify dependencies, and assign to a developer."""
        logger.info(
            "DevelopmentFlow: assign_task (task_id=%d)", self.state.task_id,
        )

        # Load task details from DB
        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return

        self.state.task_title = task.get("title", "")
        self.state.task_description = task.get("description", "")

        # Verify dependencies are met
        deps_ok = check_task_dependencies(self.state.task_id)
        if not deps_ok:
            logger.warning(
                "Task %d has unmet dependencies, returning to backlog",
                self.state.task_id,
            )
            self.state.dependencies_met = False
            return
        self.state.dependencies_met = True

        # Detect project technologies for developer prompt enrichment
        self.state.tech_hints = detect_tech_hints(self.state.project_id)

        # Team Lead assigns the task using TakeTask
        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context(task_id=self.state.task_id)

        desc, expected = tl_tasks.assign_task(
            self.state.task_id, self.state.task_title,
            self.state.task_description,
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
        crew.kickoff()

        # Developer consults Team Lead for clarifications
        developer = get_available_agent_by_role(
            "developer", self.state.project_id,
            tech_hints=self.state.tech_hints,
        )
        self.state.developer_id = developer.agent_id
        developer.activate_context(task_id=self.state.task_id)

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=self.state.developer_id,
            task_id=self.state.task_id,
        )
        desc, expected = dev_tasks.review_assigned_task(
            self.state.task_id, self.state.task_title,
            self.state.task_description,
            conversation_context=conv_ctx,
        )
        crew = Crew(
            agents=[developer.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=developer.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        dev_result = crew.kickoff()
        dev_plan = str(dev_result)[:1000]

        update_task_status(self.state.task_id, "pending")

        log_flow_event(
            self.state.project_id, "task_assigned", "development_flow",
            "task", self.state.task_id,
            {"developer_id": self.state.developer_id},
        )

        # Initiate the pre-ticket check-in protocol
        protocol = TicketProtocol()
        thread_id = protocol.initiate_checkin(
            project_id=self.state.project_id,
            task_id=self.state.task_id,
            agent_id=self.state.developer_id,
            agent_role="developer",
        )
        self.state.checkin_thread_id = thread_id

        # Developer posts their understanding to the check-in thread
        protocol.post_understanding(
            thread_id=thread_id,
            agent_id=self.state.developer_id,
            understanding_summary=(
                f"Task: {self.state.task_title}\n\n"
                f"My implementation plan:\n{dev_plan}\n\n"
                "Ready for team lead review."
            ),
        )

        # Team Lead reviews the check-in plan
        self._review_checkin(
            protocol, team_lead, developer, thread_id, dev_plan,
        )

    def _review_checkin(
        self,
        protocol: TicketProtocol,
        team_lead: Any,
        developer: Any,
        thread_id: str,
        dev_plan: str,
    ) -> None:
        """Run TL crew to review the developer's check-in plan.

        Handles one retry if the TL requests clarification.
        Auto-approves on errors to avoid blocking the flow.
        """
        max_rounds = 2
        for round_num in range(max_rounds):
            try:
                desc, expected = tl_tasks.review_checkin(
                    task_id=self.state.task_id,
                    task_title=self.state.task_title,
                    developer_plan=dev_plan,
                    thread_id=thread_id,
                    project_id=self.state.project_id,
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
                checkin_result = str(crew.kickoff()).strip()
            except Exception:
                logger.exception(
                    "Error running TL checkin review for task %d (round %d)",
                    self.state.task_id, round_num + 1,
                )
                protocol.approve_checkin(
                    thread_id=thread_id,
                    team_lead_id=team_lead.agent_id,
                )
                log_flow_event(
                    self.state.project_id, "checkin_reviewed",
                    "development_flow", "task", self.state.task_id,
                    {"result": "auto_approved_after_error", "round": round_num + 1},
                )
                return

            if checkin_result.upper().startswith("APPROVED"):
                protocol.approve_checkin(
                    thread_id=thread_id,
                    team_lead_id=team_lead.agent_id,
                )
                log_flow_event(
                    self.state.project_id, "checkin_reviewed",
                    "development_flow", "task", self.state.task_id,
                    {"result": "approved", "round": round_num + 1},
                )
                return

            if checkin_result.upper().startswith("CLARIFICATION_NEEDED"):
                # On the final round, skip sending a clarification to avoid
                # conflicting signals (clarification then auto-approve) in the
                # thread. Fall through to the auto-approve block instead.
                if round_num >= max_rounds - 1:
                    break

                protocol.request_clarification(
                    thread_id=thread_id,
                    team_lead_id=team_lead.agent_id,
                    clarification=checkin_result,
                )
                log_flow_event(
                    self.state.project_id, "checkin_reviewed",
                    "development_flow", "task", self.state.task_id,
                    {"result": "clarification_requested", "round": round_num + 1},
                )

                # Re-run developer to respond to clarification
                developer.activate_context(task_id=self.state.task_id)
                desc_dev, expected_dev = dev_tasks.review_assigned_task(
                    self.state.task_id, self.state.task_title,
                    self.state.task_description,
                )
                dev_crew = Crew(
                    agents=[developer.crewai_agent],
                    tasks=[Task(
                        description=desc_dev,
                        agent=developer.crewai_agent,
                        expected_output=expected_dev,
                    )],
                    verbose=True,
                )
                dev_result = dev_crew.kickoff()
                dev_plan = str(dev_result)[:1000]

                protocol.post_understanding(
                    thread_id=thread_id,
                    agent_id=self.state.developer_id,
                    understanding_summary=(
                        f"Task: {self.state.task_title}\n\n"
                        f"Updated implementation plan:\n{dev_plan}\n\n"
                        "Ready for team lead review."
                    ),
                )
                continue

        # Exhausted retries — auto-approve to unblock the flow
        logger.warning(
            "Check-in review exhausted retries for task %d, auto-approving",
            self.state.task_id,
        )
        protocol.approve_checkin(
            thread_id=thread_id,
            team_lead_id=team_lead.agent_id,
        )
        log_flow_event(
            self.state.project_id, "checkin_reviewed",
            "development_flow", "task", self.state.task_id,
            {"result": "auto_approved_after_retries"},
        )

    @router("assign_task")
    def route_assignment(self):
        """Route based on task assignment result."""
        if not self.state.task_title:
            # Task not found
            return "error"
        if not self.state.dependencies_met:
            return "blocked"
        return "checkin_initiated"

    @listen("blocked")
    def handle_blocked(self):
        """Keep task in backlog when dependencies aren't met."""
        logger.info("DevelopmentFlow: task %d blocked by dependencies", self.state.task_id)
        update_task_status(self.state.task_id, "backlog")

    # ── Check-in gate ─────────────────────────────────────────────────────

    @listen("checkin_initiated")
    def wait_for_checkin_approval(self):
        """Wait for team lead approval via event bus.

        On timeout the task returns to backlog — it does NOT proceed without approval.
        """
        from backend.flows.event_listeners import event_bus

        logger.info(
            "DevelopmentFlow: waiting for check-in approval on task %d (thread %s)",
            self.state.task_id, self.state.checkin_thread_id,
        )

        max_wait_seconds = 1800  # 30 minutes
        approved_event = threading.Event()
        task_id = self.state.task_id

        def _on_checkin_approved(event):
            if event.entity_id == task_id:
                approved_event.set()

        event_bus.subscribe("ticket_checkin_approved", _on_checkin_approved)

        try:
            protocol = TicketProtocol()
            status = protocol.get_checkin_status(self.state.task_id)
            if status["status"] == "resolved":
                approved_event.set()
            approved_event.wait(timeout=max_wait_seconds)
        finally:
            event_bus.unsubscribe("ticket_checkin_approved", _on_checkin_approved)

        if approved_event.is_set():
            self.state.checkin_approved = True
            logger.info(
                "DevelopmentFlow: check-in approved for task %d",
                self.state.task_id,
            )
            log_flow_event(
                self.state.project_id,
                "ticket_checkin_approved",
                "development_flow",
                "task",
                self.state.task_id,
                {"thread_id": self.state.checkin_thread_id},
            )
        else:
            self.state.checkin_approved = False
            logger.warning(
                "DevelopmentFlow: check-in approval timed out for task %d",
                self.state.task_id,
            )
            notify_team_lead(
                self.state.project_id,
                self.state.developer_id,
                f"Check-in approval timed out for task {self.state.task_id}. "
                f"Please review thread {self.state.checkin_thread_id}.",
            )

    @router("wait_for_checkin_approval")
    def route_after_checkin(self):
        """Route based on check-in approval result."""
        if self.state.checkin_approved:
            return "task_assigned"
        update_task_status(self.state.task_id, "backlog")
        return "blocked"

    # ── Implementation ────────────────────────────────────────────────────

    @listen("task_assigned")
    def implement_code(self):
        """Developer creates branch, writes code, and commits."""
        logger.info("DevelopmentFlow: implement_code for task %d", self.state.task_id)

        developer = get_agent_by_role(
            "developer", self.state.project_id,
            agent_id=self.state.developer_id,
            tech_hints=self.state.tech_hints,
        )
        developer.activate_context(task_id=self.state.task_id)
        run_id = developer.create_agent_run(self.state.task_id)
        self.state.agent_run_id = run_id

        update_task_status(self.state.task_id, "in_progress")

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=self.state.developer_id,
            task_id=self.state.task_id,
        )
        desc, expected = dev_tasks.implement_code(
            self.state.task_id, self.state.task_title,
            self.state.task_description,
            conversation_context=conv_ctx,
        )
        crew = Crew(
            agents=[developer.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=developer.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        try:
            result = crew.kickoff()
        except Exception as exc:
            logger.exception("Crew execution failed in implement_code for task %d", self.state.task_id)
            developer.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "implementation_failed", "development_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"DevelopmentFlow error: task {self.state.task_id} implementation failed. "
                f"Error: {type(exc).__name__}",
            )
            raise  # Prevent downstream listeners

        # Extract branch name from result or generate default
        result_text = str(result)
        branch_name = f"task-{self.state.task_id}"
        for line in result_text.split("\n"):
            line = line.strip()
            if line.startswith("task-") or line.startswith("feature/"):
                branch_name = line.split()[0]
                break

        self.state.branch_name = branch_name
        set_task_branch(self.state.task_id, branch_name)

        developer.complete_agent_run(run_id, status="completed", output_summary=result_text[:500])

        log_flow_event(
            self.state.project_id, "implementation_done", "development_flow",
            "task", self.state.task_id,
            {"branch_name": branch_name},
        )

    # ── Code Review handoff ───────────────────────────────────────────────

    @router("implement_code")
    def request_review(self):
        """Invoke CodeReviewFlow and route based on the outcome."""
        from backend.flows.code_review_flow import CodeReviewFlow

        logger.info(
            "DevelopmentFlow: requesting code review for task %d (branch=%s)",
            self.state.task_id, self.state.branch_name,
        )

        review_flow = CodeReviewFlow()
        review_flow.kickoff(inputs={
            "project_id": self.state.project_id,
            "task_id": self.state.task_id,
            "branch_name": self.state.branch_name,
            "developer_id": self.state.developer_id,
        })

        # Check the review outcome
        review_status = review_flow.state.review_status
        self.state.review_status = review_status

        if review_status == ReviewStatus.APPROVED:
            log_flow_event(
                self.state.project_id, "review_approved", "development_flow",
                "task", self.state.task_id,
            )
            return "review_passed"
        elif review_status == ReviewStatus.ESCALATED:
            self.state.escalated = True
            log_flow_event(
                self.state.project_id, "review_escalated", "development_flow",
                "task", self.state.task_id,
            )
            return "escalated"
        else:
            return "review_passed"

    # ── Escalation handling ───────────────────────────────────────────────

    @listen("escalated")
    def handle_escalation(self):
        """Team Lead intervenes after repeated review failures."""
        logger.warning(
            "DevelopmentFlow: escalation for task %d", self.state.task_id,
        )

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context(task_id=self.state.task_id)

        desc, expected = tl_tasks.handle_escalation(
            self.state.task_id, self.state.task_title,
            self.state.branch_name, self.state.developer_id,
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
        result_text = str(result).strip()

        log_flow_event(
            self.state.project_id, "escalation_resolved", "development_flow",
            "task", self.state.task_id,
            {"resolution": result_text[:500]},
        )

        # Parse TL decision
        if result_text.upper().startswith("READY_FOR_MERGE"):
            self.state.tl_escalation_decision = "ready_for_merge"
        else:
            self.state.tl_escalation_decision = "needs_review"
            self.state.tl_escalation_guidance = result_text

    @router("handle_escalation")
    def route_after_escalation(self):
        """Route based on TL decision: merge directly or rework + re-review."""
        if self.state.tl_escalation_decision == "ready_for_merge":
            update_task_status(self.state.task_id, "done")
            return "review_passed"

        if self.state.escalation_occurred:
            # Second escalation — force done to prevent infinite loops
            logger.warning(
                "DevelopmentFlow: repeated escalation for task %d, forcing completion",
                self.state.task_id,
            )
            update_task_status(self.state.task_id, "done")
            return "review_passed"

        self.state.escalation_occurred = True
        return "post_escalation_rework"

    # ── Post-escalation rework + re-review ────────────────────────────────

    @listen("post_escalation_rework")
    def do_post_escalation_rework(self):
        """Developer reworks code based on Team Lead guidance after escalation."""
        logger.info(
            "DevelopmentFlow: post-escalation rework for task %d",
            self.state.task_id,
        )

        developer = get_agent_by_role(
            "developer", self.state.project_id,
            agent_id=self.state.developer_id,
            tech_hints=self.state.tech_hints,
        )
        developer.activate_context(task_id=self.state.task_id)
        run_id = developer.create_agent_run(self.state.task_id)

        desc, expected = dev_tasks.rework_code(
            self.state.task_id,
            rejection_count=1,
            max_rejections=3,
            latest_feedback=self.state.tl_escalation_guidance,
            branch_name=self.state.branch_name,
        )
        crew = Crew(
            agents=[developer.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=developer.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()

        developer.complete_agent_run(
            run_id, status="completed",
            output_summary=str(result)[:500],
        )

        log_flow_event(
            self.state.project_id, "post_escalation_rework_completed",
            "development_flow", "task", self.state.task_id,
        )

    @router("do_post_escalation_rework")
    def post_escalation_review(self):
        """Kick off CodeReviewFlow with reduced max_rejections after escalation rework."""
        from backend.flows.code_review_flow import CodeReviewFlow

        logger.info(
            "DevelopmentFlow: post-escalation review for task %d (branch=%s)",
            self.state.task_id, self.state.branch_name,
        )

        review_flow = CodeReviewFlow()
        review_flow.kickoff(inputs={
            "project_id": self.state.project_id,
            "task_id": self.state.task_id,
            "branch_name": self.state.branch_name,
            "developer_id": self.state.developer_id,
            "max_rejections": 3,
        })

        review_status = review_flow.state.review_status
        self.state.review_status = review_status

        if review_status == ReviewStatus.APPROVED:
            log_flow_event(
                self.state.project_id, "post_escalation_review_approved",
                "development_flow", "task", self.state.task_id,
            )
            return "review_passed"

        if review_status == ReviewStatus.ESCALATED:
            # Already went through one escalation cycle — force done
            logger.warning(
                "DevelopmentFlow: post-escalation review escalated again for task %d, "
                "forcing completion",
                self.state.task_id,
            )
            update_task_status(self.state.task_id, "done")
            return "review_passed"

        # Default: treat as passed
        return "review_passed"

    # ── Finalization ──────────────────────────────────────────────────────

    @listen("review_passed")
    def finalize_task(self):
        """Finalize after successful review (task already marked done by CodeReviewFlow)."""
        logger.info("DevelopmentFlow: finalizing task %d", self.state.task_id)

        log_flow_event(
            self.state.project_id, "task_completed", "development_flow",
            "task", self.state.task_id,
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: mark task as failed, notify team lead."""
        logger.error(
            "DevelopmentFlow: error state reached (task_id=%d, project_id=%d)",
            self.state.task_id, self.state.project_id,
        )
        update_task_status_safe(self.state.task_id, "failed")
        if self.state.agent_run_id:
            try:
                developer = get_agent_by_role("developer", self.state.project_id)
                developer.complete_agent_run(
                    self.state.agent_run_id, status="failed",
                    error_class="FlowError",
                )
            except Exception:
                logger.exception("Could not complete agent run on error")
        log_flow_event(
            self.state.project_id, "flow_error", "development_flow",
            "task", self.state.task_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"DevelopmentFlow error: task {self.state.task_id} failed. "
            f"Please investigate and re-assign.",
        )
