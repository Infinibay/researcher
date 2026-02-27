"""Reporting and agent execution helpers for PABADA flows."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

# Transient LLM errors that should be retried
_TRANSIENT_LLM_ERRORS = (
    "Invalid response from LLM call",
    "Connection error",
    "Rate limit",
    "timeout",
    "503",
    "502",
    "429",
)

DEFAULT_LLM_RETRIES = 3
DEFAULT_LLM_RETRY_DELAY = 5.0  # seconds


def _is_transient_llm_error(exc: Exception) -> bool:
    """Check if an exception looks like a transient LLM provider error."""
    msg = str(exc)
    return any(pattern.lower() in msg.lower() for pattern in _TRANSIENT_LLM_ERRORS)


def kickoff_with_retry(
    crew: Any,
    *,
    max_retries: int = DEFAULT_LLM_RETRIES,
    base_delay: float = DEFAULT_LLM_RETRY_DELAY,
) -> Any:
    """Run ``crew.kickoff()`` with exponential-backoff retries for transient LLM errors.

    Non-transient errors are re-raised immediately.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return crew.kickoff()
        except Exception as exc:
            last_exc = exc
            if not _is_transient_llm_error(exc) or attempt == max_retries:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                attempt, max_retries, delay, str(exc)[:200],
            )
            time.sleep(delay)
    raise last_exc  # unreachable, but keeps type checkers happy


def generate_final_report(project_id: int) -> str:
    """Generate a summary report of the project."""

    def _query(conn: sqlite3.Connection) -> str:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            return "Project not found."

        # Task summary
        tasks = conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM tasks WHERE project_id = ?
               GROUP BY status""",
            (project_id,),
        ).fetchall()
        task_summary = {r["status"]: r["cnt"] for r in tasks}

        # Epics
        epics = conn.execute(
            "SELECT title, status FROM epics WHERE project_id = ?",
            (project_id,),
        ).fetchall()

        # Agent performance
        perf = conn.execute(
            """SELECT ar.role, COUNT(*) as runs,
                      SUM(CASE WHEN ar.status = 'completed' THEN 1 ELSE 0 END) as success
               FROM agent_runs ar
               WHERE ar.project_id = ?
               GROUP BY ar.role""",
            (project_id,),
        ).fetchall()

        report_lines = [
            f"# Project Report: {project['name']}",
            f"Status: {project['status']}",
            "",
            "## Task Summary",
        ]
        for status, count in task_summary.items():
            report_lines.append(f"- {status}: {count}")

        report_lines.append("")
        report_lines.append("## Epics")
        for epic in epics:
            report_lines.append(f"- {epic['title']}: {epic['status']}")

        report_lines.append("")
        report_lines.append("## Agent Performance")
        for p in perf:
            report_lines.append(
                f"- {p['role']}: {p['success']}/{p['runs']} successful"
            )

        return "\n".join(report_lines)

    return execute_with_retry(_query)


def log_flow_event(
    project_id: int,
    event_type: str,
    event_source: str,
    entity_type: str,
    entity_id: int | None = None,
    event_data: dict[str, Any] | None = None,
) -> None:
    """Log an event to the events_log table and emit to event_bus."""

    def _insert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type,
                    entity_id, event_data_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (project_id, event_type, event_source, entity_type,
             entity_id, json.dumps(event_data or {})),
        )
        conn.commit()

    execute_with_retry(_insert)

    # Also emit to event_bus so WebSocket clients receive the event
    try:
        from backend.flows.event_listeners import FlowEvent, event_bus

        event_bus.emit(FlowEvent(
            event_type=event_type,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            data=event_data or {},
        ))
    except Exception:
        logger.debug("log_flow_event: could not emit to event_bus", exc_info=True)


def build_crew(
    agent: Any,
    task_prompt: tuple[str, str],
    *,
    verbose: bool = True,
    output_pydantic: type | None = None,
    guardrail: Any | None = None,
    guardrail_max_retries: int = 5,
    task_tools: list | None = None,
) -> Any:
    """Build a Crew with a single agent and task, applying PABADA defaults.

    Centralizes Crew+Task construction so that ``max_rpm``, guardrails,
    ``output_pydantic``, and task-specific tools are configured consistently
    across all flows.

    Returns:
        A ready-to-kickoff ``Crew`` instance.
    """
    from crewai import Crew, Task

    from backend.config.settings import settings
    from backend.knowledge.service import KnowledgeService

    memory_kwargs = KnowledgeService.build_crew_memory_kwargs()

    desc, expected = task_prompt
    task_kwargs: dict[str, Any] = {
        "description": desc,
        "agent": agent.crewai_agent,
        "expected_output": expected,
    }
    if output_pydantic is not None:
        task_kwargs["output_pydantic"] = output_pydantic
    if guardrail is not None:
        task_kwargs["guardrail"] = guardrail
        task_kwargs["guardrail_max_retries"] = guardrail_max_retries
    if task_tools is not None:
        # Stamp task-specific tools with the agent's ID so they can look up
        # context from the process-global dict even in worker threads (CrewAI
        # runs tools in a ThreadPoolExecutor when max_execution_time is set).
        from backend.tools.base.context import bind_tools_to_agent

        bind_tools_to_agent(task_tools, agent.agent_id)
        task_kwargs["tools"] = task_tools

    return Crew(
        agents=[agent.crewai_agent],
        tasks=[Task(**task_kwargs)],
        verbose=verbose,
        max_rpm=settings.CREW_MAX_RPM,
        **memory_kwargs,
    )


def run_agent_task(
    agent: Any,
    task_prompt: tuple[str, str],
    *,
    task_id: int | None = None,
    track_run: bool = False,
    verbose: bool = True,
    output_pydantic: type | None = None,
    guardrail: Any | None = None,
    guardrail_max_retries: int = 5,
    task_tools: list | None = None,
) -> str:
    """Run a single CrewAI task on *agent* and return the string result.

    Encapsulates the Crew + Task boilerplate used across all flows:
    activate context -> (optionally) create agent_run -> build Crew -> kickoff ->
    (optionally) complete agent_run.

    Args:
        agent: A ``PabadaAgent`` instance (caller is responsible for acquisition).
        task_prompt: ``(description, expected_output)`` tuple from a prompt function.
        task_id: Passed to ``activate_context`` for tool-level context.
        track_run: If True, calls ``create_agent_run`` / ``complete_agent_run``.
        verbose: Crew verbosity flag.
        output_pydantic: Pydantic model class for structured output validation.
        guardrail: Task guardrail function or LLM-based string.
        guardrail_max_retries: Max retries when guardrail validation fails.
        task_tools: Override task-specific tools (subset of agent tools).
    """
    agent.activate_context(task_id=task_id)

    run_id: str | None = None
    if track_run and task_id is not None:
        run_id = agent.create_agent_run(task_id)

    crew = build_crew(
        agent, task_prompt,
        verbose=verbose,
        output_pydantic=output_pydantic,
        guardrail=guardrail,
        guardrail_max_retries=guardrail_max_retries,
        task_tools=task_tools,
    )

    try:
        result = kickoff_with_retry(crew)
        result_str = str(result)
    except Exception as exc:
        if run_id:
            agent.complete_agent_run(
                run_id, status="failed", error_class=type(exc).__name__,
            )
        raise

    if run_id:
        agent.complete_agent_run(
            run_id, status="completed", output_summary=result_str[:500],
        )

    return result_str


def calculate_time_elapsed(start_time: str) -> float:
    """Calculate seconds elapsed since start_time (ISO format string)."""
    if not start_time:
        return 0.0
    start = datetime.fromisoformat(start_time)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - start).total_seconds()
