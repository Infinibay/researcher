"""User request endpoints — lets the frontend respond to agent questions."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException

from backend.api.models.user_request import (
    UserRequestList,
    UserRequestRespond,
    UserRequestResponse,
)
from backend.flows.event_listeners import FlowEvent, event_bus
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/user-requests", tags=["user-requests"])


@router.get("/{project_id}/pending", response_model=UserRequestList)
async def list_pending_requests(project_id: int):
    """Return all pending user requests for a project (FIFO order)."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT * FROM user_requests
               WHERE project_id = ? AND status = 'pending'
               ORDER BY id ASC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    requests = execute_with_retry(_query)
    return UserRequestList(
        requests=[UserRequestResponse(**r) for r in requests],
        total=len(requests),
    )


@router.post("/{request_id}/respond", response_model=UserRequestResponse)
async def respond_to_request(request_id: int, body: UserRequestRespond):
    """Submit a response to a pending user request."""

    def _respond(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT * FROM user_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if not row:
            return None
        if row["status"] != "pending":
            return None

        conn.execute(
            """UPDATE user_requests
               SET status = 'responded',
                   response = ?,
                   responded_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (body.response, request_id),
        )
        conn.commit()

        updated = conn.execute(
            "SELECT * FROM user_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(updated)

    result = execute_with_retry(_respond)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Request not found or already responded to",
        )

    # Mirror the user's response as a chat_message so it persists in chat history
    def _mirror_response(conn: sqlite3.Connection) -> None:
        pid = result["project_id"]
        thread_id = f"user-qa-p{pid}"
        conn.execute(
            """INSERT OR IGNORE INTO conversation_threads
               (thread_id, project_id, thread_type, created_at)
               VALUES (?, ?, 'user_chat', CURRENT_TIMESTAMP)""",
            (thread_id, pid),
        )
        conn.execute(
            """INSERT INTO chat_messages
               (project_id, thread_id, from_agent, to_agent, message,
                conversation_type, created_at)
               VALUES (?, ?, 'user', ?, ?, 'user_to_agent', CURRENT_TIMESTAMP)""",
            (pid, thread_id, result["agent_id"], body.response),
        )
        conn.commit()

    try:
        execute_with_retry(_mirror_response)
    except Exception:
        pass  # Non-fatal — the user_request table is the source of truth

    event_bus.emit(
        FlowEvent(
            event_type="user_request_responded",
            project_id=result["project_id"],
            entity_type="user_request",
            entity_id=request_id,
            data={"status": "responded"},
        )
    )

    return UserRequestResponse(**result)
