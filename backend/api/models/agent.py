"""Pydantic models for agent resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentCurrentRun(BaseModel):
    agent_run_id: str
    task_id: int
    task_title: str | None = None
    started_at: str | None = None


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    role: str
    status: str
    total_runs: int = 0
    created_at: str | None = None
    last_active_at: str | None = None
    current_run: AgentCurrentRun | None = None
    performance: AgentPerformanceInfo | None = None


class AgentPerformanceInfo(BaseModel):
    successful_runs: int = 0
    failed_runs: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_task_duration_s: float | None = None


# Rebuild AgentResponse now that AgentPerformanceInfo is defined
AgentResponse.model_rebuild()


class AgentList(BaseModel):
    agents: list[AgentResponse]
    total: int
