"""Dispatches incoming agent messages by spinning up a Crew task for the target agent."""

from __future__ import annotations

import logging
import sqlite3


from backend.engine.base import AgentKilledError as _AgentKilledError

logger = logging.getLogger(__name__)

_THREAD_HISTORY_LIMIT = 10


def _fetch_thread_history(project_id: int, thread_id: str) -> list[dict]:
    """Return the last N messages in *thread_id* for *project_id*, oldest-first.

    Returns an empty list on any DB error so dispatch is never blocked.
    """
    from backend.tools.base.db import execute_with_retry

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT from_agent, message, created_at
               FROM chat_messages
               WHERE project_id = ? AND thread_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (project_id, thread_id, _THREAD_HISTORY_LIMIT),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    try:
        return execute_with_retry(_query)
    except Exception:
        logger.debug("Could not fetch thread history for %s", thread_id, exc_info=True)
        return []


def _build_enriched_description(
    project_id: int,
    canonical_id: str,
    from_agent: str,
    content: str,
    thread_id: str | None,
    role: str | None = None,
) -> str:
    """Compose the full CrewTask description with project state, thread
    history, conversation context, and the original instruction."""
    from backend.flows.helpers.db_helpers import load_project_state
    from backend.prompts.team import build_conversation_context, build_state_context

    sections: list[str] = []

    # ── 1. Project state header ──────────────────────────────────────────
    try:
        project = load_project_state(project_id)
    except Exception:
        project = None

    extra: dict[str, str] = {}
    if role == "project_lead":
        extra["Role context"] = "PRD included below"
    elif role == "team_lead":
        extra["Role context"] = "Plan summary included below"

    if project:
        sections.append(build_state_context(
            project_id=project_id,
            project_name=project.get("name") or "Unknown Project",
            phase=project.get("status") or "unknown",
            summary=project.get("description") or "",
            extra=extra or None,
        ))
    else:
        sections.append(build_state_context(
            project_id=project_id,
            project_name="Unknown Project",
            phase="unknown",
            extra=extra or None,
        ))

    # ── 1b. Role-specific context ─────────────────────────────────────────
    try:
        if role == "project_lead":
            from backend.flows.helpers.messaging import _load_prd_and_plan

            prd, _ = _load_prd_and_plan(project_id)
            if prd:
                sections.append(f"## Project Requirements (PRD)\n{prd[:2000]}")
            elif project:
                desc = (project.get("description") or "")[:2000]
                if desc:
                    sections.append(f"## Project Requirements (PRD)\n{desc}")

        elif role == "team_lead":
            from backend.flows.helpers.db_helpers import get_project_progress_summary
            from backend.flows.helpers.messaging import _load_prd_and_plan

            progress = get_project_progress_summary(project_id)
            if progress:
                sections.append(f"## Current Project Plan\n{progress}")

            _, plan = _load_prd_and_plan(project_id)
            if plan:
                sections.append(f"## Planned Approach (Snapshot)\n{plan[:1000]}")
    except Exception:
        logger.debug("Could not load role-specific context for %s", role, exc_info=True)

    # ── 2. Thread-specific message history ───────────────────────────────
    if thread_id:
        history = _fetch_thread_history(project_id, thread_id)
        if history:
            lines = ["## Thread History"]
            for msg in history:
                text = (msg.get("message") or "")[:300]
                lines.append(f"- **{msg.get('from_agent', '?')}**: {text}")
            sections.append("\n".join(lines))

    # ── 3. Conversation context (Q&A + recent messages) ──────────────────
    try:
        conv_ctx = build_conversation_context(
            project_id=project_id,
            agent_id=canonical_id,
        )
        if conv_ctx:
            sections.append(conv_ctx)
    except Exception:
        logger.debug("Could not build conversation context", exc_info=True)

    # ── 4. Original instruction ──────────────────────────────────────────
    if from_agent == "user":
        tool_name = "reply_to_user"
        reply_instruction = (
            "You MUST reply using the `reply_to_user` tool with your response "
            "as the `message` parameter"
        )
        if thread_id:
            reply_instruction += f' and `thread_id="{thread_id}"`'
        reply_instruction += (
            ". Your reply must contain useful, actionable information — "
            "not just an acknowledgment. Do NOT write your answer as plain text."
        )
    else:
        tool_name = "send_message"
        reply_instruction = (
            f"Decide whether this message requires a response.\n\n"
            f"**Do NOT reply if:**\n"
            f"- The message is a simple acknowledgment (\"OK\", \"got it\", \"proceeding\")\n"
            f"- The message confirms something you already know\n"
            f"- Replying would not add new information or advance the project\n"
            f"- The conversation has already reached agreement\n\n"
            f"**Reply ONLY if** the message asks a question, requests action, "
            f"or contains information that requires your input.\n\n"
            f"If you decide to reply, use the `{tool_name}` tool with "
            f"`to_agent=\"{from_agent}\""
        )
        if thread_id:
            reply_instruction += f", thread_id=\"{thread_id}\""
        reply_instruction += (
            "`. Your reply must add new, useful information — "
            "never send acknowledgments like \"understood\" or \"will do\"."
        )

    sections.append(
        f"## Incoming Message\n"
        f"**From:** {from_agent}\n"
        f"**Message:**\n{content}\n\n"
        f"## Required Action\n"
        f"Read the message above carefully.\n\n"
        f"**CRITICAL:** {reply_instruction}\n\n"
        f"If no reply is needed, do NOT call any tool — simply move on."
    )

    return "\n\n".join(sections)


def dispatch_message(
    project_id: int,
    agent_id: str,
    from_agent: str,
    content: str,
    thread_id: str | None = None,
) -> None:
    """Run a Crew task so the target agent processes the incoming message."""
    from backend.agents.registry import get_agent_by_role
    from backend.flows.event_listeners import AgentResolver

    resolver = AgentResolver()

    try:
        # Resolve agent_id (may be a display name or composite like "role_name")
        resolved = resolver.resolve_identity(project_id, agent_id)
        if resolved is None:
            logger.warning(
                "Cannot resolve agent '%s' in project %d — skipping dispatch.",
                agent_id, project_id,
            )
            return
        canonical_id, role = resolved

        agent = get_agent_by_role(role, project_id, agent_id=canonical_id)
        agent.activate_context()

        description = _build_enriched_description(
            project_id, canonical_id, from_agent, content, thread_id, role=role,
        )

        from backend.engine import get_engine
        reply_tool = "send_message"
        if from_agent == "user":
            expected = (
                f"Confirmation that you called the `{reply_tool}` tool to reply. "
                "Do NOT write the response as plain text — you MUST use the tool."
            )
        else:
            expected = (
                f"Either a reply via the `{reply_tool}` tool (if the message "
                "requires a response), or nothing if no reply is needed."
            )
        get_engine().execute(agent, (description, expected))
        logger.info(
            "Message dispatched to agent %s (project %d) from %s",
            agent_id, project_id, from_agent,
        )
    except _AgentKilledError:
        logger.info(
            "Message dispatch to agent %s interrupted (agent killed)", agent_id,
        )
    except Exception:
        logger.exception(
            "Failed to dispatch message to agent %s (project %d)",
            agent_id, project_id,
        )
