"""TicketCreationFlow — iterative ticket creation with per-ticket research.

Lifecycle: initialize → create epics/milestones → loop(create single ticket) →
           set dependencies → done.

Each task ticket gets its own Crew run so the Team Lead can research the
codebase, wiki, findings, and web before writing the description.

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

from backend.agents.registry import get_agent_by_role
from backend.flows.event_listeners import FlowEvent, event_bus
from backend.flows.guardrails import validate_ticket_creation
from backend.engine import get_engine
from backend.flows.helpers import (
    log_flow_event,
    notify_team_lead,
    parse_created_task_id,
    parse_epics_milestones_from_result,
    parse_plan_tasks,
)
from backend.flows.snapshot_service import update_subflow_step
from backend.flows.state_models import TicketCreationState
from backend.prompts.team_lead import tasks as tl_tasks

logger = logging.getLogger(__name__)


@persist()
class TicketCreationFlow(Flow[TicketCreationState]):
    """Creates project structure iteratively: epics/milestones first, then
    one task at a time with full research, then dependencies."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def initialize(self):
        """Load inputs and extract task titles from the plan."""
        update_subflow_step(self.state.project_id, "ticket_creation_flow", "initialize")
        logger.info(
            "TicketCreationFlow: initialize (project_id=%d)",
            self.state.project_id,
        )

        self.state.task_titles = parse_plan_tasks(self.state.plan)
        self.state.total_tickets = len(self.state.task_titles)

        logger.info(
            "TicketCreationFlow: found %d task titles in plan",
            self.state.total_tickets,
        )

        log_flow_event(
            self.state.project_id, "ticket_creation_started",
            "ticket_creation_flow", "project", self.state.project_id,
            {"total_tickets": self.state.total_tickets},
        )

        if self.state.total_tickets == 0:
            logger.warning(
                "TicketCreationFlow: plan contains 0 parseable tasks for project %d",
                self.state.project_id,
            )
            event_bus.emit(FlowEvent(
                event_type="no_tickets_in_plan",
                project_id=self.state.project_id,
                entity_type="project",
                entity_id=self.state.project_id,
            ))

    # ── Epics & Milestones ────────────────────────────────────────────────

    @listen("initialize")
    def create_epics_and_milestones(self):
        """Create all epics and milestones in one Crew run."""
        if self.state.total_tickets == 0:
            logger.info(
                "TicketCreationFlow: skipping epics/milestones — 0 tasks to create",
            )
            return  # Will proceed to ticket_loop_router → all_tickets_done

        update_subflow_step(self.state.project_id, "ticket_creation_flow", "create_epics_and_milestones")
        logger.info("TicketCreationFlow: create_epics_and_milestones")

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        task_prompt = tl_tasks.create_epics_and_milestones(
            self.state.project_name,
            self.state.project_id,
            self.state.plan,
        )
        result = get_engine().execute(team_lead, task_prompt)

        epics, milestones = parse_epics_milestones_from_result(result)
        self.state.epics_created = epics
        self.state.milestones_created = milestones

        logger.info(
            "TicketCreationFlow: created %d epics, %d milestones",
            len(self.state.epics_created),
            len(self.state.milestones_created),
        )

        log_flow_event(
            self.state.project_id, "epics_milestones_created",
            "ticket_creation_flow", "project", self.state.project_id,
            {
                "epics_count": len(self.state.epics_created),
                "milestones_count": len(self.state.milestones_created),
            },
        )

    # ── Ticket loop ───────────────────────────────────────────────────────

    @router("create_epics_and_milestones")
    def ticket_loop_router(self):
        """Route to next ticket or to dependency setting."""
        if self.state.ticket_index < self.state.total_tickets:
            return "next_ticket"
        return "all_tickets_done"

    @listen("next_ticket")
    def create_single_ticket(self):
        """Create one task with full research via a dedicated Crew run."""
        update_subflow_step(
            self.state.project_id, "ticket_creation_flow",
            f"create_ticket_{self.state.ticket_index + 1}_of_{self.state.total_tickets}",
        )
        ticket_title = self.state.task_titles[self.state.ticket_index]
        logger.info(
            "TicketCreationFlow: creating ticket %d/%d — '%s'",
            self.state.ticket_index + 1, self.state.total_tickets, ticket_title,
        )

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        task_prompt = tl_tasks.create_single_ticket(
            project_name=self.state.project_name,
            project_id=self.state.project_id,
            plan=self.state.plan,
            ticket_title=ticket_title,
            ticket_index=self.state.ticket_index,
            total_tickets=self.state.total_tickets,
            epics_created=self.state.epics_created,
            milestones_created=self.state.milestones_created,
            tasks_already_created=self.state.tasks_created,
        )
        try:
            result = get_engine().execute(
                team_lead, task_prompt,
                guardrail=validate_ticket_creation,
            )

            # Check if agent detected a duplicate and skipped creation
            if "SKIPPED_DUPLICATE" in result:
                logger.info(
                    "TicketCreationFlow: ticket '%s' skipped (duplicate detected)",
                    ticket_title,
                )
                log_flow_event(
                    self.state.project_id, "ticket_skipped_duplicate",
                    "ticket_creation_flow", "task", None,
                    {"ticket_title": ticket_title, "reason": result[:200]},
                )
            else:
                task_id = parse_created_task_id(result)
                if task_id is not None:
                    self.state.tasks_created[ticket_title] = task_id
                    event_bus.emit(FlowEvent(
                        event_type="task_available",
                        project_id=self.state.project_id,
                        entity_type="task",
                        entity_id=task_id,
                        data={
                            "ticket_title": ticket_title,
                            "ticket_index": self.state.ticket_index,
                        },
                    ))
                    logger.info(
                        "TicketCreationFlow: ticket '%s' created with ID %d",
                        ticket_title, task_id,
                    )
                else:
                    logger.warning(
                        "TicketCreationFlow: could not parse task ID for '%s'",
                        ticket_title,
                    )
                    self.state.failed_items.append(ticket_title)
        except Exception:
            logger.exception(
                "TicketCreationFlow: failed to create ticket '%s'",
                ticket_title,
            )
            self.state.failed_items.append(ticket_title)

        self.state.ticket_index += 1

        log_flow_event(
            self.state.project_id, "ticket_created",
            "ticket_creation_flow", "task", None,
            {
                "ticket_title": ticket_title,
                "ticket_index": self.state.ticket_index,
                "total_tickets": self.state.total_tickets,
            },
        )

    @router("create_single_ticket")
    def check_more_tickets(self):
        """Route to next ticket or to dependency setting."""
        if self.state.ticket_index < self.state.total_tickets:
            return "next_ticket"
        return "all_tickets_done"

    # ── Dependencies ──────────────────────────────────────────────────────

    @listen("all_tickets_done")
    def set_dependencies(self):
        """Set task dependencies between the newly created tickets."""
        update_subflow_step(self.state.project_id, "ticket_creation_flow", "set_dependencies")

        if len(self.state.tasks_created) < 2:
            logger.info(
                "TicketCreationFlow: skipping dependency setting — "
                "only %d task(s) created, nothing to link",
                len(self.state.tasks_created),
            )
            return

        logger.info(
            "TicketCreationFlow: set_dependencies (%d tasks created, %d failed)",
            len(self.state.tasks_created), len(self.state.failed_items),
        )

        team_lead = get_agent_by_role("team_lead", self.state.project_id)
        team_lead.activate_context()

        task_prompt = tl_tasks.set_all_dependencies(
            project_id=self.state.project_id,
            plan=self.state.plan,
            tasks_created=self.state.tasks_created,
        )
        get_engine().execute(team_lead, task_prompt)

        log_flow_event(
            self.state.project_id, "dependencies_set",
            "ticket_creation_flow", "project", self.state.project_id,
            {
                "tasks_created": len(self.state.tasks_created),
                "failed_items": self.state.failed_items,
            },
        )

    # ── Error handling ────────────────────────────────────────────────────

    @listen("error")
    def handle_error(self):
        """Handle flow errors: log and notify."""
        logger.error(
            "TicketCreationFlow: error state reached (project_id=%d)",
            self.state.project_id,
        )
        log_flow_event(
            self.state.project_id, "flow_error", "ticket_creation_flow",
            "project", self.state.project_id,
        )
        notify_team_lead(
            self.state.project_id, "system",
            f"TicketCreationFlow error for project {self.state.project_id}. "
            f"Please investigate.",
        )
