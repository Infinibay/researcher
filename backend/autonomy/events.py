"""Persistent event creation helpers for the agent loop system.

These functions INSERT rows into ``agent_events`` which the AgentLoop picks up.
They replace the ephemeral EventBus → handler chain for agent work scheduling.

Import safety: uses ``backend.autonomy.db`` to avoid circular imports.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from backend.autonomy.db import execute_with_retry

logger = logging.getLogger(__name__)

# Default priorities (lower = higher priority)
PRIORITY_URGENT = 10
PRIORITY_HIGH = 20
PRIORITY_NORMAL = 50
PRIORITY_LOW = 80

# Event type → default priority mapping
_DEFAULT_PRIORITIES: dict[str, int] = {
    "message_received": PRIORITY_HIGH,
    "user_message_received": PRIORITY_URGENT,
    "task_available": PRIORITY_NORMAL,
    "task_resume": PRIORITY_HIGH,
    "review_ready": PRIORITY_HIGH,
    "task_rejected": PRIORITY_HIGH,
    "stagnation_detected": PRIORITY_HIGH,
    "health_check": PRIORITY_NORMAL,
    "evaluate_progress": PRIORITY_LOW,
    "all_tasks_done": PRIORITY_HIGH,
    "waiting_for_research": PRIORITY_LOW,
}


def _resolve_agents_for_role(project_id: int, role: str) -> list[str]:
    """Look up agent IDs from the roster for a given role and project.

    Uses direct DB query to avoid importing AgentResolver (circular import risk).
    """

    def _query(conn: sqlite3.Connection) -> list[str]:
        rows = conn.execute(
            """SELECT agent_id FROM roster
               WHERE agent_id LIKE ? ESCAPE '\\' AND role = ? AND status != 'retired'""",
            (f"%\\_p{project_id}", role),
        ).fetchall()
        return [r["agent_id"] for r in rows]

    return execute_with_retry(_query)


def has_pending_review_event(project_id: int, task_id: int) -> bool:
    """Check if there is already an unprocessed review_ready event for a task.

    Returns True if any agent_event with event_type='review_ready' and
    status in ('pending', 'claimed', 'in_progress') exists for this task.
    Prevents duplicate reviews when a flow already manages its own review cycle.
    """

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM agent_events
               WHERE project_id = ?
                 AND event_type = 'review_ready'
                 AND status IN ('pending', 'claimed', 'in_progress')
                 AND payload_json LIKE ?""",
            (project_id, f'%"task_id": {task_id}%'),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    try:
        return execute_with_retry(_query)
    except Exception:
        logger.debug("has_pending_review_event check failed", exc_info=True)
        return False


