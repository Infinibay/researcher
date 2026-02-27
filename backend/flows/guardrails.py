"""Task guardrails and structured output models for PABADA flows.

Guardrails validate and transform task outputs BEFORE accepting them.
They integrate with CrewAI's ``Task(guardrail=...)`` parameter.

Each guardrail function receives a ``TaskOutput`` and returns
``(True, output)`` on success or ``(False, "reason")`` on failure.
CrewAI automatically retries the task when a guardrail rejects.
"""

import logging
import sqlite3

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


# ── Research artifact guardrails ─────────────────────────────────────────────

MAX_RESCUE_ATTEMPTS = 2


def check_research_artifacts(
    project_id: int, task_id: int,
) -> dict[str, int]:
    """Check the DB for research artifacts (findings + reports) for a task.

    Returns {"findings": <count>, "reports": <count>}.
    """

    def _query(conn: sqlite3.Connection) -> dict[str, int]:
        findings = conn.execute(
            "SELECT COUNT(*) FROM findings WHERE project_id = ? AND task_id = ?",
            (project_id, task_id),
        ).fetchone()[0]
        reports = conn.execute(
            "SELECT COUNT(*) FROM artifacts "
            "WHERE project_id = ? AND task_id = ? AND type = 'report'",
            (project_id, task_id),
        ).fetchone()[0]
        return {"findings": findings, "reports": reports}

    return execute_with_retry(_query)


# ── Review guardrails ────────────────────────────────────────────────────────


def validate_review_verdict(output):
    """Ensure a code review output contains an explicit APPROVED or REJECTED verdict.

    Prevents ambiguous reviews that neither approve nor reject.
    """
    text = str(output).upper()
    has_verdict = "APPROVED" in text or "REJECTED" in text
    if not has_verdict:
        return (
            False,
            "Your review MUST contain an explicit verdict: either 'APPROVED' "
            "or 'REJECTED' followed by specific feedback. Please re-do the "
            "review with a clear verdict.",
        )
    return (True, output)


def validate_research_review_verdict(output):
    """Ensure a peer review output contains an explicit VALIDATED or REJECTED verdict."""
    text = str(output).upper()
    has_verdict = "VALIDATED" in text or "REJECTED" in text
    if not has_verdict:
        return (
            False,
            "Your peer review MUST contain an explicit verdict: either "
            "'VALIDATED' or 'REJECTED' followed by specific feedback. "
            "Please re-do the review with a clear verdict.",
        )
    return (True, output)


# ── Plan guardrails ──────────────────────────────────────────────────────────


def validate_plan_output(output):
    """Ensure a plan contains actionable content.

    Focuses on *content quality* rather than rigid formatting:
    - Rejects plans that are too short or vague.
    - Rejects plans that don't mention concrete work items.
    - Caps the number of epics to encourage incremental planning.

    Format/structure is intentionally NOT validated here — the downstream
    ``parse_plan_tasks()`` in ``ticket_creation_flow`` handles extraction
    and is already flexible across many LLM output styles.
    """
    import re

    text = str(output)
    stripped = text.strip()

    # ── Length gate ───────────────────────────────────────────────────────
    if len(stripped) < 100:
        return (
            False,
            "The plan is too short. A project plan must include at least "
            "several task descriptions with clear objectives. Please provide "
            "a more detailed plan.",
        )

    # ── Content gate: must reference concrete work ───────────────────────
    # We look for *any* signal that the plan describes actionable work
    # items, not just high-level commentary.
    work_signals = re.findall(
        r'(?i)\b(?:task|implement|create|build|design|develop|configure|'
        r'set\s?up|integrate|deploy|write|test|fix|refactor|migrate|'
        r'epic|milestone|feature|endpoint|module|component|service|'
        r'database|schema|api|repository|pipeline)\b',
        text,
    )
    if len(work_signals) < 3:
        return (
            False,
            "The plan doesn't describe enough concrete work. A good plan "
            "should mention specific things to build, configure, or implement "
            "(e.g., components, endpoints, schemas, tasks). Please make the "
            "plan more actionable.",
        )

    # ── Epic count cap ───────────────────────────────────────────────────
    from backend.config.settings import settings

    epic_count = len(re.findall(r'(?i)^#+\s*epic\b', text, re.MULTILINE))
    if epic_count == 0:
        epic_count = text.lower().count("createepictool") + text.lower().count("create_epic")
    if epic_count > settings.MAX_ACTIVE_EPICS + 1:  # +1 tolerance
        return (
            False,
            f"The plan contains ~{epic_count} epics but the limit is "
            f"{settings.MAX_ACTIVE_EPICS}. Plan incrementally: define only "
            f"the {settings.MAX_ACTIVE_EPICS} most critical epics for now. "
            f"You will plan more epics after these are completed.",
        )

    return (True, output)


