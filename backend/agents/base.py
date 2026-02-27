"""Base agent wrapper for PABADA CrewAI agents."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from crewai import Agent

from backend.tools import get_tools_for_role
from backend.tools.base.context import bind_tools_to_agent, set_context
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class PabadaAgent:
    """Wrapper around crewai.Agent that adds PABADA-specific behaviour.

    Responsibilities:
    - Build a ``crewai.Agent`` with the correct tools for *role*
    - Register / update the agent in the ``roster`` table
    - Create ``agent_runs`` records when the agent starts work
    - Persist memory back to the ``roster.memory`` column
    - Set execution context (project_id, agent_id) for tools
    """

    # Per-role execution time limits (seconds).
    # Populated from settings at class level to avoid repeated lookups.
    _ROLE_EXECUTION_TIMES: dict[str, str] = {
        "researcher": "AGENT_MAX_EXECUTION_TIME_RESEARCHER",
        "developer": "AGENT_MAX_EXECUTION_TIME_DEVELOPER",
        "code_reviewer": "AGENT_MAX_EXECUTION_TIME_CODE_REVIEWER",
        "team_lead": "AGENT_MAX_EXECUTION_TIME_TEAM_LEAD",
        "project_lead": "AGENT_MAX_EXECUTION_TIME_PROJECT_LEAD",
        "research_reviewer": "AGENT_MAX_EXECUTION_TIME_RESEARCH_REVIEWER",
    }

    def __init__(
        self,
        *,
        agent_id: str,
        role: str,
        name: str,
        goal: str,
        backstory: str,
        project_id: int,
        allow_delegation: bool = False,
        verbose: bool = True,
        max_iter: int = 25,
        max_execution_time: int | None = None,
        max_retry_limit: int = 2,
        reasoning: bool = False,
        max_reasoning_attempts: int | None = None,
        llm: Any | None = None,
        extra_tools: list | None = None,
        knowledge_sources: list | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.name = name
        self.project_id = project_id

        # Resolve tools for the role, plus optional extras
        tools = get_tools_for_role(role)
        if extra_tools:
            tools = tools + list(extra_tools)

        # Stamp each tool with this agent's ID so they can look up context
        # from the process-global dict even when running in a worker thread.
        bind_tools_to_agent(tools, agent_id)

        # Resolve max_execution_time from settings if not explicitly provided
        if max_execution_time is None:
            from backend.config.settings import settings
            setting_attr = self._ROLE_EXECUTION_TIMES.get(role)
            if setting_attr:
                max_execution_time = getattr(settings, setting_attr)
            else:
                max_execution_time = settings.AGENT_MAX_EXECUTION_TIME_DEFAULT

        # Build the underlying CrewAI agent
        agent_kwargs: dict[str, Any] = {
            "role": name,
            "goal": goal,
            "backstory": backstory,
            "tools": tools,
            "allow_delegation": allow_delegation,
            "verbose": verbose,
            "max_iter": max_iter,
            "max_execution_time": max_execution_time,
            "max_retry_limit": max_retry_limit,
        }
        if reasoning:
            agent_kwargs["reasoning"] = True
            if max_reasoning_attempts is not None:
                agent_kwargs["max_reasoning_attempts"] = max_reasoning_attempts
        if llm is not None:
            agent_kwargs["llm"] = llm
        else:
            from backend.config.llm import get_llm
            try:
                agent_kwargs["llm"] = get_llm()
            except RuntimeError:
                pass  # fall back to CrewAI's default env-var resolution
        if knowledge_sources:
            agent_kwargs["knowledge_sources"] = knowledge_sources
            # Configure embedder so CrewAI's knowledge system uses the
            # correct provider instead of defaulting to OpenAI's API.
            from backend.knowledge.service import KnowledgeService
            agent_kwargs["embedder"] = KnowledgeService.configure_embedder()

        self._agent = Agent(**agent_kwargs)

    # -- Public properties -----------------------------------------------------

    @property
    def crewai_agent(self) -> Agent:
        """Return the underlying ``crewai.Agent`` instance."""
        return self._agent

    # -- Context management ----------------------------------------------------

    def activate_context(self, *, task_id: int | None = None) -> None:
        """Set the tool-level context vars for this agent's execution scope.

        In pod mode, also starts a persistent container for this agent.
        """
        workspace_path = self._resolve_workspace_path()
        set_context(
            project_id=self.project_id,
            agent_id=self.agent_id,
            task_id=task_id,
            workspace_path=workspace_path,
        )
        if self._is_pod_mode():
            from backend.security.pod_manager import pod_manager  # lazy import

            # For worktree agents, mount the main repo (parent of .worktrees/)
            # so git's cross-directory references work inside the container.
            mount_path = workspace_path
            pod_workdir = "/workspace"

            if "/.worktrees/" in workspace_path:
                parts = workspace_path.rsplit("/.worktrees/", 1)
                mount_path = parts[0]  # main repo path
                agent_subdir = parts[1]  # e.g. "developer_1_p1"
                pod_workdir = f"/workspace/.worktrees/{agent_subdir}"

            pod_manager.start_pod(
                agent_id=self.agent_id,
                role=self.role,
                workspace_path=mount_path,
                workdir=pod_workdir,
            )

    def deactivate(self) -> None:
        """Stop the agent's pod (if running in pod mode).

        Worktrees are NOT removed here — they persist across tasks so
        the agent keeps its branch and uncommitted work.  Stale worktrees
        are cleaned up by the scavenger when agents leave the roster.
        """
        if self._is_pod_mode():
            from backend.security.pod_manager import pod_manager  # lazy import

            pod_manager.stop_pod(self.agent_id)

    def _is_pod_mode(self) -> bool:
        """Check if sandbox (pod) mode is active."""
        from backend.config.settings import settings

        return settings.SANDBOX_ENABLED

    # Roles that work on code and need isolated worktrees.
    _WORKTREE_ROLES = {"developer", "code_reviewer"}

    def _resolve_workspace_path(self) -> str:
        """Determine the workspace path for this agent's project.

        For developer and code_reviewer roles, returns a per-agent git
        worktree so multiple agents can work on different branches
        concurrently without overwriting each other's files.
        """
        import os

        from backend.config.settings import settings

        # Try to get repo path from the repositories table
        try:
            from backend.tools.base.db import execute_with_retry

            result = {"path": None, "branch": None}

            def _query(conn):
                row = conn.execute(
                    """SELECT local_path, default_branch FROM repositories
                       WHERE project_id = ? AND status = 'active'
                       ORDER BY id DESC LIMIT 1""",
                    (self.project_id,),
                ).fetchone()
                if row:
                    result["path"] = row["local_path"]
                    result["branch"] = row["default_branch"] or "main"

            execute_with_retry(_query)

            if result["path"]:
                repo_local_path = result["path"]
                os.makedirs(repo_local_path, exist_ok=True)

                # Worktree isolation for code-touching roles
                if self.role in self._WORKTREE_ROLES:
                    try:
                        from backend.git.worktree_manager import WorktreeManager

                        return WorktreeManager().ensure_worktree(
                            project_id=self.project_id,
                            agent_id=self.agent_id,
                            repo_local_path=repo_local_path,
                            base_branch=result["branch"],
                        )
                    except Exception:
                        logger.warning(
                            "Worktree creation failed for %s, "
                            "falling back to shared repo path",
                            self.agent_id, exc_info=True,
                        )

                return repo_local_path
        except Exception:
            pass

        # Fallback: standard workspace directory
        path = f"{settings.WORKSPACE_BASE_DIR}/projects/{self.project_id}"
        os.makedirs(path, exist_ok=True)
        return path

    # -- Roster helpers --------------------------------------------------------

    def register_in_roster(self) -> None:
        """Insert or update the agent row in the ``roster`` table."""

        def _upsert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO roster (agent_id, name, role, status, created_at)
                   VALUES (?, ?, ?, 'idle', CURRENT_TIMESTAMP)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       name = excluded.name,
                       role = excluded.role,
                       last_active_at = CURRENT_TIMESTAMP""",
                (self.agent_id, self.name, self.role),
            )
            conn.commit()

        execute_with_retry(_upsert)
        logger.info("Registered agent %s (%s) in roster", self.agent_id, self.role)

    # -- Agent run tracking ----------------------------------------------------

    def create_agent_run(self, task_id: int) -> str:
        """Insert a new row in ``agent_runs`` and return the ``agent_run_id``."""
        agent_run_id = str(uuid.uuid4())

        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO agent_runs
                       (project_id, agent_run_id, agent_id, task_id, role, status, started_at)
                   VALUES (?, ?, ?, ?, ?, 'running', CURRENT_TIMESTAMP)""",
                (self.project_id, agent_run_id, self.agent_id, task_id, self.role),
            )
            # Also bump roster stats
            conn.execute(
                """UPDATE roster
                      SET status = 'active',
                          total_runs = total_runs + 1,
                          last_active_at = CURRENT_TIMESTAMP
                    WHERE agent_id = ?""",
                (self.agent_id,),
            )
            conn.commit()

        execute_with_retry(_insert)

        # Set run id in context so tools can reference it.
        # Include agent_id so the process-global context dict gets updated.
        set_context(agent_id=self.agent_id, agent_run_id=agent_run_id)
        logger.info(
            "Created agent_run %s for agent %s on task %d",
            agent_run_id, self.agent_id, task_id,
        )
        return agent_run_id

    _VALID_RUN_STATUSES = {"completed", "failed", "timeout"}

    def complete_agent_run(
        self,
        agent_run_id: str,
        *,
        status: str = "completed",
        output_summary: str = "",
        tokens_used: int = 0,
        error_class: str | None = None,
    ) -> None:
        """Mark an agent_run as finished and update performance metrics."""
        if status not in self._VALID_RUN_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Valid: {sorted(self._VALID_RUN_STATUSES)}"
            )

        def _finish(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE agent_runs
                      SET status = ?, output_summary = ?,
                          tokens_used = ?, error_class = ?,
                          ended_at = CURRENT_TIMESTAMP
                    WHERE agent_run_id = ?""",
                (status, output_summary, tokens_used, error_class, agent_run_id),
            )
            # Update agent_performance (upsert)
            if status == "completed":
                conn.execute(
                    """INSERT INTO agent_performance (agent_id, role, total_runs, successful_runs, total_tokens, last_updated_at)
                       VALUES (?, ?, 1, 1, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(agent_id) DO UPDATE SET
                           total_runs = total_runs + 1,
                           successful_runs = successful_runs + 1,
                           total_tokens = total_tokens + excluded.total_tokens,
                           last_updated_at = CURRENT_TIMESTAMP""",
                    (self.agent_id, self.role, tokens_used),
                )
            else:
                conn.execute(
                    """INSERT INTO agent_performance (agent_id, role, total_runs, failed_runs, total_tokens, last_updated_at)
                       VALUES (?, ?, 1, 1, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(agent_id) DO UPDATE SET
                           total_runs = total_runs + 1,
                           failed_runs = failed_runs + 1,
                           total_tokens = total_tokens + excluded.total_tokens,
                           last_updated_at = CURRENT_TIMESTAMP""",
                    (self.agent_id, self.role, tokens_used),
                )
            # Return roster to idle
            conn.execute(
                "UPDATE roster SET status = 'idle' WHERE agent_id = ?",
                (self.agent_id,),
            )
            conn.commit()

        execute_with_retry(_finish)
        logger.info(
            "Completed agent_run %s with status=%s", agent_run_id, status,
        )