def create_task_event(
    project_id: int,
    task_id: int,
    event_type: str,
    *,
    target_agent_id: str | None = None,
    target_role: str | None = None,
    source: str = "system",
    priority: int | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> list[int]:
    """Create agent_events for a task-related change.

    If ``target_agent_id`` is given, creates one event for that agent.
    If ``target_role`` is given, resolves all agents with that role and
    creates one event each.
    If neither is given, no events are created.

    Returns list of created event IDs.
    """
    agent_ids: list[str] = []
    if target_agent_id:
        agent_ids = [target_agent_id]
    elif target_role:
        agent_ids = _resolve_agents_for_role(project_id, target_role)

    if not agent_ids:
        return []

    effective_priority = priority if priority is not None else _DEFAULT_PRIORITIES.get(event_type, PRIORITY_NORMAL)
    payload = {"task_id": task_id}
    if extra_payload:
        payload.update(extra_payload)
    payload_str = json.dumps(payload)

    created_ids: list[int] = []
    for agent_id in agent_ids:
        event_id = _insert_event(
            agent_id=agent_id,
            project_id=project_id,
            event_type=event_type,
            source=source,
            priority=effective_priority,
            payload_json=payload_str,
        )
        if event_id:
            created_ids.append(event_id)

    return created_ids


def create_message_event(
    project_id: int,
    from_agent: str,
    to_agent: str | None,
    to_role: str | None,
    message: str,
    thread_id: str | None = None,
    message_id: int | None = None,
    conversation_type: str = "agent_to_agent",
) -> list[int]:
    """Create agent_events for an incoming message.

    Routes to specific agent or all agents of a role.
    Returns list of created event IDs.
    """
    # Skip creating events for "system" targets — nobody consumes them
    if to_agent == "system" or to_role == "system":
        return []

    # Skip creating dispatch events for system-originated messages (stagnation
    # alerts, progress updates, etc.).  The message is already persisted in
    # chat_messages (visible in the UI) before this function is called; we
    # only prevent the autonomy layer from kicking off a Crew task for it.
    if from_agent == "system":
        return []

    agent_ids: list[str] = []
    if to_agent:
        agent_ids = [to_agent]
    elif to_role:
        # Need project_id to look up roster — extract from agent_id convention
        agent_ids = _resolve_agents_for_role(project_id, to_role)

    if not agent_ids:
        return []

    event_type = "user_message_received" if conversation_type == "user_to_agent" else "message_received"
    priority = _DEFAULT_PRIORITIES.get(event_type, PRIORITY_NORMAL)

    payload: dict[str, Any] = {
        "from_agent": from_agent,
        "message": message[:2000],  # Truncate very long messages in payload
        "conversation_type": conversation_type,
    }
    if thread_id:
        payload["thread_id"] = thread_id
    if message_id:
        payload["message_id"] = message_id
    payload_str = json.dumps(payload)

    created_ids: list[int] = []
    for agent_id in agent_ids:
        event_id = _insert_event(
            agent_id=agent_id,
            project_id=project_id,
            event_type=event_type,
            source=from_agent,
            priority=priority,
            payload_json=payload_str,
        )
        if event_id:
            created_ids.append(event_id)

    return created_ids


def create_system_event(
    project_id: int,
    agent_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    priority: int | None = None,
    source: str = "system",
) -> int | None:
    """Create a generic system event for a specific agent.

    Used for stagnation detection, health checks, progress evaluation, etc.
    Returns the created event ID or None on failure.
    """
    effective_priority = priority if priority is not None else _DEFAULT_PRIORITIES.get(event_type, PRIORITY_NORMAL)
    payload_str = json.dumps(payload or {})

    return _insert_event(
        agent_id=agent_id,
        project_id=project_id,
        event_type=event_type,
        source=source,
        priority=effective_priority,
        payload_json=payload_str,
    )


def _insert_event(
    agent_id: str,
    project_id: int,
    event_type: str,
    source: str,
    priority: int,
    payload_json: str,
) -> int | None:
    """Insert a single agent_event row. Returns the event ID or None."""

    def _insert(conn: sqlite3.Connection) -> int:
        cursor = conn.execute(
            """INSERT INTO agent_events
                   (agent_id, project_id, event_type, source, priority, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_id, project_id, event_type, source, priority, payload_json),
        )
        conn.commit()
        return cursor.lastrowid

    try:
        return execute_with_retry(_insert)
    except Exception:
        logger.warning(
            "Failed to create agent_event (agent=%s, type=%s)",
            agent_id, event_type, exc_info=True,
        )
        return None


# -- Event lifecycle helpers (used by AgentLoop) ---------------------------


def poll_pending_events(agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch pending events for an agent, ordered by priority then creation time."""

    def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT id, agent_id, project_id, event_type, source, priority,
                      status, payload_json, progress_json, created_at
               FROM agent_events
               WHERE agent_id = ? AND status = 'pending'
               ORDER BY priority ASC, created_at ASC
               LIMIT ?""",
            (agent_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    return execute_with_retry(_query)


def atomic_claim_event(event_id: int, agent_id: str) -> bool:
    """Atomically claim an event. Returns True if successful."""

    def _claim(conn: sqlite3.Connection) -> bool:
        cursor = conn.execute(
            """UPDATE agent_events
               SET status = 'claimed', claimed_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status = 'pending' AND agent_id = ?""",
            (event_id, agent_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    return execute_with_retry(_claim)


def update_event_status(
    event_id: int,
    status: str,
    *,
    error: str | None = None,
    progress: dict[str, Any] | None = None,
) -> None:
    """Update an event's status and optional error/progress fields."""

    def _update(conn: sqlite3.Connection) -> None:
        parts = ["status = ?"]
        params: list[Any] = [status]

        if status == "in_progress":
            parts.append("started_at = CURRENT_TIMESTAMP")
        elif status in ("completed", "failed"):
            parts.append("completed_at = CURRENT_TIMESTAMP")

        if error is not None:
            parts.append("error_message = ?")
            params.append(error)

        if progress is not None:
            parts.append("progress_json = ?")
            params.append(json.dumps(progress))

        params.append(event_id)
        conn.execute(
            f"UPDATE agent_events SET {', '.join(parts)} WHERE id = ?",
            params,
        )
        conn.commit()

    execute_with_retry(_update)


def get_event_by_id(event_id: int) -> dict[str, Any] | None:
    """Load a single agent_event by ID."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM agent_events WHERE id = ?", (event_id,),
        ).fetchone()
        return dict(row) if row else None

    return execute_with_retry(_query)


def cancel_pending_events(agent_id: str, project_id: int) -> int:
    """Cancel all pending events for an agent. Returns count cancelled."""

    def _cancel(conn: sqlite3.Connection) -> int:
        cursor = conn.execute(
            """UPDATE agent_events SET status = 'cancelled'
               WHERE agent_id = ? AND project_id = ? AND status = 'pending'""",
            (agent_id, project_id),
        )
        conn.commit()
        return cursor.rowcount

    return execute_with_retry(_cancel)


# -- Loop state helpers ----------------------------------------------------


def save_loop_state(
    agent_id: str,
    project_id: int,
    current_event_id: int | None,
    status: str,
    last_error: str | None = None,
    consecutive_errors: int = 0,
) -> None:
    """Upsert the agent_loop_state for crash recovery."""

    def _upsert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO agent_loop_state
                   (agent_id, project_id, status, current_event_id,
                    last_poll_at, last_error, consecutive_errors, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(agent_id) DO UPDATE SET
                   status = excluded.status,
                   current_event_id = excluded.current_event_id,
                   last_poll_at = CURRENT_TIMESTAMP,
                   last_error = excluded.last_error,
                   consecutive_errors = excluded.consecutive_errors,
                   updated_at = CURRENT_TIMESTAMP""",
            (agent_id, project_id, status, current_event_id,
             last_error, consecutive_errors),
        )
        conn.commit()

    execute_with_retry(_upsert)


def load_loop_state(agent_id: str) -> dict[str, Any] | None:
    """Load the agent_loop_state for an agent."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM agent_loop_state WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        return dict(row) if row else None

    return execute_with_retry(_query)
