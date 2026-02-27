"""Read-only endpoint exposing the current flow snapshot for a project."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.flows.snapshot_service import load_snapshot

router = APIRouter(prefix="/api/flow-state", tags=["flow"])

_SUMMARY_KEYS = (
    "status",
    "project_name",
    "completed_tasks",
    "total_tasks",
    "current_task_id",
    "current_task_type",
)


class FlowStateResponse(BaseModel):
    flow_name: str | None = None
    current_step: str | None = None
    subflow_name: str | None = None
    subflow_step: str | None = None
    state_summary: dict | None = None
    updated_at: str | None = None


@router.get("/{project_id}", response_model=FlowStateResponse)
async def get_flow_state(project_id: int) -> FlowStateResponse:
    snapshot = load_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No flow snapshot found")

    state_summary: dict | None = None
    raw = snapshot.get("state_json")
    if raw:
        try:
            full_state = json.loads(raw)
            state_summary = {k: full_state[k] for k in _SUMMARY_KEYS if k in full_state}
        except (json.JSONDecodeError, TypeError):
            state_summary = None

    return FlowStateResponse(
        flow_name=snapshot.get("flow_name"),
        current_step=snapshot.get("current_step"),
        subflow_name=snapshot.get("subflow_name"),
        subflow_step=snapshot.get("subflow_step"),
        state_summary=state_summary,
        updated_at=snapshot.get("updated_at"),
    )
