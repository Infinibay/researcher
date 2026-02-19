"""Shared team definitions and context builders for all PABADA agents.

Provides:
- ROLE_DESCRIPTIONS: static info about what each role does.
- NAME_POOL: names for random agent name generation.
- generate_agent_name(): pick a unique name for a new agent.
- build_team_section(): build the "Your Team" block from live roster data.
- build_state_context(): build a timestamped project state block for tasks.

Architecture note:
  Names are generated randomly at agent creation time and stored in the
  ``roster`` DB table.  The system prompt receives the *live* roster
  (agent_name + teammates list) so it always reflects the current team,
  regardless of how many agents of each role exist.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any


# ── Role Descriptions (static) ───────────────────────────────────────────────
# What each role type does.  Used in the "Your Team" section of system prompts
# so every agent knows what every role is responsible for.

ROLE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "project_lead": {
        "title": "Project Lead",
        "summary": (
            "The sole point of contact with the human user. Gathers and "
            "clarifies requirements, produces the PRD, and presents "
            "deliverables to the user for approval. Does NOT make technical "
            "decisions."
        ),
    },
    "team_lead": {
        "title": "Team Lead",
        "summary": (
            "Technical coordinator and planner. Receives the PRD from the "
            "Project Lead, creates the execution plan (epics, milestones, "
            "tasks), assigns work, and monitors progress. Makes technical "
            "architecture decisions."
        ),
    },
    "developer": {
        "title": "Developer",
        "summary": (
            "Code implementation specialist. Writes high-quality code per "
            "task specifications, creates branches, commits, and pull "
            "requests. Reports progress via task status updates."
        ),
    },
    "code_reviewer": {
        "title": "Code Reviewer",
        "summary": (
            "Quality assurance for code changes. Reviews pull requests, "
            "validates code quality, performance, and adherence to "
            "specifications. Can approve or reject deliverables."
        ),
    },
    "researcher": {
        "title": "Researcher",
        "summary": (
            "Scientific investigation specialist. Conducts literature "
            "reviews, formulates hypotheses, runs experiments, and documents "
            "findings. Uses web search and paper reading tools."
        ),
    },
    "research_reviewer": {
        "title": "Research Reviewer",
        "summary": (
            "Scientific peer review specialist. Validates research rigor, "
            "methodology, and conclusions. Can approve or reject findings."
        ),
    },
}


# ── Communication Rules (static, by role type) ──────────────────────────────
# These reference role titles, not specific names, so they work regardless of
# how many agents exist.

COMMUNICATION_RULES: dict[str, str] = {
    "project_lead": (
        "You are the ONLY agent who can communicate with the human user "
        "(via AskUserTool). Other agents contact you via AskProjectLeadTool "
        "when they need user input or have questions about requirements."
    ),
    "team_lead": (
        "You communicate with the Project Lead via AskProjectLeadTool when "
        "you need clarification on requirements or user decisions. You "
        "coordinate with Developers, Researchers, and Reviewers via "
        "SendMessageTool."
    ),
    "developer": (
        "You communicate with the Team Lead via AskTeamLeadTool when you "
        "need guidance. You can message other team members via "
        "SendMessageTool."
    ),
    "code_reviewer": (
        "You communicate with the team via SendMessageTool. You provide "
        "feedback on pull requests through task comments."
    ),
    "researcher": (
        "You communicate with the Team Lead via AskTeamLeadTool when you "
        "need guidance. You can message other team members via "
        "SendMessageTool."
    ),
    "research_reviewer": (
        "You communicate with the team via SendMessageTool. You provide "
        "feedback on research through task comments and finding validation."
    ),
}


# ── Name Pool ────────────────────────────────────────────────────────────────
# Gender-neutral English first names used for random agent naming.
# When an agent is created, it picks one not already in use in the project.

NAME_POOL: list[str] = [
    "Alex", "Jordan", "Sam", "Casey", "Riley", "Morgan", "Taylor", "Quinn",
    "Avery", "Blake", "Charlie", "Dakota", "Emery", "Finley", "Harper",
    "Jamie", "Kai", "Logan", "Noel", "Parker", "Reese", "Sage", "Skyler",
    "Drew", "Ellis", "Francis", "Glenn", "Hayden", "Indigo", "Jesse",
    "Kerry", "Lane", "Marley", "Nico", "Oakley", "Peyton", "Robin",
    "Shay", "Tatum", "Val", "Wren", "Arden", "Blair", "Cameron", "Devon",
    "Eden", "Frankie", "Gray", "Hollis",
]


def generate_agent_name(existing_names: set[str] | None = None) -> str:
    """Pick a random name from the pool that is not already in use.

    Args:
        existing_names: Names already assigned to agents in this project.
            Pass the set of names from the roster table.

    Returns:
        A unique name string.
    """
    used = existing_names or set()
    available = [n for n in NAME_POOL if n not in used]
    if not available:
        # Extremely unlikely: all 50 names are taken.  Fall back to
        # name + number.
        base = random.choice(NAME_POOL)
        i = 2
        while f"{base} {i}" in used:
            i += 1
        return f"{base} {i}"
    return random.choice(available)


def get_role_title(role: str) -> str:
    """Return the title (e.g. 'Team Lead') for *role*."""
    return ROLE_DESCRIPTIONS[role]["title"]


# ── Prompt Builders ──────────────────────────────────────────────────────────


def build_team_section(
    *,
    my_name: str,
    my_role: str,
    teammates: list[dict[str, str]] | None = None,
) -> str:
    """Build the '## Your Team' section for a system prompt.

    Uses the live roster data (queried from the DB) so it always reflects
    the actual team composition, not a hardcoded list.

    Args:
        my_name: This agent's assigned name.
        my_role: This agent's role key.
        teammates: List of dicts with keys ``name``, ``role``, ``status``.
            Comes from the ``roster`` table.  Can be empty or None if no
            other agents are registered yet.
    """
    my_title = ROLE_DESCRIPTIONS[my_role]["title"]
    my_summary = ROLE_DESCRIPTIONS[my_role]["summary"]

    lines = [
        "## Your Team\n",
        f"- **{my_name}** — {my_title} **(You)**\n  {my_summary}",
    ]

    if teammates:
        for mate in teammates:
            role = mate["role"]
            name = mate["name"]
            status = mate.get("status", "idle")
            desc = ROLE_DESCRIPTIONS.get(role, {})
            title = desc.get("title", role)
            summary = desc.get("summary", "")
            status_tag = f" [{status}]" if status != "idle" else ""
            lines.append(
                f"- **{name}** — {title}{status_tag}\n  {summary}"
            )
    else:
        lines.append(
            "\n_No other team members registered yet. They will join as "
            "the project progresses._"
        )

    lines.append("")
    comm = COMMUNICATION_RULES.get(my_role, "")
    if comm:
        lines.append(f"## Communication Protocol\n{comm}")

    # Append universal clarification protocol to all agents
    lines.append("")
    lines.append(build_clarification_protocol())

    return "\n".join(lines)


def build_clarification_protocol() -> str:
    """Return the universal clarification protocol block for all agents.

    This is appended to every agent's system prompt via build_team_section().
    """
    return """\
