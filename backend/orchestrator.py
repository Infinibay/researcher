"""Project orchestrator for TUI mode — manages multi-agent task execution.

Replaces the MainProjectFlow + CrewAI flow system for CLI/TUI usage.
The user sends messages, the Project Lead plans internally, and agents
execute tasks in their respective worktrees.

Workflow:
1. User sends a message
2. Project Lead analyzes and creates a task plan
3. Tasks are assigned to Developer(s) / Researcher
4. Agents execute in parallel (if multi-dev with worktrees)
5. Code Reviewer reviews completed work
6. Changes are merged back to main branch
7. Results shown to user
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from backend.agents.base import InfinibayAgent
from backend.config.settings import settings
from backend.engine import get_engine
from backend.engine.loop_models import LoopState
from backend.tools.base.context import bind_tools_to_agent, set_context

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    FAILED = "failed"


@dataclass
class AgentTask:
    """A task assigned to an agent."""

    id: int
    description: str
    expected_output: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None
    result: str = ""
    review_feedback: str = ""
    branch_name: str = ""


@dataclass
class OrchestratorEvent:
    """Event emitted by the orchestrator for TUI display."""

    event_type: str  # "plan_created", "task_started", "task_completed", "review", "merge", "done"
    agent_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class ProjectOrchestrator:
    """Manages multi-agent task execution for TUI mode.

    Unlike the CrewAI flow-based system, this orchestrator:
    - Runs synchronously (TUI drives the event loop)
    - Dispatches tasks directly to agents via LoopEngine
    - Uses git worktrees for parallel dev work
    - Emits events for TUI display
    """

    def __init__(
        self,
        project_id: int = 1,
        workspace_path: str | None = None,
        on_event: Callable[[OrchestratorEvent], None] | None = None,
    ):
        self.project_id = project_id
        self.workspace_path = workspace_path or os.getcwd()
        self.on_event = on_event or (lambda e: None)

        self.agents: dict[str, InfinibayAgent] = {}
        self.tasks: list[AgentTask] = []
        self._task_counter = 0
        self._initialized = False
        self._worktree_mgr = None
        self._session_summaries: list[str] = []

    def initialize(self) -> None:
        """Set up agents, worktrees, and context."""
        if self._initialized:
            return

        # Create agents based on settings
        self._create_agents()

        # Set up worktrees if multi-dev enabled
        if settings.MULTI_DEV_ENABLED:
            self._setup_worktrees()

        self._initialized = True
        logger.info(
            "Orchestrator initialized: %d agents, workspace=%s, multi_dev=%s",
            len(self.agents), self.workspace_path, settings.MULTI_DEV_ENABLED,
        )

    def _create_agents(self) -> None:
        """Create the agent team."""
        from backend.agents.registry import get_tools_for_role

        roles = self._get_team_composition()

        for agent_id, role_config in roles.items():
            role = role_config["role"]
            tools = get_tools_for_role(role)
            agent = InfinibayAgent(
                agent_id=agent_id,
                role=role,
                name=role_config.get("name", agent_id),
                goal=role_config.get("goal", f"Act as {role}"),
                backstory=role_config.get("backstory", ""),
                project_id=self.project_id,
            )
            bind_tools_to_agent(tools, agent_id)
            agent._tools = tools

            # Set workspace context
            workspace = self.workspace_path
            if settings.MULTI_DEV_ENABLED and role == "developer":
                # Worktree path will be set after worktree creation
                pass

            set_context(
                project_id=self.project_id,
                agent_id=agent_id,
                workspace_path=workspace,
            )

            self.agents[agent_id] = agent

    def _get_team_composition(self) -> dict[str, dict[str, str]]:
        """Define the agent team based on settings."""
        from backend.prompts.developer.system import get_system_prompt as dev_system
        from backend.prompts.code_reviewer.system import get_system_prompt as cr_system
        from backend.prompts.researcher.system import get_system_prompt as res_system

        team: dict[str, dict[str, str]] = {
            "project_lead": {
                "role": "project_lead",
                "name": "Lead",
                "goal": "Analyze user requests, create task plans, coordinate the team",
                "backstory": (
                    "You are a senior technical project lead. When the user describes "
                    "what they want, you break it down into concrete, actionable tasks. "
                    "Each task should be small enough for one developer to complete. "
                    "You assign tasks and coordinate the team."
                ),
            },
        }

        # Add developers
        dev_count = settings.DEV_COUNT if settings.MULTI_DEV_ENABLED else 1
        for i in range(1, dev_count + 1):
            agent_id = f"dev-{i}" if dev_count > 1 else "developer"
            team[agent_id] = {
                "role": "developer",
                "name": f"Dev-{i}" if dev_count > 1 else "Developer",
                "goal": "Implement code changes, fix bugs, write tests",
                "backstory": _get_role_backstory("developer"),
            }

        # Code reviewer
        team["code_reviewer"] = {
            "role": "code_reviewer",
            "name": "Reviewer",
            "goal": "Review code changes for quality, correctness, and best practices",
            "backstory": _get_role_backstory("code_reviewer"),
        }

        # Researcher
        team["researcher"] = {
            "role": "researcher",
            "name": "Researcher",
            "goal": "Research documentation, APIs, and technical solutions",
            "backstory": _get_role_backstory("researcher"),
        }

        # Research reviewer
        team["research_reviewer"] = {
            "role": "research_reviewer",
            "name": "Research Reviewer",
            "goal": "Review research findings for accuracy and completeness",
            "backstory": _get_role_backstory("research_reviewer"),
        }

        return team

    def _setup_worktrees(self) -> None:
        """Create git worktrees for developer agents."""
        from backend.git.local_worktree import LocalWorktreeManager as WorktreeManager

        self._worktree_mgr = WorktreeManager(self.workspace_path)
        dev_agents = [aid for aid, a in self.agents.items() if a.role == "developer"]

        paths = self._worktree_mgr.setup_for_agents(dev_agents)
        for agent_id, path in paths.items():
            set_context(
                project_id=self.project_id,
                agent_id=agent_id,
                workspace_path=path,
            )
            logger.info("Dev %s workspace: %s", agent_id, path)

    def handle_user_message(self, message: str) -> str:
        """Process a user message through the agent pipeline.

        Returns the final response to display to the user.
        """
        if not self._initialized:
            self.initialize()

        # Add to session context
        self._session_summaries.append(f"User: {message[:200]}")

        # Phase 1: Project Lead analyzes and plans
        plan_result = self._run_project_lead(message)
        self.on_event(OrchestratorEvent(
            event_type="plan_created",
            agent_id="project_lead",
            data={"plan": plan_result},
        ))

        # Check if this is a simple response (no tasks needed)
        if not self.tasks:
            self._session_summaries.append(f"Lead: {plan_result[:200]}")
            return plan_result

        # Phase 2: Execute tasks
        results = self._execute_tasks()

        # Phase 3: Code review (if code was changed)
        review_results = self._run_code_reviews(results)

        # Phase 4: Merge worktrees (if multi-dev)
        if settings.MULTI_DEV_ENABLED and self._worktree_mgr:
            self._merge_completed_work()

        # Phase 5: Synthesize final response
        final = self._synthesize_response(plan_result, results, review_results)
        self._session_summaries.append(f"Result: {final[:200]}")

        self.on_event(OrchestratorEvent(
            event_type="done",
            data={"result": final},
        ))

        return final

    def _run_project_lead(self, user_message: str) -> str:
        """Have the Project Lead analyze the request and create tasks."""
        lead = self.agents.get("project_lead")
        if not lead:
            return user_message  # No lead, pass through

        engine = get_engine()

        # Build task prompt for the project lead
        task_desc = (
            f"The user says: {user_message}\n\n"
            "Analyze this request. If it requires code changes or research:\n"
            "1. Break it down into concrete tasks\n"
            "2. For each task, call step_complete with the task in your summary\n"
            "3. When done planning, provide the plan overview as final_answer\n\n"
            "If it's a simple question you can answer directly, just answer it."
        )
        expected = "A plan with concrete tasks, or a direct answer."

        result = engine.execute(
            lead,
            (task_desc, expected),
            identity_override=lead.backstory,
        )

        return result

    def _execute_tasks(self) -> list[dict[str, Any]]:
        """Execute all pending tasks using available agents."""
        results = []
        engine = get_engine()

        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Find available agent
            agent = self._assign_task(task)
            if not agent:
                task.status = TaskStatus.FAILED
                task.result = "No available agent for this task"
                continue

            task.status = TaskStatus.IN_PROGRESS
            task.assigned_to = agent.agent_id

            self.on_event(OrchestratorEvent(
                event_type="task_started",
                agent_id=agent.agent_id,
                data={"task_id": task.id, "description": task.description},
            ))

            try:
                result = engine.execute(
                    agent,
                    (task.description, task.expected_output or "Complete the task."),
                )
                task.result = result
                task.status = TaskStatus.DONE

                self.on_event(OrchestratorEvent(
                    event_type="task_completed",
                    agent_id=agent.agent_id,
                    data={"task_id": task.id, "result": result[:500]},
                ))

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f"Failed: {exc}"
                logger.error("Task %d failed: %s", task.id, exc)

            results.append({
                "task_id": task.id,
                "agent": agent.agent_id,
                "status": task.status.value,
                "result": task.result,
            })

        return results

    def _assign_task(self, task: AgentTask) -> InfinibayAgent | None:
        """Find an available agent for a task."""
        # Simple assignment: first available developer
        for agent_id, agent in self.agents.items():
            if agent.role == "developer":
                # Check if agent is busy
                busy = any(
                    t.assigned_to == agent_id and t.status == TaskStatus.IN_PROGRESS
                    for t in self.tasks
                )
                if not busy:
                    return agent
        return None

    def _run_code_reviews(self, task_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run code review on completed tasks."""
        if not settings.REVIEW_ENABLED:
            return []

        reviewer = self.agents.get("code_reviewer")
        if not reviewer:
            return []

        engine = get_engine()
        reviews = []

        # Get file changes from engine
        file_changes = engine.get_changed_files_summary() if engine.has_file_changes() else ""
        if not file_changes:
            return []

        review_prompt = (
            f"Review the following code changes:\n\n{file_changes}\n\n"
            "Provide your verdict: APPROVED or REJECTED with specific feedback."
        )

        self.on_event(OrchestratorEvent(
            event_type="review_started",
            agent_id="code_reviewer",
        ))

        try:
            result = engine.execute(
                reviewer,
                (review_prompt, "APPROVED or REJECTED with feedback."),
            )
            reviews.append({"reviewer": "code_reviewer", "result": result})

            self.on_event(OrchestratorEvent(
                event_type="review_completed",
                agent_id="code_reviewer",
                data={"result": result[:500]},
            ))
        except Exception as exc:
            logger.error("Code review failed: %s", exc)

        return reviews

    def _merge_completed_work(self) -> None:
        """Merge developer worktrees back to main."""
        if not self._worktree_mgr:
            return

        for task in self.tasks:
            if task.status == TaskStatus.DONE and task.assigned_to:
                agent = self.agents.get(task.assigned_to)
                if agent and agent.role == "developer":
                    result = self._worktree_mgr.merge_worktree(
                        task.assigned_to,
                        message=f"Merge: {task.description[:80]}",
                    )
                    if result["success"]:
                        self.on_event(OrchestratorEvent(
                            event_type="merge_completed",
                            agent_id=task.assigned_to,
                            data={"task_id": task.id},
                        ))
                    else:
                        logger.warning(
                            "Merge failed for %s: %s",
                            task.assigned_to, result["message"],
                        )

    def _synthesize_response(
        self,
        plan: str,
        results: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
    ) -> str:
        """Combine all results into a user-facing response."""
        parts = []

        if len(results) == 0:
            return plan

        # Task results
        for r in results:
            if r["status"] == "done":
                parts.append(r["result"])
            elif r["status"] == "failed":
                parts.append(f"Task {r['task_id']} failed: {r['result']}")

        # Review results
        for rev in reviews:
            parts.append(f"\nCode Review: {rev['result']}")

        return "\n\n".join(parts) if parts else plan

    def add_task(self, description: str, expected_output: str = "") -> AgentTask:
        """Add a task to the orchestrator."""
        self._task_counter += 1
        task = AgentTask(
            id=self._task_counter,
            description=description,
            expected_output=expected_output,
        )
        self.tasks.append(task)
        return task

    def get_status(self) -> dict[str, Any]:
        """Get current orchestrator status for display."""
        return {
            "agents": {
                aid: {"role": a.role, "name": a.name}
                for aid, a in self.agents.items()
            },
            "tasks": [
                {"id": t.id, "description": t.description[:80], "status": t.status.value, "assigned_to": t.assigned_to}
                for t in self.tasks
            ],
            "multi_dev": settings.MULTI_DEV_ENABLED,
            "workspace": self.workspace_path,
        }

    def shutdown(self) -> None:
        """Clean up resources."""
        if self._worktree_mgr:
            count = self._worktree_mgr.cleanup_worktrees()
            if count:
                logger.info("Cleaned up %d worktrees", count)
        self._initialized = False


def _get_role_backstory(role: str) -> str:
    """Load backstory for a role from the prompts system."""
    try:
        if role == "developer":
            from backend.prompts.developer.system import get_system_prompt
            return get_system_prompt()
        elif role == "code_reviewer":
            from backend.prompts.code_reviewer.system import get_system_prompt
            return get_system_prompt()
        elif role == "researcher":
            from backend.prompts.researcher.system import get_system_prompt
            return get_system_prompt()
        elif role == "research_reviewer":
            from backend.prompts.research_reviewer.system import get_system_prompt
            return get_system_prompt()
        elif role == "project_lead":
            from backend.prompts.project_lead.system import get_system_prompt
            return get_system_prompt()
    except Exception:
        pass
    return f"You are a {role}."
