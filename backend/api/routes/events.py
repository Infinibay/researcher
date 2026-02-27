"""Events log endpoint — provides historical events for the activity feed."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/events", tags=["events"])


class EventResponse(BaseModel):
    id: int
    type: str
    project_id: int
    entity_type: str | None = None
    entity_id: int | None = None
    data: dict | None = None
    timestamp: str | None = None


@router.get("/{project_id}", response_model=list[EventResponse])
async def list_events(
    project_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    after_id: int | None = Query(default=None),
):
    """Return recent events for a project, newest first.

    Use ``after_id`` for forward-pagination (events created after the given id).
    """

    def _query(conn: sqlite3.Connection) -> list[dict]:
        where = ["el.project_id = ?"]
        params: list = [project_id]

        if after_id is not None:
            where += ["el.id > ?"]
            params.append(after_id)

        params.append(limit)
        rows = conn.execute(
            f"""SELECT el.id, el.project_id, el.event_type, el.entity_type,
                       el.entity_id, el.event_data_json, el.created_at
                FROM events_log el
                WHERE {' AND '.join(where)}
                ORDER BY el.created_at DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    rows = execute_with_retry(_query)

    events: list[EventResponse] = []
    for r in rows:
        data = {}
        if r.get("event_data_json"):
            try:
                data = json.loads(r["event_data_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        events.append(EventResponse(
            id=r["id"],
            type=r["event_type"],
            project_id=r["project_id"],
            entity_type=r.get("entity_type"),
            entity_id=r.get("entity_id"),
            data=data,
            timestamp=r.get("created_at"),
        ))

    return events
