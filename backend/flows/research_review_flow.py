"""ResearchReviewFlow — independent peer review for research tasks.

Triggered after ResearchFlow completes artifact verification.
Can also be launched independently for orphaned review_ready research tasks.

Lifecycle: receive request → peer review → approve/reject → revision loop.
"""

from __future__ import annotations

import logging

from crewai.flow.flow import Flow, listen, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.engine import get_engine
from backend.engine.base import AgentKilledError
from backend.flows.guardrails import validate_research_review_verdict
from backend.flows.helpers import (
    get_project_name,
    get_task_by_id,
    log_flow_event,
    notify_team_lead,
    parse_review_result,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.snapshot_service import update_subflow_step
from backend.flows.state_models import ResearchReviewState
from backend.knowledge import KnowledgeService
from backend.prompts.research_reviewer import tasks as rr_tasks
from backend.prompts.researcher import tasks as res_tasks

logger = logging.getLogger(__name__)


@persist()
class ResearchReviewFlow(Flow[ResearchReviewState]):
    """Manages peer review for a research task independently."""

    def _ensure_services(self) -> None:
        if not getattr(self, "_knowledge_service", None):
            self._knowledge_service = KnowledgeService()

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def receive_review_request(self):
        """Load task details and prepare for peer review."""
        logger.info(
            "ResearchReviewFlow: receive_review_request (task_id=%d)",
            self.state.task_id,
        )

        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return

        self.state.task_title = task.get("title", "")
        if not self.state.project_name:
            self.state.project_name = get_project_name(self.state.project_id)

        # Ensure task is in review_ready
        update_task_status_safe(self.state.task_id, "review_ready")

        log_flow_event(
            self.state.project_id, "research_review_started",
            "research_review_flow", "task", self.state.task_id,
        )

    @router("receive_review_request")
    def route_review_request(self):
        if not self.state.task_title:
            return "error"
        return "ready_for_review"

    # ── Peer review ───────────────────────────────────────────────────────

    @listen("ready_for_review")
    def perform_peer_review(self):
        """Research Reviewer evaluates findings and methodology."""
        update_subflow_step(
            self.state.project_id, "research_review_flow", "perform_peer_review",
        )
        logger.info(
            "ResearchReviewFlow: perform_peer_review for task %d",
            self.state.task_id,
        )

        self._ensure_services()
        reviewer = get_available_agent_by_role(
            "research_reviewer", self.state.project_id,
            knowledge_service=self._knowledge_service,
        )
        self.state.reviewer_id = reviewer.agent_id
        reviewer.activate_context(task_id=self.state.task_id)
        run_id = reviewer.create_agent_run(self.state.task_id)

        task_prompt = rr_tasks.peer_review(
            self.state.task_id, self.state.task_title,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(
                reviewer, task_prompt,
                guardrail=validate_research_review_verdict,
            ).strip()
        except AgentKilledError:
            logger.info("Agent killed during peer_review for task %d", self.state.task_id)
            reviewer.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception(
                "Engine execution failed in peer_review for task %d",
                self.state.task_id,
            )
            reviewer.complete_agent_run(
                run_id, status="failed", error_class=type(exc).__name__,
            )
            log_flow_event(
                self.state.project_id, "peer_review_failed",
                "research_review_flow", "task", self.state.task_id,
                {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchReviewFlow error: task {self.state.task_id} peer review failed.",
            )
            raise

        reviewer.complete_agent_run(
            run_id, status="completed", output_summary=result[:500],
        )

        if parse_review_result(result, approve_keyword="VALIDATED") == "approved":
            self.state.validated = True
            self.state.last_reviewer_feedback = ""
        else:
            self.state.validated = False
            upper_result = result.upper()
            rejected_idx = upper_result.find("REJECTED:")
            if rejected_idx != -1:
                self.state.last_reviewer_feedback = result[
                    rejected_idx + len("REJECTED:"):
                ].strip()
            else:
                self.state.last_reviewer_feedback = result

        log_flow_event(
            self.state.project_id, "peer_review_done",
            "research_review_flow", "task", self.state.task_id,
            {"validated": self.state.validated},
        )

    @router("perform_peer_review")
    def review_outcome_router(self):
        if self.state.validated:
            return "validated"

        self.state.revision_count += 1
        if self.state.revision_count >= self.state.max_revisions:
            logger.warning(
                "ResearchReviewFlow: max revisions (%d) reached for task %d",
                self.state.max_revisions, self.state.task_id,
            )
            return "max_revisions_reached"

        return "rejected"

    # ── Rejection → revision → re-review loop ─────────────────────────────

    @router("rejected")
    def revise_research(self):
        """Researcher revises based on feedback, then re-review."""
        logger.info(
            "ResearchReviewFlow: revise_research for task %d (revision %d/%d)",
            self.state.task_id, self.state.revision_count, self.state.max_revisions,
        )

        self._ensure_services()

        # Resolve researcher from task assignment
        task = get_task_by_id(self.state.task_id)
        researcher_id = self.state.researcher_id
        if not researcher_id and task:
            researcher_id = task.get("assigned_to", "")
            self.state.researcher_id = researcher_id

        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.revise_research(
            self.state.task_id,
            reviewer_feedback=self.state.last_reviewer_feedback,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info(
                "Agent killed during revise_research for task %d",
                self.state.task_id,
            )
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception(
                "Engine execution failed in revise_research for task %d",
                self.state.task_id,
            )
            researcher.complete_agent_run(
                run_id, status="failed", error_class=type(exc).__name__,
            )
            log_flow_event(
                self.state.project_id, "rework_failed",
                "research_review_flow", "task", self.state.task_id,
                {"error": str(exc)[:300]},
            )
            return "max_revisions_reached"

        researcher.complete_agent_run(
            run_id, status="completed", output_summary=result[:500],
        )

        log_flow_event(
            self.state.project_id, "research_revised",
            "research_review_flow", "task", self.state.task_id,
            {"revision_count": self.state.revision_count},
        )

        return "ready_for_review"

    # ── Max revisions ─────────────────────────────────────────────────────

    @listen("max_revisions_reached")
    def handle_max_revisions(self):
        """Accept best-effort research after exhausting revision attempts."""
        logger.warning(
            "ResearchReviewFlow: accepting task %d after %d failed revisions",
            self.state.task_id, self.state.revision_count,
        )
        update_task_status(self.state.task_id, "done")

        log_flow_event(
            self.state.project_id, "research_max_revisions",
            "research_review_flow", "task", self.state.task_id,
            {"revision_count": self.state.revision_count},
        )

    # ── Validation → knowledge base update ────────────────────────────────

    @listen("validated")
    def update_knowledge_base(self):
        """Index validated findings in the knowledge base."""
        update_subflow_step(
            self.state.project_id, "research_review_flow", "update_knowledge_base",
        )
        logger.info(
            "ResearchReviewFlow: updating knowledge base for task %d",
            self.state.task_id,
        )

        self._ensure_services()

        # Resolve researcher
        task = get_task_by_id(self.state.task_id)
        researcher_id = self.state.researcher_id
        if not researcher_id and task:
            researcher_id = task.get("assigned_to", "")

        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)

        task_prompt = res_tasks.update_knowledge_base(
            self.state.task_id,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info(
                "Agent killed during update_knowledge_base for task %d",
                self.state.task_id,
            )
            raise
        except Exception as exc:
            logger.warning(
                "Engine execution failed in update_knowledge_base for task %d: %s",
                self.state.task_id, exc,
            )
            # Non-fatal: research is already validated

        update_task_status_safe(self.state.task_id, "review_ready")
        update_task_status(self.state.task_id, "done")

        log_flow_event(
            self.state.project_id, "research_completed",
            "research_review_flow", "task", self.state.task_id,
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        logger.error(
            "ResearchReviewFlow: error (task_id=%d, project_id=%d)",
            self.state.task_id, self.state.project_id,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "flow_error", "research_review_flow",
            "task", self.state.task_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"ResearchReviewFlow error: task {self.state.task_id} failed. "
            f"Please investigate.",
        )
