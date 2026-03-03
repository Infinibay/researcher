"""ResearchFlow — manages the research lifecycle with peer review.

Lifecycle: assign → literature review → hypothesis → investigate → report → peer review → validate.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method "X" completes or a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes next trigger
- Non-router return values are DATA only, not triggers
"""

from __future__ import annotations

import logging
from typing import Any

from crewai.flow.flow import Flow, listen, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.flows.guardrails import (
    MAX_RESCUE_ATTEMPTS,
    check_research_artifacts,
    validate_research_review_verdict,
)
from backend.engine import get_engine
from backend.engine.base import AgentKilledError
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
from backend.flows.state_models import ResearchState
from backend.knowledge import KnowledgeService
from backend.prompts.research_reviewer import tasks as rr_tasks
from backend.prompts.researcher import tasks as res_tasks

logger = logging.getLogger(__name__)


@persist()
class ResearchFlow(Flow[ResearchState]):
    """Manages a research task through investigation and peer review."""

    # ── Service helpers ───────────────────────────────────────────────────

    def _ensure_services(self) -> None:
        """Ensure knowledge service is initialised."""
        if self.state.knowledge_service_enabled:
            if not getattr(self, "_knowledge_service", None):
                self._knowledge_service = KnowledgeService()
        else:
            self._knowledge_service = None

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def assign_research(self):
        """Load task and assign to researcher."""
        update_subflow_step(self.state.project_id, "research_flow", "assign_research")
        logger.info("ResearchFlow: assign_research (task_id=%d)", self.state.task_id)

        self._ensure_services()

        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return

        self.state.task_title = task.get("title", "")
        if not self.state.project_name:
            self.state.project_name = get_project_name(self.state.project_id)

        researcher = get_available_agent_by_role(
            "researcher", self.state.project_id,
            knowledge_service=self._knowledge_service,
        )
        self.state.researcher_id = researcher.agent_id
        researcher.activate_context(task_id=self.state.task_id)

        # Move to in_progress BEFORE the crew runs — the agent may advance
        # the task further (e.g. to review_ready) during kickoff.
        update_task_status_safe(self.state.task_id, "in_progress")

        task_prompt = res_tasks.assign_research(
            self.state.task_id, self.state.task_title,
            task.get("description", ""),
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during assign_research for task %d", self.state.task_id)
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in assign_research for task %d", self.state.task_id)
            log_flow_event(
                self.state.project_id, "research_assignment_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchFlow error: task {self.state.task_id} assignment failed.",
            )
            raise

        log_flow_event(
            self.state.project_id, "research_assigned", "research_flow",
            "task", self.state.task_id,
            {"researcher_id": self.state.researcher_id},
        )

    @router("assign_research")
    def route_assignment(self):
        """Route based on task assignment result."""
        if not self.state.task_title:
            return "error"
        return "task_assigned"

    # ── Literature review ─────────────────────────────────────────────────

    @listen("task_assigned")
    def literature_review(self):
        """Researcher searches for relevant papers and references."""
        update_subflow_step(self.state.project_id, "research_flow", "literature_review")
        logger.info("ResearchFlow: literature_review for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.literature_review(
            self.state.task_id, self.state.task_title,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during literature_review for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in literature_review for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "literature_review_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchFlow error: task {self.state.task_id} literature review failed.",
            )
            raise

        researcher.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        log_flow_event(
            self.state.project_id, "literature_reviewed", "research_flow",
            "task", self.state.task_id,
        )

    # ── Hypothesis formulation ────────────────────────────────────────────

    @listen("literature_review")
    def formulate_hypothesis(self):
        """Researcher formulates a hypothesis based on literature review."""
        update_subflow_step(self.state.project_id, "research_flow", "formulate_hypothesis")
        logger.info("ResearchFlow: formulate_hypothesis for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.formulate_hypothesis(
            self.state.task_id, self.state.task_title,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during formulate_hypothesis for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in formulate_hypothesis for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "hypothesis_formulation_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchFlow error: task {self.state.task_id} hypothesis formulation failed.",
            )
            raise

        self.state.hypothesis = result
        researcher.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        log_flow_event(
            self.state.project_id, "hypothesis_created", "research_flow",
            "task", self.state.task_id,
        )

    # ── Investigation ─────────────────────────────────────────────────────

    @listen("formulate_hypothesis")
    def investigate(self):
        """Researcher conducts in-depth investigation."""
        update_subflow_step(self.state.project_id, "research_flow", "investigate")
        logger.info("ResearchFlow: investigate for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.investigate(
            self.state.task_id, self.state.task_title,
            self.state.hypothesis,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during investigate for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Crew execution failed in investigate for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "investigation_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchFlow error: task {self.state.task_id} investigation failed.",
            )
            raise  # Prevent downstream listeners

        researcher.complete_agent_run(run_id, status="completed", output_summary=str(result)[:500])

        log_flow_event(
            self.state.project_id, "findings_recorded", "research_flow",
            "task", self.state.task_id,
        )

    @router("investigate")
    def route_after_investigation(self):
        """Route to report writing after investigation completes."""
        return "ready_for_report"

    # ── Report writing ────────────────────────────────────────────────────

    @listen("ready_for_report")
    def write_report(self):
        """Researcher writes a structured research report."""
        update_subflow_step(self.state.project_id, "research_flow", "write_report")
        logger.info("ResearchFlow: write_report for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.write_report(
            self.state.task_id, self.state.task_title,
            self.state.hypothesis,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during write_report for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in write_report for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "report_writing_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchFlow error: task {self.state.task_id} report writing failed.",
            )
            raise

        self.state.report_path = result
        researcher.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        log_flow_event(
            self.state.project_id, "report_written", "research_flow",
            "task", self.state.task_id,
        )

    # ── Artifact guardrail ─────────────────────────────────────────────────

    @router("write_report")
    def verify_artifacts(self):
        """Check that findings and report exist in DB before peer review.

        If artifacts are missing, invoke a rescue prompt that tells the
        researcher to call RecordFindingTool/WriteReportTool immediately.
        Routes to "peer_review_ready" on success or "rescue_artifacts" on
        missing artifacts.  After MAX_RESCUE_ATTEMPTS failures, routes to
        "artifacts_unrecoverable".
        """
        counts = check_research_artifacts(
            self.state.project_id, self.state.task_id,
        )
        logger.info(
            "ResearchFlow: verify_artifacts task=%d findings=%d reports=%d",
            self.state.task_id, counts["findings"], counts["reports"],
        )

        if counts["findings"] > 0 and counts["reports"] > 0:
            self.state.rescue_count = 0
            return "peer_review_ready"

        if self.state.rescue_count >= MAX_RESCUE_ATTEMPTS:
            logger.warning(
                "ResearchFlow: artifacts still missing after %d rescue attempts "
                "for task %d — giving up",
                self.state.rescue_count, self.state.task_id,
            )
            return "artifacts_unrecoverable"

        return "rescue_artifacts"

    @router("rescue_artifacts")
    def rescue_missing_artifacts(self):
        """Re-invoke the researcher with a direct rescue prompt."""
        self.state.rescue_count += 1
        logger.info(
            "ResearchFlow: rescue attempt %d/%d for task %d",
            self.state.rescue_count, MAX_RESCUE_ATTEMPTS, self.state.task_id,
        )

        counts = check_research_artifacts(
            self.state.project_id, self.state.task_id,
        )

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.rescue_missing_artifacts(
            self.state.task_id, self.state.task_title,
            missing_findings=counts["findings"] == 0,
            missing_report=counts["reports"] == 0,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during rescue_missing_artifacts for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in rescue_missing_artifacts for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            return "artifacts_unrecoverable"

        researcher.complete_agent_run(
            run_id, status="completed", output_summary=result[:500],
        )

        log_flow_event(
            self.state.project_id, "artifact_rescue_attempted", "research_flow",
            "task", self.state.task_id,
            {"rescue_count": self.state.rescue_count,
             "missing_findings": counts["findings"] == 0,
             "missing_report": counts["reports"] == 0},
        )

        # Re-check — route back to verify_artifacts logic inline
        new_counts = check_research_artifacts(
            self.state.project_id, self.state.task_id,
        )
        if new_counts["findings"] > 0 and new_counts["reports"] > 0:
            return "peer_review_ready"
        if self.state.rescue_count >= MAX_RESCUE_ATTEMPTS:
            return "artifacts_unrecoverable"
        return "rescue_artifacts"

    @listen("artifacts_unrecoverable")
    def handle_unrecoverable_artifacts(self):
        """Mark task as failed when researcher cannot produce artifacts."""
        logger.error(
            "ResearchFlow: task %d failed — researcher could not produce "
            "artifacts after %d rescue attempts",
            self.state.task_id, self.state.rescue_count,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "research_artifacts_missing", "research_flow",
            "task", self.state.task_id,
            {"rescue_attempts": self.state.rescue_count},
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"Research task {self.state.task_id} failed: the researcher could "
            f"not produce findings or a report after {self.state.rescue_count} "
            f"rescue attempts. The model may not be calling tools reliably.",
        )

    # ── Peer review ───────────────────────────────────────────────────────

    @listen("peer_review_ready")
    def request_peer_review(self):
        """Research Reviewer evaluates the findings and methodology."""
        update_subflow_step(self.state.project_id, "research_flow", "request_peer_review")
        logger.info("ResearchFlow: request_peer_review for task %d", self.state.task_id)

        # Ensure task is in review_ready before peer review — the researcher
        # prompt tells the agent to call UpdateTaskStatusTool, but if the
        # agent skipped it, the state machine would block the later done
        # transition.
        update_task_status_safe(self.state.task_id, "review_ready")

        self._ensure_services()
        reviewer = get_available_agent_by_role(
            "research_reviewer", self.state.project_id,
            knowledge_service=self._knowledge_service,
        )
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
            logger.exception("Crew execution failed in peer_review for task %d", self.state.task_id)
            reviewer.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "peer_review_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"ResearchFlow error: task {self.state.task_id} peer review failed.",
            )
            raise

        reviewer.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        if parse_review_result(result, approve_keyword="VALIDATED") == "approved":
            self.state.validated = True
            self.state.peer_review_status = "validated"
            self.state.last_reviewer_feedback = ""
        else:
            self.state.validated = False
            self.state.peer_review_status = "rejected"
            # Extract feedback text after "REJECTED:" prefix
            upper_result = result.upper()
            rejected_idx = upper_result.find("REJECTED:")
            if rejected_idx != -1:
                self.state.last_reviewer_feedback = result[rejected_idx + len("REJECTED:"):].strip()
            else:
                self.state.last_reviewer_feedback = result

        log_flow_event(
            self.state.project_id, "peer_review_done", "research_flow",
            "task", self.state.task_id,
            {"validated": self.state.validated},
        )

    @router("request_peer_review")
    def peer_review_router(self):
        """Route based on peer review outcome."""
        if self.state.validated:
            return "validated"

        self.state.revision_count += 1
        if self.state.revision_count >= self.state.max_revisions:
            logger.warning(
                "ResearchFlow: max revisions (%d) reached for task %d",
                self.state.max_revisions, self.state.task_id,
            )
            return "max_revisions_reached"

        return "rejected"

    # ── Rejection handling ────────────────────────────────────────────────

    @router("rejected")
    def revise_research(self):
        """Researcher revises findings based on peer review feedback.

        Returns "ready_for_report" → write_report.
        """
        logger.info(
            "ResearchFlow: revise_research for task %d (revision %d/%d)",
            self.state.task_id, self.state.revision_count, self.state.max_revisions,
        )

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
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
            logger.info("Agent killed during revise_research for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception(
                "Crew execution failed in revise_research for task %d", self.state.task_id,
            )
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "rework_failed", "research_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            # Accept best-effort instead of crashing the entire flow
            return "max_revisions_reached"

        researcher.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        log_flow_event(
            self.state.project_id, "research_revised", "research_flow",
            "task", self.state.task_id,
            {"revision_count": self.state.revision_count},
        )

        return "ready_for_report"

    @listen("max_revisions_reached")
    def handle_max_revisions(self):
        """Accept best-effort research after exhausting all revision attempts."""
        logger.warning(
            "ResearchFlow: accepting task %d after %d failed revisions",
            self.state.task_id, self.state.revision_count,
        )

        update_task_status(self.state.task_id, "done")

        log_flow_event(
            self.state.project_id, "research_max_revisions", "research_flow",
            "task", self.state.task_id,
            {
                "revision_count": self.state.revision_count,
                "hypothesis": self.state.hypothesis[:500],
            },
        )

    # ── Validation and knowledge base update ──────────────────────────────

    @listen("validated")
    def update_knowledge_base(self):
        """Index validated findings in the knowledge base."""
        update_subflow_step(self.state.project_id, "research_flow", "update_knowledge_base")
        logger.info(
            "ResearchFlow: updating knowledge base for task %d", self.state.task_id,
        )

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
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
            logger.info("Agent killed during update_knowledge_base for task %d", self.state.task_id)
            raise
        except Exception as exc:
            logger.warning(
                "Engine execution failed in update_knowledge_base for task %d: %s",
                self.state.task_id, exc,
            )
            # Non-fatal: the research is already validated, proceed to mark done

        # Ensure review_ready before done — the researcher agent may have
        # already moved it, so use _safe to tolerate no-op transitions.
        update_task_status_safe(self.state.task_id, "review_ready")
        update_task_status(self.state.task_id, "done")

        log_flow_event(
            self.state.project_id, "research_completed", "research_flow",
            "task", self.state.task_id,
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: mark task as failed, notify team lead."""
        logger.error(
            "ResearchFlow: error state reached (task_id=%d, project_id=%d)",
            self.state.task_id, self.state.project_id,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "flow_error", "research_flow",
            "task", self.state.task_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"ResearchFlow error: task {self.state.task_id} failed unexpectedly. "
            f"Please investigate.",
        )
