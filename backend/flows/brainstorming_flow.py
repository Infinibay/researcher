"""BrainstormingFlow — time-limited ideation sessions with multi-agent participation.

Lifecycle: start session → brainstorm phase (15 min) → consolidate → decision phase (5 min) →
           select ideas → present to user → create tasks.

CrewAI Flow routing rules (v1.9.3):
- @listen("X") triggers when method "X" completes or a router returns "X"
- @router("X") triggers when method "X" completes; return value becomes next trigger
- Non-router return values are DATA only, not triggers
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from crewai.flow.flow import Flow, listen, or_, router, start
from crewai.flow.persistence import persist

from backend.agents.registry import get_agent_by_role
from backend.flows.guardrails import validate_brainstorm_task_creation
from backend.flows.helpers import (
    calculate_time_elapsed,
    classify_approval_response,
    format_ideas,
    load_project_state,
    log_flow_event,
    notify_team_lead,
    parse_ideas,
    run_agent_task,
)
from backend.flows.snapshot_service import update_subflow_step
from backend.flows.state_models import BrainstormPhase, BrainstormState
from backend.prompts.project_lead import tasks as pl_tasks
from backend.prompts.shared import brainstorm_round
from backend.prompts.team_lead import tasks as tl_tasks

logger = logging.getLogger(__name__)


@persist()
class BrainstormingFlow(Flow[BrainstormState]):
    """Manages time-limited brainstorming sessions with multiple agents."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def start_session(self):
        """Configure participants and start the brainstorming session."""
        update_subflow_step(self.state.project_id, "brainstorming_flow", "start_session")
        logger.info(
            "BrainstormingFlow: start_session (project_id=%d)",
            self.state.project_id,
        )

        # Load project context for richer brainstorming prompts
        try:
            project = load_project_state(self.state.project_id)
            if project:
                self.state.project_name = project.get("name", "")
                self.state.project_description = project.get("description", "") or ""
                metadata = json.loads(project.get("metadata_json") or "{}")
                self.state.project_type = metadata.get("project_type", "development")
        except Exception:
            logger.warning(
                "BrainstormingFlow: could not load project context for project %d, "
                "using defaults",
                self.state.project_id,
                exc_info=True,
            )

        self.state.participants = [
            "team_lead", "developer", "researcher",
        ]
        self.state.start_time = datetime.now(timezone.utc).isoformat()
        self.state.phase = BrainstormPhase.BRAINSTORM
        self.state.round_count = 0

        # Create a brainstorming thread for chat visibility
        from backend.communication.thread_manager import ThreadManager
        tm = ThreadManager()
        self.state.thread_id = tm.create_thread(
            project_id=self.state.project_id,
            thread_type="brainstorming",
            participants=self.state.participants,
        )

        log_flow_event(
            self.state.project_id, "brainstorm_started", "brainstorming_flow",
            "project", self.state.project_id,
            {"participants": self.state.participants},
        )

    # ── Brainstorm phase ──────────────────────────────────────────────────

    @router(or_("start_session", "continue_brainstorm_bridge", "reset_for_new_round"))
    def brainstorm_phase(self):
        """Each agent proposes ideas within the time limit.

        Routes to "brainstorm_time_up" or "continue_brainstorm" for more rounds.
        """
        logger.info(
            "BrainstormingFlow: brainstorm_phase (round %d/%d)",
            self.state.round_count + 1, self.state.max_rounds,
        )

        elapsed = calculate_time_elapsed(self.state.start_time)
        if elapsed >= self.state.time_limit_brainstorm:
            logger.info("BrainstormingFlow: brainstorm time limit reached")
            return "brainstorm_time_up"

        self.state.round_count += 1
        if self.state.round_count > self.state.max_rounds:
            logger.info("BrainstormingFlow: max rounds reached")
            return "brainstorm_time_up"

        # Collect existing ideas for context
        existing = ""
        if self.state.ideas:
            existing = (
                f"\n\nPrevious ideas proposed:\n"
                f"{format_ideas(self.state.ideas, numbered=False)}\n"
            )

        self._collect_ideas_from_participants(existing)

        # Check time again
        elapsed = calculate_time_elapsed(self.state.start_time)
        if elapsed >= self.state.time_limit_brainstorm:
            return "brainstorm_time_up"

        if self.state.round_count < self.state.max_rounds:
            return "continue_brainstorm"

        return "brainstorm_time_up"

    def _collect_ideas_from_participants(self, existing: str) -> None:
        """Run one brainstorm round: each participant proposes ideas and appends them to state."""
        for role in self.state.participants:
            agent = get_agent_by_role(role, self.state.project_id)
            result = run_agent_task(agent, brainstorm_round(
                round_count=self.state.round_count,
                project_name=self.state.project_name,
                project_description=self.state.project_description,
                project_type=self.state.project_type,
                existing_ideas=existing,
                user_feedback=self.state.user_feedback,
            ))

            new_ideas = parse_ideas(result)
            for idea in new_ideas:
                idea["proposed_by"] = role
                idea["round"] = self.state.round_count
            self.state.ideas.extend(new_ideas)

            # Post ideas to the brainstorming thread for chat visibility
            if self.state.thread_id and result:
                from backend.flows.helpers.messaging import send_agent_message
                send_agent_message(
                    project_id=self.state.project_id,
                    from_agent=agent.agent_id,
                    to_agent=None,
                    to_role=None,
                    message=result,
                    conversation_type="broadcast",
                    thread_id=self.state.thread_id,
                )

    @listen("continue_brainstorm")
    def continue_brainstorm_bridge(self):
        """No-op bridge required by CrewAI's ``or_()`` routing pattern.

        ``brainstorm_phase`` is a ``@router`` and cannot listen to itself;
        this listener re-triggers it after each ``'continue_brainstorm'`` signal.
        """
        pass

    # ── Consolidation ─────────────────────────────────────────────────────

    @listen("brainstorm_time_up")
    def consolidate_ideas(self):
        """Team Lead consolidates, deduplicates, and ranks ideas."""
        update_subflow_step(self.state.project_id, "brainstorming_flow", "consolidate_ideas")
        logger.info(
            "BrainstormingFlow: consolidate_ideas (%d ideas)",
            len(self.state.ideas),
        )

        self.state.phase = BrainstormPhase.CONSOLIDATION

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        ideas_text = format_ideas(
            self.state.ideas, numbered=False, include_attribution=True,
        )
        result = run_agent_task(team_lead, tl_tasks.consolidate_ideas(
            ideas_text,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        ))

        self.state.consolidated_ideas = parse_ideas(result)

        # Post consolidation summary to the brainstorming thread
        if self.state.thread_id and result:
            from backend.flows.helpers.messaging import send_agent_message
            send_agent_message(
                project_id=self.state.project_id,
                from_agent=team_lead.agent_id,
                to_agent=None,
                to_role=None,
                message=result,
                conversation_type="broadcast",
                thread_id=self.state.thread_id,
            )

        log_flow_event(
            self.state.project_id, "ideas_consolidated", "brainstorming_flow",
            "project", self.state.project_id,
            {"consolidated_count": len(self.state.consolidated_ideas)},
        )

    # ── Decision phase ────────────────────────────────────────────────────

    @listen("consolidate_ideas")
    def decision_phase(self):
        """Agents discuss and vote on consolidated ideas within the time limit."""
        update_subflow_step(self.state.project_id, "brainstorming_flow", "decision_phase")
        logger.info("BrainstormingFlow: decision_phase")

        self.state.phase = BrainstormPhase.DECISION
        self.state.decision_start_time = datetime.now(timezone.utc).isoformat()

        consolidated_text = format_ideas(self.state.consolidated_ideas)

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        result = run_agent_task(team_lead, tl_tasks.select_ideas(
            consolidated_text,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        ))

        self.state.selected_ideas = parse_ideas(result)

        # Post selected ideas to the brainstorming thread
        if self.state.thread_id and result:
            from backend.flows.helpers.messaging import send_agent_message
            send_agent_message(
                project_id=self.state.project_id,
                from_agent=team_lead.agent_id,
                to_agent=None,
                to_role=None,
                message=result,
                conversation_type="broadcast",
                thread_id=self.state.thread_id,
            )

        # Check decision time limit
        elapsed = calculate_time_elapsed(self.state.decision_start_time)
        if elapsed >= self.state.time_limit_decision:
            logger.warning(
                "BrainstormingFlow: decision time limit reached (%.0fs >= %ds)",
                elapsed, self.state.time_limit_decision,
            )
            # If no ideas selected, take top consolidated as fallback
            if not self.state.selected_ideas and self.state.consolidated_ideas:
                self.state.selected_ideas = self.state.consolidated_ideas[:3]

        log_flow_event(
            self.state.project_id, "ideas_selected", "brainstorming_flow",
            "project", self.state.project_id,
            {"selected_count": len(self.state.selected_ideas)},
        )

    # ── User presentation ─────────────────────────────────────────────────

    @router("decision_phase")
    def present_to_user(self):
        """Project Lead presents selected ideas to the user for approval."""
        logger.info("BrainstormingFlow: present_to_user")

        self.state.phase = BrainstormPhase.PRESENTATION

        from backend.prompts.team import build_conversation_context

        project_lead = get_agent_by_role("project_lead", self.state.project_id)
        ideas_text = format_ideas(self.state.selected_ideas)
        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=project_lead.agent_id,
        )
        result = run_agent_task(
            project_lead, pl_tasks.present_brainstorm_ideas(
                ideas_text,
                project_name=self.state.project_name,
                project_id=self.state.project_id,
                requirements=self.state.project_description,
                conversation_context=conv_ctx,
            ),
        ).strip()

        if classify_approval_response(result) == "approved":
            self.state.user_approved = True
            log_flow_event(
                self.state.project_id, "brainstorm_ideas_approved",
                "brainstorming_flow", "project", self.state.project_id,
            )
            return "approved"
        else:
            feedback = result
            if ":" in result:
                feedback = result.split(":", 1)[1].strip()
            self.state.user_feedback = feedback
            self.state.user_approved = False
            log_flow_event(
                self.state.project_id, "brainstorm_ideas_rejected",
                "brainstorming_flow", "project", self.state.project_id,
                {"feedback": feedback},
            )
            return "rejected"

    # ── Rejection handling ────────────────────────────────────────────────

    @router("rejected")
    def handle_rejection_router(self):
        """Check rejection attempts and route accordingly."""
        self.state.rejection_attempts += 1

        if self.state.rejection_attempts >= self.state.max_rejection_attempts:
            logger.warning(
                "BrainstormingFlow: max rejection attempts (%d) reached for project %d",
                self.state.max_rejection_attempts, self.state.project_id,
            )
            log_flow_event(
                self.state.project_id, "brainstorm_rejections_exhausted",
                "brainstorming_flow", "project", self.state.project_id,
                {"rejection_attempts": self.state.rejection_attempts},
            )
            return "rejections_exhausted"

        return "restart_brainstorm"

    @listen("restart_brainstorm")
    def reset_for_new_round(self):
        """Reset ideas, timers, and round counter for a new brainstorm cycle after user rejection."""
        logger.info(
            "BrainstormingFlow: ideas rejected (attempt %d/%d), restarting",
            self.state.rejection_attempts, self.state.max_rejection_attempts,
        )

        self.state.ideas = []
        self.state.consolidated_ideas = []
        self.state.selected_ideas = []
        self.state.round_count = 0
        self.state.start_time = datetime.now(timezone.utc).isoformat()
        self.state.phase = BrainstormPhase.BRAINSTORM

        log_flow_event(
            self.state.project_id, "brainstorm_restarted", "brainstorming_flow",
            "project", self.state.project_id,
            {"feedback": self.state.user_feedback},
        )

    @listen("rejections_exhausted")
    def handle_rejections_exhausted(self):
        """Flow ends — brainstorming produced no approved results."""
        logger.warning(
            "BrainstormingFlow: all rejection attempts exhausted for project %d",
            self.state.project_id,
        )

    # ── Task creation from approved ideas ─────────────────────────────────

    @listen("approved")
    def create_tasks_from_ideas(self):
        """Team Lead creates epics/milestones/tasks from approved ideas."""
        update_subflow_step(self.state.project_id, "brainstorming_flow", "create_tasks_from_ideas")
        logger.info(
            "BrainstormingFlow: create_tasks_from_ideas (%d ideas)",
            len(self.state.selected_ideas),
        )

        self.state.phase = BrainstormPhase.COMPLETE

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        ideas_text = format_ideas(self.state.selected_ideas)
        result = run_agent_task(
            team_lead,
            tl_tasks.create_tasks_from_ideas(self.state.project_id, ideas_text),

            guardrail=validate_brainstorm_task_creation(self.state.project_id),
            guardrail_max_retries=3,
        )

        log_flow_event(
            self.state.project_id, "brainstorm_tasks_created", "brainstorming_flow",
            "project", self.state.project_id,
            {"result": str(result)[:500]},
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: log and notify."""
        logger.error(
            "BrainstormingFlow: error state reached (project_id=%d)",
            self.state.project_id,
        )
        log_flow_event(
            self.state.project_id, "flow_error", "brainstorming_flow",
            "project", self.state.project_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"BrainstormingFlow error for project {self.state.project_id}. "
            f"Please investigate.",
        )
