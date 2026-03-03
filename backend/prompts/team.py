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

import hashlib
import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


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
            "Scientific investigation specialist. Decomposes research "
            "questions, generates competing hypotheses, evaluates sources "
            "via lateral verification, synthesizes findings thematically, "
            "and produces reports with calibrated confidence levels."
        ),
    },
    "research_reviewer": {
        "title": "Research Reviewer",
        "summary": (
            "Research quality gate. Evaluates methodology against standards "
            "(question decomposition, competing hypotheses, source quality, "
            "synthesis vs. summary, confidence calibration) and provides "
            "actionable feedback. Can approve or reject findings."
        ),
    },
}


# ── Communication Rules (static, by role type) ──────────────────────────────
# These reference role titles, not specific names, so they work regardless of
# how many agents exist.

# ── Pipeline Awareness (static, by role type) ────────────────────────────────
# Every agent needs to understand where they sit in the workflow: who hands
# them work, who consumes their output, and what happens if they do it poorly.
# This is injected into every system prompt via build_team_section().

PIPELINE_AWARENESS: dict[str, str] = {
    "project_lead": (
        "You are the first and last link in the chain. Requirements you "
        "gather become the foundation for ALL downstream work — planning, "
        "development, research, everything. Vague or incomplete requirements "
        "cause cascading failures across the entire team. When you present "
        "deliverables to the user, you are representing the combined work of "
        "every agent. If you do not verify quality before presenting, you "
        "waste everyone's effort."
    ),
    "team_lead": (
        "You translate requirements into executable work. Every task you "
        "create is picked up by a Developer or Researcher who has NO context "
        "beyond what you wrote in the task description. If the description "
        "is vague, the agent will guess wrong, produce incorrect work, get "
        "rejected in review, and waste cycles. Conversely, well-specified "
        "tasks with clear acceptance criteria flow through development and "
        "review smoothly. Your planning quality directly determines the "
        "team's velocity."
    ),
    "developer": (
        "You receive tasks and produce code. After you submit, a Code "
        "Reviewer — a DIFFERENT agent with NO access to your memory, "
        "terminal history, or thought process — evaluates your work. The "
        "reviewer can only see what you committed to the branch and what "
        "you wrote in task comments. If you did not push your code, write "
        "tests, or document what you did, the reviewer has nothing to "
        "evaluate and will reject. Every rejection costs the project a full "
        "review cycle. Your goal is not just 'working code' — it is code "
        "that a reviewer can understand, verify, and approve on the first "
        "pass."
    ),
    "code_reviewer": (
        "You receive code from Developers and decide whether it ships. Your "
        "approval means the code meets quality standards — the team trusts "
        "your judgment. If you approve broken code, bugs reach the project. "
        "If you reject without clear, actionable feedback, the Developer "
        "cannot fix the issues and the task enters an endless rework loop. "
        "Every rejection MUST tell the Developer exactly what is wrong, why "
        "it matters, and how to fix it. Your feedback quality directly "
        "determines how fast tasks move through the pipeline."
    ),
    "researcher": (
        "You receive research tasks and produce knowledge. After you submit, "
        "a Research Reviewer evaluates your work. The quality of your "
        "methodology — question decomposition, competing hypotheses, source "
        "verification, thematic synthesis — directly determines whether the "
        "reviewer validates or rejects. Every finding you record, every "
        "report you write, every wiki article you create becomes part of "
        "the project's permanent knowledge base that all other agents use "
        "for decisions. Your work has lasting impact, but only if you save "
        "it with the right tools."
    ),
    "research_reviewer": (
        "You receive research from Researchers and decide whether it meets "
        "quality standards. The Researcher is trained in question "
        "decomposition, competing hypothesis analysis, source verification, "
        "thematic synthesis, and devil's advocate self-challenge. Your "
        "review criteria evaluate whether these practices were applied. "
        "Your approval means the findings are credible for project "
        "decisions. If you reject without clear, actionable feedback, the "
        "Researcher cannot improve and the task enters an endless revision "
        "loop. Every rejection MUST tell the Researcher specifically what "
        "evidence is missing, which conclusions are unsupported, and what "
        "'good enough' looks like for resubmission."
    ),
}


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


# ── Artifact Map (per-role information flow) ────────────────────────────────

