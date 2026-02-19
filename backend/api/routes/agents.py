"""Agent roster and activity endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter

from backend.api.models.agent import (
    AgentCurrentRun,
    AgentList,
    AgentPerformanceInfo,
    AgentResponse,
)
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=AgentList)
async def list_agents(project_id: int | None = None):
    """List all agents, optionally filtered by project.

    Includes current running task (if any) and performance metrics.
    """

    def _query(conn: sqlite3.Connection) -> list[dict]:
        # Build roster query — filter by project suffix if provided
        if project_id is not None:
            like_pattern = f"%\\_p{project_id}"
            roster_rows = conn.execute(
                r"""SELECT agent_id, name, role, status, total_runs,
                          created_at, last_active_at
                   FROM roster
                   WHERE agent_id LIKE ? ESCAPE '\'
                     AND status != 'retired'
                   ORDER BY role, created_at""",
                (like_pattern,),
            ).fetchall()
        else:
            roster_rows = conn.execute(
                """SELECT agent_id, name, role, status, total_runs,
                          created_at, last_active_at
                   FROM roster
                   WHERE status != 'retired'
                   ORDER BY role, created_at"""
            ).fetchall()

        agents = []
        for r in roster_rows:
            agent = dict(r)

            # Current running task
            run_row = conn.execute(
                """SELECT ar.agent_run_id, ar.task_id, t.title AS task_title,
                          ar.started_at
                   FROM agent_runs ar
                   LEFT JOIN tasks t ON t.id = ar.task_id
                   WHERE ar.agent_id = ? AND ar.status = 'running'
                   ORDER BY ar.started_at DESC
                   LIMIT 1""",
                (agent["agent_id"],),
            ).fetchone()
            agent["current_run"] = dict(run_row) if run_row else None

            # Performance metrics
            perf_row = conn.execute(
                """SELECT successful_runs, failed_runs, total_tokens,
                          total_cost_usd, avg_task_duration_s
                   FROM agent_performance
                   WHERE agent_id = ?""",
                (agent["agent_id"],),
            ).fetchone()
            agent["performance"] = dict(perf_row) if perf_row else None

            agents.append(agent)

        return agents

    rows = execute_with_retry(_query)

    agents = []
    for row in rows:
        current_run = None
        if row.get("current_run"):
            current_run = AgentCurrentRun(**row["current_run"])

        performance = None
        if row.get("performance"):
            performance = AgentPerformanceInfo(**row["performance"])

        agents.append(
            AgentResponse(
                agent_id=row["agent_id"],
                name=row["name"],
                role=row["role"],
                status=row["status"],
                total_runs=row.get("total_runs", 0),
                created_at=row.get("created_at"),
                last_active_at=row.get("last_active_at"),
                current_run=current_run,
                performance=performance,
            )
        )

    return AgentList(agents=agents, total=len(agents))
