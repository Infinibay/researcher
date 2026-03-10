"""InvestigationFlow — simplified research lifecycle for information gathering.

Lifecycle: assign -> gather information -> write summary -> verify artifacts -> hand off to ResearchReviewFlow (investigation_mode).

Unlike ResearchFlow, this skips literature review, hypothesis formulation,
and deep investigation phases. It uses a Scope -> Gather -> Organize -> Summarize
methodology instead of PICO/ACH/GRADE.
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
from backend.flows.state_models import InvestigationState
from backend.knowledge import KnowledgeService
from backend.prompts.researcher import tasks as res_tasks

logger = logging.getLogger(__name__)


@persist()
class InvestigationFlow(Flow[InvestigationState]):
    """Manages an investigation task through information gathering and summarization."""

    # -- Service helpers ---------------------------------------------------

    def _ensure_services(self) -> None:
        """Ensure knowledge service is initialised."""
        if self.state.knowledge_service_enabled:
            if not getattr(self, "_knowledge_service", None):
                self._knowledge_service = KnowledgeService()
        else:
            self._knowledge_service = None

    # -- Start -------------------------------------------------------------

    @start()
    def assign_investigation(self):
        """Load task and assign to researcher."""
        update_subflow_step(self.state.project_id, "investigation_flow", "assign_investigation")
        logger.info("InvestigationFlow: assign_investigation (task_id=%d)", self.state.task_id)

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

        update_task_status_safe(self.state.task_id, "in_progress")

        task_prompt = res_tasks.assign_investigation(
            self.state.task_id, self.state.task_title,
            task.get("description", ""),
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during assign_investigation for task %d", self.state.task_id)
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in assign_investigation for task %d", self.state.task_id)
            log_flow_event(
                self.state.project_id, "investigation_assignment_failed", "investigation_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"InvestigationFlow error: task {self.state.task_id} assignment failed.",
            )
            raise

        log_flow_event(
            self.state.project_id, "investigation_assigned", "investigation_flow",
            "task", self.state.task_id,
            {"researcher_id": self.state.researcher_id},
        )

    @router("assign_investigation")
    def route_assignment(self):
        """Route based on task assignment result."""
        if not self.state.task_title:
            return "error"
        return "task_assigned"

    # -- Information gathering ---------------------------------------------

    @listen("task_assigned")
    def gather_information(self):
        """Researcher gathers information across all scope areas."""
        update_subflow_step(self.state.project_id, "investigation_flow", "gather_information")
        logger.info("InvestigationFlow: gather_information for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.gather_information(
            self.state.task_id, self.state.task_title,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during gather_information for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in gather_information for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "information_gathering_failed", "investigation_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"InvestigationFlow error: task {self.state.task_id} information gathering failed.",
            )
            raise

        researcher.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        log_flow_event(
            self.state.project_id, "information_gathered", "investigation_flow",
            "task", self.state.task_id,
        )

    @router("gather_information")
    def route_after_gathering(self):
        """Route to summary writing after gathering completes."""
        return "ready_for_summary"

    # -- Summary writing ---------------------------------------------------

    @listen("ready_for_summary")
    def write_summary(self):
        """Researcher writes investigation summary report."""
        update_subflow_step(self.state.project_id, "investigation_flow", "write_summary")
        logger.info("InvestigationFlow: write_summary for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        task_prompt = res_tasks.write_investigation_summary(
            self.state.task_id, self.state.task_title,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        try:
            result = get_engine().execute(researcher, task_prompt)
        except AgentKilledError:
            logger.info("Agent killed during write_summary for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="interrupted")
            raise
        except Exception as exc:
            logger.exception("Engine execution failed in write_summary for task %d", self.state.task_id)
            researcher.complete_agent_run(run_id, status="failed", error_class=type(exc).__name__)
            log_flow_event(
                self.state.project_id, "summary_writing_failed", "investigation_flow",
                "task", self.state.task_id, {"error": str(exc)[:300]},
            )
            update_task_status_safe(self.state.task_id, "failed")
            notify_team_lead(
                self.state.project_id, "system",
                f"InvestigationFlow error: task {self.state.task_id} summary writing failed.",
            )
            raise

        self.state.report_path = result
        researcher.complete_agent_run(run_id, status="completed", output_summary=result[:500])

        log_flow_event(
            self.state.project_id, "summary_written", "investigation_flow",
            "task", self.state.task_id,
        )

    # -- Artifact guardrail ------------------------------------------------

    @router("write_summary")
    def verify_artifacts(self):
        """Check that findings and report exist before peer review."""
        counts = check_research_artifacts(
            self.state.project_id, self.state.task_id,
        )
        logger.info(
            "InvestigationFlow: verify_artifacts task=%d findings=%d reports=%d",
            self.state.task_id, counts["findings"], counts["reports"],
        )

        if counts["findings"] > 0 and counts["reports"] > 0:
            self.state.rescue_count = 0
            return "artifacts_ok"

        if self.state.rescue_count >= MAX_RESCUE_ATTEMPTS:
            logger.warning(
                "InvestigationFlow: artifacts still missing after %d rescue attempts "
                "for task %d -- giving up",
                self.state.rescue_count, self.state.task_id,
            )
            return "artifacts_unrecoverable"

        return "rescue_artifacts"

    @router("rescue_artifacts")
    def rescue_missing_artifacts(self):
        """Re-invoke the researcher with a direct rescue prompt."""
        self.state.rescue_count += 1
        logger.info(
            "InvestigationFlow: rescue attempt %d/%d for task %d",
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
            self.state.project_id, "artifact_rescue_attempted", "investigation_flow",
            "task", self.state.task_id,
            {"rescue_count": self.state.rescue_count,
             "missing_findings": counts["findings"] == 0,
             "missing_report": counts["reports"] == 0},
        )

        # Re-check
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
            "InvestigationFlow: task %d failed -- researcher could not produce "
            "artifacts after %d rescue attempts",
            self.state.task_id, self.state.rescue_count,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "investigation_artifacts_missing", "investigation_flow",
            "task", self.state.task_id,
            {"rescue_attempts": self.state.rescue_count},
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"Investigation task {self.state.task_id} failed: the researcher could "
            f"not produce findings or a report after {self.state.rescue_count} "
            f"rescue attempts. The model may not be calling tools reliably.",
        )

    # -- Hand off to ResearchReviewFlow (investigation mode) ---------------

    @listen("artifacts_ok")
    def launch_peer_review(self):
        """Launch ResearchReviewFlow with investigation_mode=True."""
        update_subflow_step(self.state.project_id, "investigation_flow", "launch_peer_review")
        logger.info(
            "InvestigationFlow: launching ResearchReviewFlow (investigation_mode) for task %d",
            self.state.task_id,
        )

        from backend.flows.research_review_flow import ResearchReviewFlow

        review_flow = ResearchReviewFlow()
        review_flow.kickoff(inputs={
            "project_id": self.state.project_id,
            "task_id": self.state.task_id,
            "researcher_id": self.state.researcher_id,
            "hypothesis": "",
            "investigation_mode": True,
        })

        log_flow_event(
            self.state.project_id, "investigation_review_completed", "investigation_flow",
            "task", self.state.task_id,
        )

    # -- Error handling ----------------------------------------------------

    @listen("error")
    def handle_error(self):
        """Handle flow errors: mark task as failed, notify team lead."""
        logger.error(
            "InvestigationFlow: error state reached (task_id=%d, project_id=%d)",
            self.state.task_id, self.state.project_id,
        )
        update_task_status_safe(self.state.task_id, "failed")
        log_flow_event(
            self.state.project_id, "flow_error", "investigation_flow",
            "task", self.state.task_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"InvestigationFlow error: task {self.state.task_id} failed unexpectedly. "
            f"Please investigate.",
        )