_ARTIFACT_MAP: dict[str, dict[str, str]] = {
    "project_lead": {
        "upstream": (
            "You receive the user's raw request and any follow-up answers. "
            "You may also receive status updates and deliverables from the "
            "Team Lead."
        ),
        "downstream": (
            "Your PRD is the single source of truth for the entire team. "
            "The Team Lead decomposes it into tasks. Every agent downstream "
            "(developers, researchers, reviewers) inherits the scope and "
            "constraints you defined. Ambiguity here causes cascading "
            "failures across the team."
        ),
    },
    "team_lead": {
        "upstream": (
            "You receive the PRD from the Project Lead and status updates "
            "from agents via the task system and messages."
        ),
        "downstream": (
            "Your task descriptions are the ONLY context Developers and "
            "Researchers receive. They cannot see the PRD directly — only "
            "what you wrote in each task. Vague tasks produce wrong work."
        ),
    },
    "developer": {
        "upstream": (
            "You receive a task with a description written by the Team "
            "Lead. You can read reference files and the knowledge base."
        ),
        "downstream": (
            "Your work is reviewed by a Code Reviewer who sees ONLY what "
            "you committed and pushed to the branch, plus task comments. "
            "Beyond review, your code becomes part of the project "
            "repository that other developers build on."
        ),
    },
    "code_reviewer": {
        "upstream": (
            "You receive a task marked review_ready. You can read the "
            "branch diff, task description, and task comments."
        ),
        "downstream": (
            "Your approval means the code ships. Your rejection feedback "
            "is the Developer's only guide for revision — vague feedback "
            "causes rework loops."
        ),
    },
    "researcher": {
        "upstream": (
            "You receive a research task with a question to investigate. "
            "You can query the knowledge base for prior work."
        ),
        "downstream": (
            "Your work is reviewed by a Research Reviewer who sees ONLY "
            "what you saved with tools (findings, reports, wiki, task "
            "comments). Beyond the reviewer, your findings become part "
            "of the permanent knowledge base that other agents use for "
            "decisions."
        ),
    },
    "research_reviewer": {
        "upstream": (
            "You receive a task marked review_ready. You can read the "
            "report (ReadReportTool), findings (ReadFindingsTool), wiki "
            "(ReadWikiTool), and task comments."
        ),
        "downstream": (
            "Your approval means findings enter the knowledge base as "
            "validated. Your rejection feedback is the Researcher's only "
            "guide for revision."
        ),
    },
}


TOOLS_INTRO = "Tool parameters are auto-documented — refer to each tool's schema for details."


def build_memory_section() -> str:
    """Return the shared <memory> block for agent system prompts."""
    return (
        "<memory>\n"
        "Your memory persists automatically between tasks. The system remembers key\n"
        "insights, entities, and task results from previous work and provides relevant\n"
        "context when you start new tasks.\n"
        "</memory>"
    )


