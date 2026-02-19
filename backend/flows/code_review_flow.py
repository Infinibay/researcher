"""CodeReviewFlow — manages the code review cycle with retry and escalation.

Lifecycle: receive request → review → approve/reject → rework loop → escalate after max rejections.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method "X" completes or a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes next trigger
- Non-router return values are DATA only, not triggers
"""

from __future__ import annotations

import logging

from crewai import Crew, Task
from crewai.flow.flow import Flow, listen, or_, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.flows.helpers import (
    get_task_by_id,
    increment_task_retry,
    log_flow_event,
    notify_team_lead,
    parse_review_result,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.state_models import CodeReviewState, ReviewStatus
from backend.prompts.code_reviewer import tasks as cr_tasks
from backend.prompts.developer import tasks as dev_tasks

logger = logging.getLogger(__name__)


@persist()
class CodeReviewFlow(Flow[CodeReviewState]):
    """Manages a code review cycle with up to max_rejections retries."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def receive_review_request(self):
        """Load task and branch details, prepare for review."""
        logger.info(
            "CodeReviewFlow: receive_review_request (task_id=%d, branch=%s)",
            self.state.task_id, self.state.branch_name,
        )

        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return

        self.state.review_status = ReviewStatus.REVIEWING
        update_task_status(self.state.task_id, "review_ready")

        log_flow_event(
            self.state.project_id, "review_started", "code_review_flow",
            "task", self.state.task_id,
            {"branch_name": self.state.branch_name},
        )

    @router("receive_review_request")
    def route_review_request(self):
        """Route based on whether review request is valid."""
        if self.state.review_status != ReviewStatus.REVIEWING:
            return "error"
        return "review_requested"

    # ── Review execution ──────────────────────────────────────────────────

    @listen(or_("review_requested", "notify_developer_rework"))
    def perform_review(self):
        """Code Reviewer agent reviews the code on the branch."""
        logger.info(
            "CodeReviewFlow: perform_review for task %d (attempt %d/%d)",
            self.state.task_id,
            self.state.rejection_count + 1,
            self.state.max_rejections,
        )

        reviewer = get_available_agent_by_role("code_reviewer", self.state.project_id)
        self.state.reviewer_id = reviewer.agent_id
        reviewer.activate_context(task_id=self.state.task_id)
        run_id = reviewer.create_agent_run(self.state.task_id)
        self.state.agent_run_id = run_id

        task = get_task_by_id(self.state.task_id)
        task_title = task.get("title", "") if task else ""
        task_desc = task.get("description", "") if task else ""

        desc, expected = cr_tasks.perform_review(
            self.state.task_id, task_title,
            self.state.branch_name, task_desc,
            project_id=self.state.project_id,
            rejection_count=self.state.rejection_count,
            max_rejections=self.state.max_rejections,
        )
        crew = Crew(
            agents=[reviewer.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=reviewer.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        try:
            result = str(crew.kickoff()).strip()
        except Exception as exc:
            logger.exception("Crew execution failed in perform_review for task %d", self.state.task_id)
            reviewer.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "review_failed", "code_review_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            raise

        reviewer.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        if parse_review_result(result) == "approved":
            self.state.review_status = ReviewStatus.APPROVED
            self.state.reviewer_comments.append(f"APPROVED: {result}")
            log_flow_event(
                self.state.project_id, "review_approved", "code_review_flow",
                "task", self.state.task_id,
            )
        else:
            feedback = result
            if ":" in result:
                feedback = result.split(":", 1)[1].strip()
            self.state.review_status = ReviewStatus.REJECTED
            self.state.reviewer_comments.append(f"REJECTED: {feedback}")
            log_flow_event(
                self.state.project_id, "review_rejected", "code_review_flow",
                "task", self.state.task_id,
                {"rejection_count": self.state.rejection_count + 1, "feedback": feedback[:200]},
            )

    # ── Review routing ────────────────────────────────────────────────────

    @router("perform_review")
    def review_outcome_router(self):
        """Route based on review outcome: approved, rework, or escalate."""
        if self.state.review_status == ReviewStatus.APPROVED:
            return "review_approved"

        # Rejected path
        self.state.rejection_count += 1
        increment_task_retry(self.state.task_id)

        if self.state.rejection_count >= self.state.max_rejections:
            logger.warning(
                "CodeReviewFlow: max rejections (%d) reached for task %d",
                self.state.max_rejections, self.state.task_id,
            )
            return "escalate"
        return "request_rework"

    # ── Rework cycle ──────────────────────────────────────────────────────

    @listen("request_rework")
    def notify_developer_rework(self):
        """Developer reads feedback, applies changes, and resubmits.

        Triggers "notify_developer_rework" → perform_review via or_().
        """
        logger.info(
            "CodeReviewFlow: requesting rework for task %d (rejection %d/%d)",
            self.state.task_id,
            self.state.rejection_count,
            self.state.max_rejections,
        )

        developer = get_agent_by_role(
            "developer", self.state.project_id,
            agent_id=self.state.developer_id,
        )
        developer.activate_context(task_id=self.state.task_id)
        run_id = developer.create_agent_run(self.state.task_id)

        latest_feedback = self.state.reviewer_comments[-1] if self.state.reviewer_comments else ""

        update_task_status(self.state.task_id, "rejected")

        desc, expected = dev_tasks.rework_code(
            self.state.task_id, self.state.rejection_count,
            self.state.max_rejections, latest_feedback,
            self.state.branch_name,
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

        developer.complete_agent_run(run_id, status="completed", output_summary=str(result)[:500])

        if self.state.rejection_count == 2:
            notify_team_lead(
                self.state.project_id,
                self.state.developer_id or "developer",
                f"Task {self.state.task_id} has been rejected {self.state.rejection_count} times. "
                f"Next rejection will trigger escalation.",
            )

        log_flow_event(
            self.state.project_id, "rework_completed", "code_review_flow",
            "task", self.state.task_id,
            {"rejection_count": self.state.rejection_count},
        )

    # ── Approval finalization ─────────────────────────────────────────────

    @listen("review_approved")
    def finalize_approval(self):
        """Finalize an approved review."""
        logger.info("CodeReviewFlow: task %d approved", self.state.task_id)
        self.state.review_status = ReviewStatus.APPROVED
        update_task_status(self.state.task_id, "done")

        log_flow_event(
            self.state.project_id, "review_finalized", "code_review_flow",
            "task", self.state.task_id,
        )

    # ── Escalation ────────────────────────────────────────────────────────

    @listen("escalate")
    def handle_escalation(self):
        """Escalate to Team Lead after max rejections."""
        logger.warning(
            "CodeReviewFlow: escalating task %d after %d rejections",
            self.state.task_id, self.state.rejection_count,
        )

        self.state.review_status = ReviewStatus.ESCALATED

        comments_summary = "\n".join(self.state.reviewer_comments[-3:])
        notify_team_lead(
            self.state.project_id,
            self.state.reviewer_id or "code_reviewer",
            f"ESCALATION: Task {self.state.task_id} has been rejected "
            f"{self.state.rejection_count} times.\n"
            f"Branch: {self.state.branch_name}\n"
            f"Recent review comments:\n{comments_summary}\n"
            f"Requires Team Lead intervention.",
        )

        update_task_status(self.state.task_id, "in_progress")

        log_flow_event(
            self.state.project_id, "review_escalated", "code_review_flow",
            "task", self.state.task_id,
            {"rejection_count": self.state.rejection_count},
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: mark task as failed, notify team lead."""
        logger.error(
            "CodeReviewFlow: error state reached (task_id=%d, project_id=%d)",
            self.state.task_id, self.state.project_id,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "flow_error", "code_review_flow",
            "task", self.state.task_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"CodeReviewFlow error: task {self.state.task_id} review failed unexpectedly. "
            f"Please investigate.",
        )
