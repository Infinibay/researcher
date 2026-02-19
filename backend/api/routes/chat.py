"""Chat message endpoints."""

from __future__ import annotations

import sqlite3
import uuid

from fastapi import APIRouter, Query

from backend.api.models.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatThreadResponse,
    UnreadCountsResponse,
    ThreadArchiveResponse,
)
from backend.communication.service import CommunicationService
from backend.communication.thread_manager import ThreadManager
from backend.flows.event_listeners import FlowEvent, event_bus
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/{project_id}", response_model=list[ChatMessageResponse])
async def list_messages(
    project_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    after_id: int | None = Query(default=None),
):
    """List chat messages, optionally after a given ID for polling."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        where = "cm.project_id = ?"
        params: list = [project_id]

        if after_id is not None:
            where += " AND cm.id > ?"
            params.append(after_id)

        params.append(limit)
        rows = conn.execute(
            f"""SELECT cm.*
                FROM chat_messages cm
                WHERE {where}
                ORDER BY cm.created_at DESC
                LIMIT ?""",
            params,
        ).fetchall()
        # Return in chronological order
        return [dict(r) for r in reversed(rows)]

    messages = execute_with_retry(_query)
    return [ChatMessageResponse(**m) for m in messages]


@router.post("/{project_id}", response_model=ChatMessageResponse, status_code=201)
async def send_message(project_id: int, body: ChatMessageCreate):
    """Send a user message. The event listener will process it."""

    def _create(conn: sqlite3.Connection) -> dict:
        # Create or reuse a thread
        thread_id = str(uuid.uuid4())
        conn.execute(
            """INSERT OR IGNORE INTO conversation_threads
               (thread_id, project_id, thread_type, created_at)
               VALUES (?, ?, 'user_chat', CURRENT_TIMESTAMP)""",
            (thread_id, project_id),
        )

        cursor = conn.execute(
            """INSERT INTO chat_messages
               (project_id, thread_id, from_agent, to_agent, to_role,
                message, conversation_type, created_at)
               VALUES (?, ?, 'user', ?, ?, ?, 'user_to_agent', CURRENT_TIMESTAMP)""",
            (project_id, thread_id, body.to_agent, body.to_role,
             body.message),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    message = execute_with_retry(_create)
    return ChatMessageResponse(**message)


@router.get("/{project_id}/threads", response_model=list[ChatThreadResponse])
async def list_threads(project_id: int):
    """List conversation threads with last message."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT ct.thread_id, ct.project_id, ct.thread_type, ct.created_at,
                      (SELECT message FROM chat_messages cm
                       WHERE cm.thread_id = ct.thread_id
                       ORDER BY cm.created_at DESC LIMIT 1) as last_message,
                      (SELECT COUNT(*) FROM chat_messages cm
                       WHERE cm.thread_id = ct.thread_id) as message_count
               FROM conversation_threads ct
               WHERE ct.project_id = ?
               ORDER BY ct.created_at DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    threads = execute_with_retry(_query)
    return [ChatThreadResponse(**t) for t in threads]


@router.get("/{project_id}/threads/{thread_id}", response_model=list[ChatMessageResponse])
async def get_thread_messages(project_id: int, thread_id: str):
    """Get all messages in a thread."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT * FROM chat_messages
               WHERE thread_id = ? AND project_id = ?
               ORDER BY created_at ASC""",
            (thread_id, project_id),
        ).fetchall()
        return [dict(r) for r in rows]

    messages = execute_with_retry(_query)
    return [ChatMessageResponse(**m) for m in messages]


@router.get("/{project_id}/unread", response_model=UnreadCountsResponse)
async def get_unread_counts(project_id: int):
    """Return per-agent unread message counts."""

    def _query(conn: sqlite3.Connection) -> dict[str, int]:
        rows = conn.execute(
            """SELECT
                   COALESCE(cm.to_agent, cm.to_role) as target,
                   COUNT(*) as cnt
               FROM chat_messages cm
               WHERE cm.project_id = ?
                 AND (cm.to_agent IS NOT NULL OR cm.to_role IS NOT NULL)
                 AND NOT EXISTS (
                     SELECT 1 FROM message_reads mr
                     WHERE mr.message_id = cm.id
                       AND (
                           -- Agent-targeted: read by the specific agent
                           (cm.to_agent IS NOT NULL AND mr.agent_id = cm.to_agent)
                           OR
                           -- Role-targeted: read by any agent with that role
                           (cm.to_agent IS NULL AND cm.to_role IS NOT NULL
                            AND mr.agent_id IN (
                               SELECT r.agent_id FROM roster r
                               WHERE r.role = cm.to_role
                                 AND r.project_id = cm.project_id
                            ))
                       )
                 )
               GROUP BY target""",
            (project_id,),
        ).fetchall()
        return {r["target"]: r["cnt"] for r in rows if r["target"]}

    counts = execute_with_retry(_query)
    return UnreadCountsResponse(counts=counts)


@router.post(
    "/{project_id}/threads/{thread_id}/archive",
    response_model=ThreadArchiveResponse,
    status_code=200,
)
async def archive_thread(project_id: int, thread_id: str):
    """Archive a conversation thread."""
    tm = ThreadManager()
    tm.archive_thread(thread_id)

    event_bus.emit(
        FlowEvent(
            event_type="thread_archived",
            project_id=project_id,
            entity_type="thread",
            data={"thread_id": thread_id},
        )
    )
    return ThreadArchiveResponse(thread_id=thread_id, status="archived")


@router.get("/{project_id}/agent/{agent_id}", response_model=list[ChatMessageResponse])
async def get_agent_messages(
    project_id: int,
    agent_id: str,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Return messages directed at a specific agent (by agent id or role)."""
    comms = CommunicationService()
    messages = comms.get_messages(
        project_id=project_id,
        agent_id=agent_id,
        unread_only=unread_only,
        limit=limit,
    )
    return [ChatMessageResponse(**m) for m in messages]
