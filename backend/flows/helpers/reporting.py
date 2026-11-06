"""Read historical project reports and events; legacy Crew/model activation helpers are retired in favor of explicit native owner runs."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

# Historical arguments remain readable, but no retry or provider is executed.
DEFAULT_LLM_RETRIES = 3
DEFAULT_LLM_RETRY_DELAY = 5.0


def kickoff_with_retry(
    crew: Any,
    *,
    max_retries: int = DEFAULT_LLM_RETRIES,
    base_delay: float = DEFAULT_LLM_RETRY_DELAY,
) -> Any:
    """Reject the retired Crew kickoff entry; retry arguments or an old approval never authorize model execution."""
    from backend.runtime.lifecycle import NativeOwnerRequired

    raise NativeOwnerRequired("Legacy Crew kickoff is retired; use an explicitly admitted native owner run")


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
        from backend.flows.event_bus import FlowEvent, event_bus

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
    """Reject old Crew construction in actual project scope before model, knowledge-service, context or tool initialization."""
    from backend.runtime.lifecycle import (
        NativeOwnerRequired,
        require_legacy_execution_project,
    )

    require_legacy_execution_project(agent.project_id)
    raise NativeOwnerRequired("Legacy Crew construction is retired; use native owner admission")


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
    """Reject automatic old agent tasks before context activation, run tracking or provider setup; historical keyword arguments confer no execution authority."""
    from backend.runtime.lifecycle import (
        NativeOwnerRequired,
        require_legacy_execution_project,
    )

    require_legacy_execution_project(agent.project_id)
    raise NativeOwnerRequired("Legacy agent tasks are retired; use native owner admission")


def calculate_time_elapsed(start_time: str) -> float:
    """Calculate seconds elapsed since start_time (ISO format string)."""
    if not start_time:
        return 0.0
    start = datetime.fromisoformat(start_time)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - start).total_seconds()
