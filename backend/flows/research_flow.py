"""ResearchFlow — manages the research lifecycle up to artifact verification.

Lifecycle: assign → literature review → hypothesis → investigate → report → verify artifacts → hand off to ResearchReviewFlow.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method "X" completes or a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes next trigger
- Non-router return values are DATA only, not triggers
"""

from __future__ import annotations

import logging

from crewai.flow.flow import Flow, listen, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.flows.guardrails import (
    MAX_RESCUE_ATTEMPTS,
    check_research_artifacts,
)
from backend.engine import get_engine
from backend.engine.base import AgentKilledError
from backend.flows.helpers import (
    get_project_name,
    get_task_by_id,
    log_flow_event,
    notify_team_lead,
    update_task_status_safe,
)
from backend.flows.snapshot_service import update_subflow_step
from backend.flows.state_models import ResearchState
from backend.knowledge import KnowledgeService
from backend.prompts.researcher import tasks as res_tasks

logger = logging.getLogger(__name__)


@persist()
class ResearchFlow(Flow[ResearchState]):
    """Manages a research task through investigation and artifact verification."""

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

        if self.state.researcher_id:
            researcher = get_agent_by_role(
                "researcher", self.state.project_id,
                agent_id=self.state.researcher_id,
                knowledge_service=self._knowledge_service,
            )
        else:
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
        Routes to "artifacts_ok" on success or "rescue_artifacts" on
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
            return "artifacts_ok"

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
            return "artifacts_ok"
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

    # ── Hand off to ResearchReviewFlow ────────────────────────────────────

    @listen("artifacts_ok")
    def launch_peer_review(self):
        """Launch ResearchReviewFlow as an independent sub-flow.

        This decouples peer review from the research lifecycle so that
        interrupted reviews can be restarted independently.
        """
        update_subflow_step(self.state.project_id, "research_flow", "launch_peer_review")
        logger.info(
            "ResearchFlow: launching ResearchReviewFlow for task %d",
            self.state.task_id,
        )

        from backend.flows.research_review_flow import ResearchReviewFlow

        review_flow = ResearchReviewFlow()
        review_flow.kickoff(inputs={
            "project_id": self.state.project_id,
            "task_id": self.state.task_id,
            "researcher_id": self.state.researcher_id,
            "hypothesis": self.state.hypothesis,
        })

        log_flow_event(
            self.state.project_id, "research_review_completed", "research_flow",
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