def build_system_awareness(role: str) -> str:
    """Build the 'How This System Works' section for a system prompt.

    Two parts:
    1. Universal section (identical for all agents) — isolation model,
       what crosses boundaries, persistence principle.
    2. Per-role section (from _ARTIFACT_MAP) — upstream/downstream info flow.

    Args:
        role: The agent's role key (e.g. 'researcher', 'team_lead').
    """
    universal = """\
## How This System Works

### Isolation Model
You are an independent process with your own memory and context. Other
agents run in separate processes and CANNOT see your reasoning, your
searches, your file reads, or your terminal output. Each agent knows
only what was explicitly persisted through shared systems.

### What Crosses Agent Boundaries
- **Task system**: task descriptions, status, comments (AddCommentTool)
- **Git**: committed AND pushed code (not uncommitted changes)
- **Knowledge base**: findings (RecordFindingTool), wiki (WriteWikiTool),
  reports (WriteReportTool)
- **Messages**: explicit agent-to-agent messages (SendMessageTool)

### What Does NOT Cross
- Your reasoning and chain of thought
- Web searches you ran and their results
- Files you read but did not modify
- Terminal output from commands you executed
- Anything you "remember" but did not save with a tool

### The Persistence Principle
**If you did not save it with a tool, it does not exist for anyone else.**
This is the most common cause of rejected work: an agent does thorough
research or writes good code, but fails to persist it. The reviewer then
sees nothing and rejects."""

    # Per-role information flow
    artifact_info = _ARTIFACT_MAP.get(role, {})
    if artifact_info:
        role_section = (
            f"\n\n### Your Information Flow\n"
            f"**What you receive:** {artifact_info['upstream']}\n\n"
            f"**What depends on you:** {artifact_info['downstream']}"
        )
    else:
        role_section = ""

    return universal + role_section


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

    # System awareness: how the multi-agent system works
    lines.append("")
    lines.append(build_system_awareness(my_role))

    # Pipeline awareness: where this agent sits in the workflow
    awareness = PIPELINE_AWARENESS.get(my_role, "")
    if awareness:
        lines.append("")
        lines.append(f"## Your Role in the Pipeline\n{awareness}")

    lines.append("")
    comm = COMMUNICATION_RULES.get(my_role, "")
    if comm:
        lines.append(f"## Communication Protocol\n{comm}")

    # Append universal clarification protocol to all agents
    lines.append("")
    lines.append(build_clarification_protocol())

    # Response format reminder — prevents open models from wrapping
    # Thought/Action/Action Input in markdown code fences, which breaks
    # CrewAI's ReAct parser and causes infinite retry loops.
    lines.append("")
    lines.append(
        "## Response Format — CRITICAL\n"
        "When using tools, write your Thought/Action/Action Input as **plain text**.\n"
        "NEVER wrap them in markdown code blocks (```).\n\n"
        "Correct:\n"
        "Thought: I need to check the tasks\n"
        "Action: read_tasks\n"
        'Action Input: {"status": null}\n\n'
        "Wrong (NEVER do this):\n"
        "```\n"
        "Thought: I need to check the tasks\n"
        "Action: read_tasks\n"
        'Action Input: {"status": null}\n'
        "```"
    )

    return "\n".join(lines)


def build_clarification_protocol() -> str:
    """Return the universal clarification protocol block for all agents.

    This is appended to every agent's system prompt via build_team_section().
    """
    return """\
## Communication Rules — MANDATORY

### The Silence Principle
Before sending ANY message, ask yourself: **"Is my silence more harmful
than this message is helpful for the project's final outcome?"**

If the answer is no — do not send the message. Silence is the default.
Messages cost processing time for the recipient and can trigger response
chains. Only break silence when the project would be worse off without
your message.

Messages that FAIL this test (do not send):
- Acknowledgments ("Recibido", "Got it", "Understood", "Thanks")
- Status announcements ("I'm working on it", "I'm monitoring", "Standing by")
- Restatements of what someone just told you
- Confirmations that add no new information

Messages that PASS this test (send these):
- A specific question with 2-3 options that you cannot resolve alone
- A decision or action that changes the project direction
- New information the recipient does not already have
- A deliverable (report, finding, code reference)

### Clarification Protocol

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
6. **Act on context already in your task**: If the information needed to
   respond is already present in your task description (project state, PRD,
   recent messages, phase), do NOT ask a question — act directly. Asking
   for information you already have is a protocol violation that creates
   communication loops."""


## ── Chat summary via LLM ──────────────────────────────────────────────────

_summary_cache: dict[str, tuple[float, str]] = {}
_summary_cache_lock = threading.Lock()
_SUMMARY_CACHE_TTL = 300.0  # 5 minutes