## Clarification Protocol

Follow these rules strictly when you need to clarify requirements:

1. **Check before asking**: Use ReadMessagesTool first to check if your
   question was already answered in a previous message or thread.
2. **Ask once, then proceed**: If you do not receive a response within the
   timeout, make a reasonable assumption, document it with AddCommentTool
   (prefix: `ASSUMPTION:`), and continue working.
3. **Max 2 clarification questions per task**: After asking 2 questions,
   proceed with your best judgment. Do NOT keep asking.
4. **Never re-ask the same question**: If you already asked something and
   got no answer, assume your best interpretation and move on.
5. **Ask specific, bounded questions**: Always provide 2-3 concrete options
   when asking a question. Never ask open-ended "what should I do?" questions.
6. **Document all assumptions**: Every assumption you make must be recorded
   with AddCommentTool using the prefix `ASSUMPTION:` so the team can verify."""


def build_conversation_context(
    *,
    project_id: int,
    agent_id: str,
    task_id: int | None = None,
    max_messages: int = 10,
) -> str:
    """Build a conversation context block for injection into task descriptions.

    Queries recent answered Q&A pairs and recent messages so agents see what
    was already discussed before they act.
    """
    import sqlite3

    from backend.tools.base.db import execute_with_retry

    def _query(conn: sqlite3.Connection) -> dict:
        # Get answered questions for this project
        qa_rows = conn.execute(
            """SELECT asked_by, question_text, answer_text, answered_by
               FROM clarification_questions
               WHERE project_id = ? AND status = 'answered'
               ORDER BY answered_at DESC LIMIT 5""",
            (project_id,),
        ).fetchall()

        # Get recent messages to this agent
        msg_rows = conn.execute(
            """SELECT from_agent, message, created_at FROM chat_messages
               WHERE project_id = ?
                 AND (to_agent = ? OR to_role IN (
                     SELECT role FROM roster WHERE agent_id = ?
                 ))
               ORDER BY created_at DESC LIMIT ?""",
            (project_id, agent_id, agent_id, max_messages),
        ).fetchall()

        return {
            "qa": [dict(r) for r in qa_rows],
            "messages": [dict(r) for r in reversed(msg_rows)],
        }

    try:
        data = execute_with_retry(_query)
    except Exception:
        return ""

    lines: list[str] = []

    if data["qa"]:
        lines.append("## Questions Already Asked and Answered")
        lines.append("Do NOT re-ask these questions.\n")
        for qa in data["qa"]:
            lines.append(f"**Q ({qa['asked_by']}):** {qa['question_text']}")
            lines.append(f"**A ({qa['answered_by']}):** {qa['answer_text']}\n")

    if data["messages"]:
        lines.append("## Recent Messages to You")
        for msg in data["messages"]:
            text = msg["message"][:300]
            lines.append(f"- **{msg['from_agent']}**: {text}")

    return "\n".join(lines)


def build_state_context(
    *,
    project_id: int,
    project_name: str,
    phase: str,
    summary: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Build a timestamped project state block for task descriptions.

    This goes in the CrewAI Task description (not the system prompt) because
    it changes between invocations.

    Args:
        project_id: DB id of the project.
        project_name: Human-readable project name.
        phase: Current phase (e.g. 'planning', 'executing', 'completed').
        summary: Optional free-text summary of what has happened so far.
        extra: Optional dict of additional key-value context.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "## Project State",
        f"- **Project:** {project_name} (ID: {project_id})",
        f"- **Phase:** {phase}",
        f"- **Timestamp:** {now}",
    ]
    if summary:
        lines.append(f"- **Context:** {summary}")
    if extra:
        for key, value in extra.items():
            lines.append(f"- **{key}:** {value}")
    return "\n".join(lines)
