"""Owner-readable durable event history using the same ascending cursor as live delivery."""

import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.runtime.event_history import EventHistory

router = APIRouter(prefix="/api/events", tags=["events"])


class EventResponse(BaseModel):
    """One committed observation with its durable identity and explicit missing payload state."""

    event_id: str
    type: str
    project_id: int
    source: str
    entity_type: str | None = None
    entity_id: int | None = None
    data: dict | None = None
    data_unavailable: bool
    timestamp: str | None = None


class EventPageResponse(BaseModel):
    """Bounded ascending page or an explicit snapshot refresh requirement after retention loss."""

    type: str
    project_id: int
    after_id: str
    next_after_id: str
    has_more: bool
    events: list[EventResponse]
    reset_required: bool
    resume_after_id: str | None
    reset_reason: str | None


@router.get("/{project_id}", response_model=EventPageResponse)
async def list_events(
    project_id: int,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    after_id: int = Query(default=0, ge=0, le=9223372036854775807),
):
    """Recover committed events in stable order; expired cursors cannot silently skip history."""
    from backend.api.routes.runs import read_store

    page = await asyncio.to_thread(EventHistory(read_store(request).database).page, project_id, after_id=after_id, limit=limit)
    return JSONResponse(page, headers={"Cache-Control": "no-store"})
