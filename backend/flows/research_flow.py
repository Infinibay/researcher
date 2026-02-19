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

from crewai import Crew, Task
from crewai.flow.flow import Flow, listen, or_, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role, get_available_agent_by_role
from backend.flows.helpers import (
    get_task_by_id,
    log_flow_event,
    notify_team_lead,
    parse_review_result,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.state_models import ResearchState
from backend.knowledge import AgentMemoryService, KnowledgeService
from backend.prompts.research_reviewer import tasks as rr_tasks
from backend.prompts.researcher import tasks as res_tasks

logger = logging.getLogger(__name__)


@persist()
class ResearchFlow(Flow[ResearchState]):
    """Manages a research task through investigation and peer review."""

    # ── Service helpers ───────────────────────────────────────────────────

    def _ensure_services(self) -> None:
        """Ensure knowledge and memory services are initialised."""
        if self.state.knowledge_service_enabled:
            if not getattr(self, "_knowledge_service", None):
                self._knowledge_service = KnowledgeService()
            if not getattr(self, "_memory_service", None):
                self._memory_service = AgentMemoryService()
        else:
            self._knowledge_service = None
            self._memory_service = None

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def assign_research(self):
        """Load task and assign to researcher."""
        logger.info("ResearchFlow: assign_research (task_id=%d)", self.state.task_id)

        self._ensure_services()

        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return

        self.state.task_title = task.get("title", "")

        researcher = get_available_agent_by_role(
            "researcher", self.state.project_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        self.state.researcher_id = researcher.agent_id
        researcher.activate_context(task_id=self.state.task_id)

        desc, expected = res_tasks.assign_research(
            self.state.task_id, self.state.task_title,
            task.get("description", ""),
        )
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        crew.kickoff()

        update_task_status(self.state.task_id, "in_progress")

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
        logger.info("ResearchFlow: literature_review for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        desc, expected = res_tasks.literature_review(
            self.state.task_id, self.state.task_title,
        )
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()

        researcher.complete_agent_run(run_id, status="completed", output_summary=str(result)[:500])

        log_flow_event(
            self.state.project_id, "literature_reviewed", "research_flow",
            "task", self.state.task_id,
        )

    # ── Hypothesis formulation ────────────────────────────────────────────

    @listen("literature_review")
    def formulate_hypothesis(self):
        """Researcher formulates a hypothesis based on literature review."""
        logger.info("ResearchFlow: formulate_hypothesis for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        researcher.activate_context(task_id=self.state.task_id)

        desc, expected = res_tasks.formulate_hypothesis(
            self.state.task_id, self.state.task_title,
        )
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()
        self.state.hypothesis = str(result)

        log_flow_event(
            self.state.project_id, "hypothesis_created", "research_flow",
            "task", self.state.task_id,
        )

    # ── Investigation ─────────────────────────────────────────────────────

    @listen("formulate_hypothesis")
    def investigate(self):
        """Researcher conducts in-depth investigation."""
        logger.info("ResearchFlow: investigate for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        desc, expected = res_tasks.investigate(
            self.state.task_id, self.state.task_title,
            self.state.hypothesis,
        )
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        try:
            result = crew.kickoff()
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

    # ── Report writing ────────────────────────────────────────────────────

    @listen(or_("investigate", "revise_research"))
    def write_report(self):
        """Researcher writes a structured research report."""
        logger.info("ResearchFlow: write_report for task %d", self.state.task_id)

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        researcher.activate_context(task_id=self.state.task_id)

        desc, expected = res_tasks.write_report(
            self.state.task_id, self.state.task_title,
            self.state.hypothesis,
        )
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()
        self.state.report_path = str(result)

        log_flow_event(
            self.state.project_id, "report_written", "research_flow",
            "task", self.state.task_id,
        )

    # ── Peer review ───────────────────────────────────────────────────────

    @listen("write_report")
    def request_peer_review(self):
        """Research Reviewer evaluates the findings and methodology."""
        logger.info("ResearchFlow: request_peer_review for task %d", self.state.task_id)

        self._ensure_services()
        reviewer = get_available_agent_by_role(
            "research_reviewer", self.state.project_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        reviewer.activate_context(task_id=self.state.task_id)
        run_id = reviewer.create_agent_run(self.state.task_id)

        desc, expected = rr_tasks.peer_review(
            self.state.task_id, self.state.task_title,
            project_id=self.state.project_id,
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

    @listen("rejected")
    def revise_research(self):
        """Researcher revises findings based on peer review feedback.

        Triggers "revise_research" → write_report via or_().
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
            memory_service=self._memory_service,
        )
        researcher.activate_context(task_id=self.state.task_id)
        run_id = researcher.create_agent_run(self.state.task_id)

        desc, expected = res_tasks.revise_research(
            self.state.task_id,
            reviewer_feedback=self.state.last_reviewer_feedback,
        )
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()

        researcher.complete_agent_run(run_id, status="completed", output_summary=str(result)[:500])

        log_flow_event(
            self.state.project_id, "research_revised", "research_flow",
            "task", self.state.task_id,
            {"revision_count": self.state.revision_count},
        )

    @listen("max_revisions_reached")
    def handle_max_revisions(self):
        """Accept best-effort research after exhausting all revision attempts."""
        logger.warning(
            "ResearchFlow: accepting task %d after %d failed revisions",
            self.state.task_id, self.state.revision_count,
        )

        self._ensure_services()

        if self._memory_service is not None:
            researcher = get_agent_by_role(
                "researcher", self.state.project_id,
                knowledge_service=self._knowledge_service,
                memory_service=self._memory_service,
            )
            self._memory_service.persist_agent_memory(
                self.state.researcher_id,
                f"Research for task {self.state.task_id} could not pass peer review "
                f"after {self.state.revision_count} revisions. "
                f"Last hypothesis: {self.state.hypothesis[:500]}",
            )

        update_task_status(self.state.task_id, "done")

        log_flow_event(
            self.state.project_id, "research_max_revisions", "research_flow",
            "task", self.state.task_id,
            {"revision_count": self.state.revision_count},
        )

    # ── Validation and knowledge base update ──────────────────────────────

    @listen("validated")
    def update_knowledge_base(self):
        """Index validated findings in the knowledge base."""
        logger.info(
            "ResearchFlow: updating knowledge base for task %d", self.state.task_id,
        )

        self._ensure_services()
        researcher = get_agent_by_role(
            "researcher", self.state.project_id,
            agent_id=self.state.researcher_id,
            knowledge_service=self._knowledge_service,
            memory_service=self._memory_service,
        )
        researcher.activate_context(task_id=self.state.task_id)

        desc, expected = res_tasks.update_knowledge_base(self.state.task_id)
        crew = Crew(
            agents=[researcher.crewai_agent],
            tasks=[Task(
                description=desc,
                agent=researcher.crewai_agent,
                expected_output=expected,
            )],
            verbose=True,
        )
        result = crew.kickoff()

        if self._memory_service is not None:
            self._memory_service.persist_agent_memory(
                self.state.researcher_id,
                str(result)[:2000],
            )

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
