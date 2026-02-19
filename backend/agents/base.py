"""Base agent wrapper for PABADA CrewAI agents."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from crewai import Agent

from backend.tools import get_tools_for_role
from backend.tools.base.context import set_context
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
        max_iter: int = 20,
        llm: Any | None = None,
        extra_tools: list | None = None,
        knowledge_sources: list | None = None,
        memory_service: Any | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.name = name
        self.project_id = project_id
        self._memory_service = memory_service

        # Inject persistent memory into backstory if available
        if memory_service is not None:
            memory_context = memory_service.build_memory_context_for_backstory(
                agent_id, project_id,
            )
            if memory_context:
                backstory = backstory + memory_context

        # Resolve tools for the role, plus optional extras
        tools = get_tools_for_role(role)
        if extra_tools:
            tools = tools + list(extra_tools)

        # Build the underlying CrewAI agent
        agent_kwargs: dict[str, Any] = {
            "role": name,
            "goal": goal,
            "backstory": backstory,
            "tools": tools,
            "allow_delegation": allow_delegation,
            "verbose": verbose,
            "max_iter": max_iter,
        }
        if llm is not None:
            agent_kwargs["llm"] = llm
        if knowledge_sources:
            agent_kwargs["knowledge_sources"] = knowledge_sources

        self._agent = Agent(**agent_kwargs)

    # -- Public properties -----------------------------------------------------

    @property
    def crewai_agent(self) -> Agent:
        """Return the underlying ``crewai.Agent`` instance."""
        return self._agent

    # -- Context management ----------------------------------------------------

    def activate_context(self, *, task_id: int | None = None) -> None:
        """Set the tool-level context vars for this agent's execution scope."""
        set_context(
            project_id=self.project_id,
            agent_id=self.agent_id,
            task_id=task_id,
        )

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

    def update_memory(self, memory: str) -> None:
        """Persist free-form memory text to the ``roster.memory`` column."""

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE roster SET memory = ? WHERE agent_id = ?",
                (memory, self.agent_id),
            )
            conn.commit()

        execute_with_retry(_update)

    def load_memory(self) -> str:
        """Load the agent's persisted memory from the roster table."""

        def _select(conn: sqlite3.Connection) -> str:
            row = conn.execute(
                "SELECT memory FROM roster WHERE agent_id = ?",
                (self.agent_id,),
            ).fetchone()
            return row["memory"] if row else ""

        return execute_with_retry(_select)

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

        # Set run id in context so tools can reference it
        set_context(agent_run_id=agent_run_id)
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
        memory_text: str | None = None,
    ) -> None:
        """Mark an agent_run as finished and update performance metrics.

        If *memory_text* is provided and a memory service is available,
        persist the memory for future runs.
        """
        if status not in self._VALID_RUN_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Valid: {sorted(self._VALID_RUN_STATUSES)}"
            )

        if memory_text is not None and self._memory_service is not None:
            self._memory_service.persist_agent_memory(self.agent_id, memory_text)

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