def _summarize_messages_llm(
    messages: list[dict[str, str]],
    agent_id: str,
    project_id: int,
) -> str | None:
    """Call the LLM to produce a concise summary of recent chat messages.

    Returns a summary string, or None on failure (caller falls back to raw
    messages).  Results are cached for 5 minutes keyed on a content hash.
    """
    if not messages:
        return None

    # Build cache key from message content hash
    content_blob = "|".join(
        f"{m.get('from_agent', '?')}:{m.get('message', '')[:200]}"
        for m in messages
    )
    cache_key = hashlib.md5(
        f"{project_id}:{agent_id}:{content_blob}".encode(), usedforsecurity=False,
    ).hexdigest()

    with _summary_cache_lock:
        if cache_key in _summary_cache:
            ts, cached = _summary_cache[cache_key]
            if time.time() - ts < _SUMMARY_CACHE_TTL:
                return cached
            del _summary_cache[cache_key]

    # Build transcript for the LLM
    transcript_lines = []
    for m in messages:
        sender = m.get("from_agent", "unknown")
        text = m.get("message", "")
        ts = m.get("created_at", "")
        transcript_lines.append(f"[{ts}] {sender}: {text}")
    transcript = "\n".join(transcript_lines)

    try:
        import litellm
        from backend.config.llm import get_litellm_params

        params = get_litellm_params()
        if params is None:
            return None
        response = litellm.completion(
            **params,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an internal assistant. Summarize the following "
                        "inter-agent chat log into a concise digest for agent "
                        f"'{agent_id}'. Focus on:\n"
                        "- Decisions made and their rationale\n"
                        "- Open questions or unresolved issues\n"
                        "- Action items or requests directed at this agent\n"
                        "- Key findings or status updates\n\n"
                        "Be direct and use bullet points. Keep it under 400 words. "
                        "Do NOT invent information not present in the chat."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            max_tokens=600,
            temperature=0.2,
        )
        summary = response.choices[0].message.content.strip()
        if not summary:
            return None

        with _summary_cache_lock:
            # Evict stale entries if cache is growing
            if len(_summary_cache) > 50:
                now = time.time()
                _summary_cache.clear()
            _summary_cache[cache_key] = (time.time(), summary)

        return summary
    except Exception:
        logger.debug(
            "Failed to generate chat summary via LLM for agent %s",
            agent_id, exc_info=True,
        )
        return None


def build_conversation_context(
    *,
    project_id: int,
    agent_id: str,
    task_id: int | None = None,
    max_messages: int = 50,
) -> str:
    """Build a conversation context block for injection into task descriptions.

    Queries recent answered Q&A pairs and recent messages.  Messages are
    summarized by an LLM call (cached 5 min) instead of dumped raw, so
    agents receive a concise digest rather than a wall of truncated text.
    Falls back to raw messages if the LLM call fails.
    """
    import sqlite3

    from backend.tools.base.db import execute_with_retry

    def _query(conn: sqlite3.Connection) -> dict:
        # Get answered questions for this project (agent-to-agent)
        qa_rows = conn.execute(
            """SELECT asked_by, question_text, answer_text, answered_by
               FROM clarification_questions
               WHERE project_id = ? AND status = 'answered'
               ORDER BY answered_at DESC LIMIT 5""",
            (project_id,),
        ).fetchall()

        # Get user Q&A pairs (Project Lead ↔ user via AskUserTool)
        user_qa_rows = conn.execute(
            """SELECT agent_id, body, response, responded_at
               FROM user_requests
               WHERE project_id = ? AND status = 'responded'
               ORDER BY responded_at DESC LIMIT 10""",
            (project_id,),
        ).fetchall()

        # Get recent messages to this agent (up to 50 for summarization)
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
            "user_qa": [dict(r) for r in user_qa_rows],
            "messages": [dict(r) for r in reversed(msg_rows)],
        }

    try:
        data = execute_with_retry(_query)
    except Exception:
        return ""

    lines: list[str] = []

    if data["user_qa"]:
        lines.append("## User Q&A History")
        lines.append(
            "These are questions the Project Lead asked the user and the "
            "user's responses. Do NOT re-ask these questions.\n"
        )
        for uqa in data["user_qa"]:
            lines.append(f"**Q ({uqa['agent_id']}):** {uqa['body']}")
            lines.append(f"**A (user):** {uqa['response']}\n")

    if data["qa"]:
        lines.append("## Agent Q&A History")
        lines.append("Do NOT re-ask these questions.\n")
        for qa in data["qa"]:
            lines.append(f"**Q ({qa['asked_by']}):** {qa['question_text']}")
            lines.append(f"**A ({qa['answered_by']}):** {qa['answer_text']}\n")

    if data["messages"]:
        summary = _summarize_messages_llm(
            data["messages"], agent_id, project_id,
        )
        if summary:
            lines.append("## Recent Communication Summary")
            lines.append(
                "The following is an AI-generated digest of recent messages "
                "directed to you. Do NOT re-ask questions already answered here.\n"
            )
            lines.append(summary)
        else:
            # Fallback: raw messages (truncated) if LLM summary fails
            lines.append("## Recent Messages to You")
            for msg in data["messages"][:10]:
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
