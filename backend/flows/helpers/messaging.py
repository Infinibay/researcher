"""Inter-agent messaging helpers for PABADA flows."""

from __future__ import annotations

import logging
import sqlite3
import uuid

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def send_agent_message(
    project_id: int,
    from_agent: str,
    to_agent: str | None,
    to_role: str | None,
    message: str,
    conversation_type: str = "agent_to_agent",
    thread_id: str | None = None,
) -> int:
    """Insert a chat_message and return its id."""

    def _insert(conn: sqlite3.Connection) -> int:
        # Ensure a thread exists; create a default one if thread_id is None
        actual_thread_id = thread_id
        if actual_thread_id is None:
            actual_thread_id = str(uuid.uuid4())
            conn.execute(
                """INSERT OR IGNORE INTO conversation_threads
                       (thread_id, project_id, thread_type, created_at)
                   VALUES (?, ?, 'team_sync', CURRENT_TIMESTAMP)""",
                (actual_thread_id, project_id),
            )

        cursor = conn.execute(
            """INSERT INTO chat_messages
                   (project_id, thread_id, from_agent, to_agent, to_role,
                    message, conversation_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (project_id, actual_thread_id, from_agent, to_agent, to_role,
             message, conversation_type),
        )
        conn.commit()
        return cursor.lastrowid

    message_id = execute_with_retry(_insert)

    # Create persistent agent_events for the message
    try:
        from backend.autonomy.events import create_message_event
        create_message_event(
            project_id=project_id,
            from_agent=from_agent,
            to_agent=to_agent,
            to_role=to_role,
            message=message,
            thread_id=thread_id,
            message_id=message_id,
            conversation_type=conversation_type,
        )
    except Exception:
        logger.debug("Could not create agent events for message", exc_info=True)

    return message_id


def _load_prd_and_plan(project_id: int) -> tuple[str, str]:
    """Load PRD (requirements) and plan text from the flow snapshot.

    Returns (prd, plan) — either may be empty if unavailable.
    """
    import json as _json

    from backend.flows.snapshot_service import load_snapshot

    snapshot = load_snapshot(project_id)
    if not snapshot:
        return "", ""
    state_raw = snapshot.get("state_json")
    if not state_raw:
        return "", ""
    try:
        state = _json.loads(state_raw) if isinstance(state_raw, str) else state_raw
    except Exception:
        return "", ""
    if not isinstance(state, dict):
        return "", ""
    return state.get("requirements", ""), state.get("plan", "")


def _truncate(text: str, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_enriched_message(
    project_id: int,
    question: str,
    sender_role: str | None = None,
    thread_id: str | None = None,
) -> str:
    """Prepend a compact project-state block to an outgoing question.

    Includes PRD/plan content when available — prefers PRD when the
    target is the Project Lead, plan when the target is the Team Lead,
    and combines both (clearly labeled) when sender_role is unset.

    If anything fails, returns the original question unchanged.
    """
    try:
        from backend.flows.helpers.db_helpers import load_project_state
        from backend.prompts.team import build_state_context

        project = load_project_state(project_id)
        if project is None:
            return question

        # Build summary from PRD/plan, falling back to project description
        prd, plan = _load_prd_and_plan(project_id)

        summary_parts: list[str] = []
        if sender_role == "project_lead":
            # Target is PL — prefer PRD
            if prd:
                summary_parts.append(f"PRD: {_truncate(prd)}")
            if plan:
                summary_parts.append(f"Plan: {_truncate(plan)}")
        elif sender_role == "team_lead":
            # Target is TL — prefer plan
            if plan:
                summary_parts.append(f"Plan: {_truncate(plan)}")
            if prd:
                summary_parts.append(f"PRD: {_truncate(prd)}")
        else:
            # Unknown target — include both if available
            if prd:
                summary_parts.append(f"PRD: {_truncate(prd)}")
            if plan:
                summary_parts.append(f"Plan: {_truncate(plan)}")

        # Fall back to project description if no PRD/plan available
        if not summary_parts:
            description = project.get("description") or ""
            if description:
                summary_parts.append(_truncate(description))

        summary = " | ".join(summary_parts)

        extra: dict[str, str] = {}
        if thread_id:
            extra["Thread"] = thread_id

        state_block = build_state_context(
            project_id=project_id,
            project_name=project.get("name", "Unknown"),
            phase=project.get("status", "unknown"),
            summary=summary,
            extra=extra or None,
        )

        return f"{state_block}\n\n## Question\n{question}"
    except Exception:
        logger.debug("build_enriched_message failed, returning raw question", exc_info=True)
        return question


def notify_team_lead(project_id: int, from_agent: str, message: str) -> int:
    """Send a message to the Team Lead role."""
    return send_agent_message(
        project_id=project_id,
        from_agent=from_agent,
        to_agent=None,
        to_role="team_lead",
        message=message,
    )
