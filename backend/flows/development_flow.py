"""DevelopmentFlow — handles task assignment, implementation, and review handoff.

Lifecycle: assign → implement → code review (dev↔reviewer until approval).

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
from backend.flows.guardrails import validate_implementation_output
from backend.flows.helpers import (
    build_crew,
    check_task_dependencies,
    detect_tech_hints,
    get_project_name,
    get_task_by_id,
    log_flow_event,
    notify_team_lead,
    set_task_branch,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.snapshot_service import update_subflow_step
from backend.flows.state_models import DevelopmentState
from backend.prompts.developer import tasks as dev_tasks
from backend.prompts.team import build_conversation_context

logger = logging.getLogger(__name__)


@persist()
class DevelopmentFlow(Flow[DevelopmentState]):
    """Manages the development lifecycle for a single task."""

    # ── Start ─────────────────────────────────────────────────────────────

    @start()
    def assign_task(self):
        """Load task, verify dependencies, and assign to a developer."""
        update_subflow_step(self.state.project_id, "development_flow", "assign_task")
        logger.info(
            "DevelopmentFlow: assign_task (task_id=%d)", self.state.task_id,
        )

        task = self._load_task_and_validate()
        if task is None:
            return

        # Find an available developer and assign directly
        developer = get_available_agent_by_role(
            "developer", self.state.project_id,
            tech_hints=self.state.tech_hints,
        )
        self.state.developer_id = developer.agent_id
        developer.activate_context(task_id=self.state.task_id)

        # Assign task in DB (backlog/pending → in_progress)
        self._assign_task_in_db(developer.agent_id)

        log_flow_event(
            self.state.project_id, "task_assigned", "development_flow",
            "task", self.state.task_id,
            {
                "developer_id": self.state.developer_id,
                "task_title": self.state.task_title,
                "task_description": self.state.task_description[:200],
            },
        )

    # ── assign_task helpers ────────────────────────────────────────────────

    def _load_task_and_validate(self) -> dict | None:
        """Load task from DB, verify dependencies, and populate tech hints on state."""
        task = get_task_by_id(self.state.task_id)
        if task is None:
            logger.error("Task %d not found", self.state.task_id)
            return None

        self.state.task_title = task.get("title", "")
        self.state.task_description = task.get("description", "")
        if not self.state.project_name:
            self.state.project_name = get_project_name(self.state.project_id)

        deps_ok = check_task_dependencies(self.state.task_id)
        if not deps_ok:
            logger.warning(
                "Task %d has unmet dependencies, returning to backlog",
                self.state.task_id,
            )
            self.state.dependencies_met = False
            return None
        self.state.dependencies_met = True

        self.state.tech_hints = detect_tech_hints(self.state.project_id)
        return task

    def _assign_task_in_db(self, developer_id: str) -> None:
        """Assign task to developer and move to in_progress.

        Handles the state machine transitions: if the task is in backlog,
        it must go through pending first before reaching in_progress.
        """
        from backend.tools.base.db import execute_with_retry
        import sqlite3

        def _update(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (self.state.task_id,)
            ).fetchone()
            if row is None:
                return
            current_status = row["status"] if isinstance(row, sqlite3.Row) else row[0]

            # backlog → pending → in_progress (two transitions)
            if current_status == "backlog":
                conn.execute(
                    "UPDATE tasks SET status = 'pending' WHERE id = ?",
                    (self.state.task_id,),
                )
                current_status = "pending"

            # pending → in_progress
            if current_status == "pending":
                conn.execute(
                    "UPDATE tasks SET status = 'in_progress', assigned_to = ? WHERE id = ?",
                    (developer_id, self.state.task_id),
                )

            conn.commit()

        execute_with_retry(_update)

    @router("assign_task")
    def route_assignment(self):
        """Route based on task assignment result."""
        if not self.state.task_title:
            # Task not found
            return "error"
        if not self.state.dependencies_met:
            return "blocked"
        return "task_assigned"

    @listen("blocked")
    def handle_blocked(self):
        """Keep task in backlog when dependencies aren't met."""
        logger.info("DevelopmentFlow: task %d blocked by dependencies", self.state.task_id)
        update_task_status(self.state.task_id, "backlog")

    # ── Implementation ────────────────────────────────────────────────────

    @listen("task_assigned")
    def implement_code(self):
        """Developer creates branch, writes code, and commits."""
        update_subflow_step(self.state.project_id, "development_flow", "implement_code")
        logger.info("DevelopmentFlow: implement_code for task %d", self.state.task_id)

        developer = get_agent_by_role(
            "developer", self.state.project_id,
            agent_id=self.state.developer_id,
            tech_hints=self.state.tech_hints,
        )
        developer.activate_context(task_id=self.state.task_id)
        run_id = developer.create_agent_run(self.state.task_id)
        self.state.agent_run_id = run_id

        conv_ctx = build_conversation_context(
            project_id=self.state.project_id,
            agent_id=self.state.developer_id,
            task_id=self.state.task_id,
        )
        task_prompt = dev_tasks.implement_code(
            self.state.task_id, self.state.task_title,
            self.state.task_description,
            conversation_context=conv_ctx,
            project_id=self.state.project_id,
            project_name=self.state.project_name,
        )
        from backend.tools import get_tools_for_task_type
        crew = build_crew(
            developer, task_prompt,
            guardrail=validate_implementation_output,
            task_tools=get_tools_for_task_type("implement"),
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

    @listen("implement_code")
    def request_review(self):
        """Invoke CodeReviewFlow — it runs the full dev↔reviewer cycle internally.

        The review cycle loops until approval. No escalation to Team Lead.
        """
        update_subflow_step(self.state.project_id, "development_flow", "request_review")
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

        self.state.review_status = review_flow.state.review_status

        log_flow_event(
            self.state.project_id, "review_completed", "development_flow",
            "task", self.state.task_id,
            {"developer_id": self.state.developer_id, "task_title": self.state.task_title,
             "branch_name": self.state.branch_name,
             "review_status": self.state.review_status.value},
        )

    # ── Finalization ──────────────────────────────────────────────────────

    @listen("request_review")
    def finalize_task(self):
        """Finalize after review completes (task already marked done by CodeReviewFlow)."""
        update_subflow_step(self.state.project_id, "development_flow", "finalize_task")
        logger.info("DevelopmentFlow: finalizing task %d", self.state.task_id)

        # Stop the developer's pod if running
        self._deactivate_developer()

        log_flow_event(
            self.state.project_id, "task_completed", "development_flow",
            "task", self.state.task_id,
            {"developer_id": self.state.developer_id, "task_title": self.state.task_title,
             "branch_name": self.state.branch_name},
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
        # Stop the developer's pod if running
        self._deactivate_developer()

        notify_team_lead(
            self.state.project_id, "system",
            f"DevelopmentFlow error: task {self.state.task_id} failed. "
            f"Please investigate and re-assign.",
        )

    def _deactivate_developer(self) -> None:
        """Stop the developer's pod if pod mode is active."""
        try:
            developer = get_agent_by_role("developer", self.state.project_id)
            developer.deactivate()
        except Exception:
            logger.debug("Could not deactivate developer pod", exc_info=True)