# ── Implementation guardrails ────────────────────────────────────────────────


def validate_implementation_output(output):
    """Ensure a developer's implementation output is substantive.

    Rejects outputs that are clearly just planning text without actual code work.
    """
    text = str(output)
    if len(text.strip()) < 50:
        return (
            False,
            "The implementation output is too brief. Please provide a "
            "summary of what was implemented, which files were created or "
            "modified, and the branch name.",
        )
    return (True, output)


# ── Requirements guardrails ──────────────────────────────────────────────────


def validate_requirements_output(output):
    """Ensure requirements are substantive and actionable."""
    text = str(output)
    if len(text.strip()) < 100:
        return (
            False,
            "The requirements document is too brief. Requirements must "
            "include specific features, acceptance criteria, or user stories. "
            "Please gather more detailed requirements from the user.",
        )
    return (True, output)


# ── Brainstorm task creation guardrails ──────────────────────────────────────


def validate_brainstorm_task_creation(project_id: int):
    """Return a guardrail closure that checks the DB for newly created tasks.

    Captures a *before* snapshot of existing task IDs so the guardrail can
    detect whether the agent actually called CreateTaskTool during execution.
    """
    # Snapshot existing task IDs before the agent runs
    def _get_task_ids(conn: sqlite3.Connection) -> set[int]:
        rows = conn.execute(
            "SELECT id FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchall()
        return {r[0] for r in rows}

    before_ids = execute_with_retry(_get_task_ids)

    def _guardrail(output):
        after_ids = execute_with_retry(_get_task_ids)
        new_ids = after_ids - before_ids
        if not new_ids:
            return (
                False,
                "No tasks were created in the database. You MUST actually call "
                "the CreateEpicTool, CreateMilestoneTool, and CreateTaskTool to "
                "create project structure — do not just describe what you would "
                "create. Use the tools now.",
            )
        logger.info(
            "Brainstorm task creation guardrail passed: %d new tasks created "
            "(IDs: %s) for project %d",
            len(new_ids), sorted(new_ids), project_id,
        )
        return (True, output)

    return _guardrail


# ── Ticket creation guardrails ───────────────────────────────────────────────


def validate_ticket_creation(output):
    """Ensure ticket creation produced a parseable task ID or SKIPPED_DUPLICATE.

    Prevents silent failures where the agent talks about creating a task
    but doesn't actually call the CreateTask tool.
    """
    text = str(output)
    # Valid outcomes: contains a task ID number or explicit skip
    if "SKIPPED_DUPLICATE" in text:
        return (True, output)

    # Look for evidence of task creation (ID reference)
    import re
    has_id = bool(re.search(r'(?:task|id|created)[:\s#]*(\d+)', text, re.IGNORECASE))
    if not has_id:
        return (
            False,
            "Your output must contain evidence of task creation (the created "
            "task ID) or 'SKIPPED_DUPLICATE' if the task already exists. "
            "Please actually use the CreateTask tool to create the task.",
        )
    return (True, output)
