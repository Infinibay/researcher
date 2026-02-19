"""Helper utilities for PABADA flows — DB queries, notifications, parsers."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from backend.tools.base.db import DBConnection, execute_with_retry

logger = logging.getLogger(__name__)


# ── Project helpers ───────────────────────────────────────────────────────────


def load_project_state(project_id: int) -> dict[str, Any] | None:
    """Load full project state from DB, including counts."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            return None
        project = dict(row)

        # Count tasks by status
        task_counts = {}
        for r in conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM tasks WHERE project_id = ?
               GROUP BY status""",
            (project_id,),
        ):
            task_counts[r["status"]] = r["cnt"]
        project["task_counts"] = task_counts
        project["total_tasks"] = sum(task_counts.values())

        # Count epics
        epic_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM epics WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        project["total_epics"] = epic_row["cnt"] if epic_row else 0

        return project

    return execute_with_retry(_query)


def create_project(name: str, description: str = "") -> int:
    """Create a new project in the DB and return its id."""

    def _insert(conn: sqlite3.Connection) -> int:
        cursor = conn.execute(
            """INSERT INTO projects (name, description, status, created_at)
               VALUES (?, ?, 'new', CURRENT_TIMESTAMP)""",
            (name, description),
        )
        conn.commit()
        return cursor.lastrowid

    return execute_with_retry(_insert)


def update_project_status(project_id: int, status: str) -> None:
    """Update the status of a project."""

    def _update(conn: sqlite3.Connection) -> None:
        if status == "completed":
            conn.execute(
                "UPDATE projects SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, project_id),
            )
        else:
            conn.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                (status, project_id),
            )
        conn.commit()

    execute_with_retry(_update)


# ── Task helpers ──────────────────────────────────────────────────────────────


def get_pending_tasks(project_id: int) -> list[dict[str, Any]]:
    """Get tasks with status in ('backlog', 'pending') ordered by priority.

    Only returns tasks whose dependencies are all 'done'.
    """

    def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT t.*
               FROM tasks t
               WHERE t.project_id = ?
                 AND t.status IN ('backlog', 'pending')
                 AND NOT EXISTS (
                     SELECT 1 FROM task_dependencies td
                     JOIN tasks dep ON dep.id = td.depends_on_task_id
                     WHERE td.task_id = t.id
                       AND td.dependency_type = 'blocks'
                       AND dep.status != 'done'
                 )
               ORDER BY t.priority ASC, t.id ASC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    return execute_with_retry(_query)


def get_task_by_id(task_id: int) -> dict[str, Any] | None:
    """Load a single task from DB."""

    def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    return execute_with_retry(_query)


def check_task_dependencies(task_id: int) -> bool:
    """Return True if all blocking dependencies of task_id are done."""

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as cnt
               FROM task_dependencies td
               JOIN tasks dep ON dep.id = td.depends_on_task_id
               WHERE td.task_id = ?
                 AND td.dependency_type = 'blocks'
                 AND dep.status != 'done'""",
            (task_id,),
        ).fetchone()
        return row["cnt"] == 0

    return execute_with_retry(_query)


def update_task_status(task_id: int, status: str) -> None:
    """Update a task's status."""

    def _update(conn: sqlite3.Connection) -> None:
        if status == "done":
            conn.execute(
                "UPDATE tasks SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, task_id),
            )
        else:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
        conn.commit()

    execute_with_retry(_update)


def update_task_status_safe(task_id: int, status: str) -> None:
    """Update a task's status, ignoring errors if task doesn't exist."""
    try:
        update_task_status(task_id, status)
    except Exception:
        logger.warning("Could not update task %d to status '%s'", task_id, status)


def get_task_branch(task_id: int) -> str | None:
    """Get the branch_name for a task."""

    def _query(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT branch_name FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row["branch_name"] if row and row["branch_name"] else None

    return execute_with_retry(_query)


def set_task_branch(task_id: int, branch_name: str) -> None:
    """Set the branch_name on a task."""

    def _update(conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE tasks SET branch_name = ? WHERE id = ?",
            (branch_name, task_id),
        )
        conn.commit()

    execute_with_retry(_update)


def increment_task_retry(task_id: int) -> int:
    """Increment retry_count on a task and return the new count."""

    def _update(conn: sqlite3.Connection) -> int:
        conn.execute(
            "UPDATE tasks SET retry_count = retry_count + 1 WHERE id = ?",
            (task_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT retry_count FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row["retry_count"]

    return execute_with_retry(_update)


# ── Objective verification ────────────────────────────────────────────────────


def all_objectives_met(project_id: int) -> bool:
    """Check if all epics in the project are completed."""

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
               FROM epics WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        if row is None or row["total"] == 0:
            return False
        return row["completed"] == row["total"]

    return execute_with_retry(_query)


# ── Communication helpers ─────────────────────────────────────────────────────


def send_agent_message(
    project_id: int,
    from_agent: str,
    to_agent: str | None,
    to_role: str | None,
    message: str,
    conversation_type: str = "agent_to_agent",
    thread_id: int | None = None,
) -> int:
    """Insert a chat_message and return its id."""

    def _insert(conn: sqlite3.Connection) -> int:
        # Ensure a thread exists; create a default one if thread_id is None
        actual_thread_id = thread_id
        if actual_thread_id is None:
            import uuid
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

    return execute_with_retry(_insert)


def notify_team_lead(project_id: int, from_agent: str, message: str) -> int:
    """Send a message to the Team Lead role."""
    return send_agent_message(
        project_id=project_id,
        from_agent=from_agent,
        to_agent=None,
        to_role="team_lead",
        message=message,
    )


def parse_review_result(
    text: str,
    approve_keyword: str = "APPROVED",
    reject_keyword: str = "REJECTED",
) -> Literal["approved", "rejected"]:
    """Parse a review result requiring the keyword at the start of the string.

    Strips leading whitespace and checks whether the response starts with
    *reject_keyword* or *approve_keyword* (using ``^KEYWORD\\b``).
    REJECTED is checked first so it always wins.  Returns ``"rejected"``
    by default when neither keyword is found, which avoids false positives
    from phrases like "NOT APPROVED".
    """
    text_upper = text.strip().upper()

    if re.match(rf"^{reject_keyword}\b", text_upper):
        return "rejected"

    if re.match(rf"^{approve_keyword}\b", text_upper):
        return "approved"

    logger.warning(
        "parse_review_result: no keyword matched, defaulting to 'rejected'. "
        "Text: %.200s",
        text,
    )
    return "rejected"


def classify_approval_response(text: str) -> Literal["approved", "rejected"]:
    """Semantically classify a free-form agent response as approved or rejected.

    Uses a regex fast-path for unambiguous responses, then falls back to a
    LiteLLM call for natural-language answers.  Defaults to "rejected" on error.
    """
    # Fast-path: if the response starts with the keyword, skip the LLM call
    text_upper = text.strip().upper()
    if re.match(r"^APPROVED\b", text_upper):
        return "approved"
    if re.match(r"^REJECTED\b", text_upper):
        return "rejected"

    import litellm
    from backend.config.settings import settings

    try:
        kwargs: dict[str, Any] = {
            "model": settings.LLM_MODEL,
            "max_tokens": 10,
            "temperature": 0,
            "timeout": 15,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a binary classifier. Given a user response to a "
                        "plan approval request, output exactly one word: 'approved' "
                        "if the response is positive/accepting, or 'rejected' if it "
                        "is negative/requesting changes. Output nothing else."
                    ),
                },
                {"role": "user", "content": text},
            ],
        }
        if settings.LLM_BASE_URL:
            kwargs["api_base"] = settings.LLM_BASE_URL
        if settings.LLM_API_KEY:
            kwargs["api_key"] = settings.LLM_API_KEY

        response = litellm.completion(**kwargs)
        answer = response.choices[0].message.content.strip().lower()
        return "approved" if answer.startswith("approved") else "rejected"
    except Exception:
        logger.warning(
            "classify_approval_response: LLM call failed, defaulting to 'rejected'",
            exc_info=True,
        )
        return "rejected"


# ── Report helpers ────────────────────────────────────────────────────────────


def generate_final_report(project_id: int) -> str:
    """Generate a summary report of the project."""

    def _query(conn: sqlite3.Connection) -> str:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            return "Project not found."

        # Task summary
        tasks = conn.execute(
            """SELECT status, COUNT(*) as cnt
               FROM tasks WHERE project_id = ?
               GROUP BY status""",
            (project_id,),
        ).fetchall()
        task_summary = {r["status"]: r["cnt"] for r in tasks}

        # Epics
        epics = conn.execute(
            "SELECT title, status FROM epics WHERE project_id = ?",
            (project_id,),
        ).fetchall()

        # Agent performance
        perf = conn.execute(
            """SELECT ar.role, COUNT(*) as runs,
                      SUM(CASE WHEN ar.status = 'completed' THEN 1 ELSE 0 END) as success
               FROM agent_runs ar
               WHERE ar.project_id = ?
               GROUP BY ar.role""",
            (project_id,),
        ).fetchall()

        report_lines = [
            f"# Project Report: {project['name']}",
            f"Status: {project['status']}",
            "",
            "## Task Summary",
        ]
        for status, count in task_summary.items():
            report_lines.append(f"- {status}: {count}")

        report_lines.append("")
        report_lines.append("## Epics")
        for epic in epics:
            report_lines.append(f"- {epic['title']}: {epic['status']}")

        report_lines.append("")
        report_lines.append("## Agent Performance")
        for p in perf:
            report_lines.append(
                f"- {p['role']}: {p['success']}/{p['runs']} successful"
            )

        return "\n".join(report_lines)

    return execute_with_retry(_query)


# ── Event logging ─────────────────────────────────────────────────────────────


def log_flow_event(
    project_id: int,
    event_type: str,
    event_source: str,
    entity_type: str,
    entity_id: int | None = None,
    event_data: dict[str, Any] | None = None,
) -> None:
    """Log an event to the events_log table."""

    def _insert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO events_log
                   (project_id, event_type, event_source, entity_type,
                    entity_id, event_data_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (project_id, event_type, event_source, entity_type,
             entity_id, json.dumps(event_data or {})),
        )
        conn.commit()

    execute_with_retry(_insert)


# ── Parsing helpers ───────────────────────────────────────────────────────────


def parse_ideas(raw_text: str) -> list[dict[str, Any]]:
    """Parse structured ideas from agent output text.

    Pass 1: Structured format — splits on ``## Idea N`` headers and extracts
    **Title**, **Description**, **Impact**, and **Feasibility** fields via regex.

    Pass 2: Legacy fallback — line-by-line heuristic for older prompt formats
    (used by consolidate_ideas, decision_phase).
    """

    # ── Pass 1: structured ``## Idea N`` blocks ──────────────────────────
    blocks = re.split(r'(?m)^##\s+Idea\s+\d+', raw_text)
    structured_ideas: list[dict[str, Any]] = []
    for block in blocks:
        if not block.strip():
            continue
        title_m = re.search(r'\*\*Title:\*\*\s*(.+)', block)
        desc_m = re.search(r'\*\*Description:\*\*\s*(.+?)(?=\n\*\*Impact:\*\*|\Z)', block, re.S)
        impact_m = re.search(r'\*\*Impact:\*\*\s*(.+?)(?=\n\*\*Feasibility:\*\*|\Z)', block, re.S)
        feas_m = re.search(r'\*\*Feasibility:\*\*\s*(.+?)(?=\Z)', block, re.S)

        title = title_m.group(1).strip() if title_m else ""
        if title:
            structured_ideas.append({
                "title": title,
                "description": desc_m.group(1).strip() if desc_m else "",
                "impact": impact_m.group(1).strip() if impact_m else "",
                "feasibility": feas_m.group(1).strip() if feas_m else "",
            })

    if structured_ideas:
        return structured_ideas

    # ── Pass 2: legacy line-by-line fallback ──────────────────────────────
    ideas: list[dict[str, Any]] = []
    current_idea: dict[str, Any] | None = None

    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            if current_idea:
                ideas.append(current_idea)
                current_idea = None
            continue

        # Try numbered format: "1. Title: description" or "- Title: description"
        matched = False
        for prefix_check in [".", ")", "-", "*"]:
            stripped = line.lstrip("0123456789")
            if stripped.startswith(prefix_check):
                text = stripped[len(prefix_check):].strip()
                # Save previous idea before starting a new one
                if current_idea:
                    ideas.append(current_idea)
                if ":" in text:
                    title, _, desc = text.partition(":")
                    current_idea = {
                        "title": title.strip(),
                        "description": desc.strip(),
                    }
                else:
                    current_idea = {"title": text, "description": ""}
                matched = True
                break

        if not matched:
            # Continuation of previous idea description
            if current_idea:
                if current_idea["description"]:
                    current_idea["description"] += " " + line
                else:
                    current_idea["description"] = line

    if current_idea:
        ideas.append(current_idea)

    return ideas


def calculate_time_elapsed(start_time: str) -> float:
    """Calculate seconds elapsed since start_time (ISO format string)."""
    if not start_time:
        return 0.0
    start = datetime.fromisoformat(start_time)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - start).total_seconds()


# ── Stagnation detection ─────────────────────────────────────────────────────


def detect_stagnation(project_id: int, cycles_threshold: int = 3) -> bool:
    """Detect if the project is stagnating.

    Criteria:
    - No tasks completed in the last N agent runs
    - 2+ tasks stuck in 'in_progress' or 'rejected'
    """

    def _query(conn: sqlite3.Connection) -> bool:
        # Check recent completed tasks
        recent_runs = conn.execute(
            """SELECT COUNT(*) as cnt FROM agent_runs
               WHERE project_id = ?
               ORDER BY started_at DESC LIMIT ?""",
            (project_id, cycles_threshold * 2),
        ).fetchone()

        recent_completions = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE project_id = ? AND status = 'done'
                 AND completed_at >= datetime('now', '-1 hour')""",
            (project_id,),
        ).fetchone()

        stuck_tasks = conn.execute(
            """SELECT COUNT(*) as cnt FROM tasks
               WHERE project_id = ?
                 AND status IN ('in_progress', 'rejected')
                 AND created_at <= datetime('now', '-30 minutes')""",
            (project_id,),
        ).fetchone()

        has_activity = recent_runs and recent_runs["cnt"] > 0
        no_completions = recent_completions and recent_completions["cnt"] == 0
        many_stuck = stuck_tasks and stuck_tasks["cnt"] >= 2

        return has_activity and no_completions and many_stuck

    return execute_with_retry(_query)


def get_stuck_tasks(
    project_id: int, threshold_minutes: int = 30
) -> list[dict[str, Any]]:
    """Get tasks stuck in 'in_progress' or 'rejected' beyond threshold."""

    def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE project_id = ?
                 AND status IN ('in_progress', 'rejected')
                 AND created_at <= datetime('now', ? || ' minutes')
               ORDER BY created_at ASC""",
            (project_id, f"-{threshold_minutes}"),
        ).fetchall()
        return [dict(r) for r in rows]

    return execute_with_retry(_query)


def get_completed_task_count(project_id: int) -> int:
    """Count tasks with status 'done' for a project."""

    def _query(conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE project_id = ? AND status = 'done'",
            (project_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    return execute_with_retry(_query)


def has_active_review_run(task_id: int) -> bool:
    """Check if there is already a running code_reviewer agent_run for this task."""

    def _query(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM agent_runs
               WHERE task_id = ? AND role = 'code_reviewer' AND status = 'running'""",
            (task_id,),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    return execute_with_retry(_query)


# ── Tech detection ────────────────────────────────────────────────────────


def detect_tech_hints(project_id: int) -> list[str]:
    """Scan project repositories for technology indicator files.

    Checks for common config files, file extensions, and dependency declarations
    in each repository's ``local_path``. Returns a deduplicated list of technology
    names that can be fed to the developer prompt builder.

    Never raises — returns ``[]`` on any error so agent creation is never blocked.
    """
    try:
        def _query(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                "SELECT local_path FROM repositories WHERE project_id = ? AND status = 'active'",
                (project_id,),
            ).fetchall()
            return [r["local_path"] for r in rows if r["local_path"]]

        local_paths = execute_with_retry(_query)

        hints: list[str] = []
        for path_str in local_paths:
            root = Path(path_str)
            if not root.is_dir():
                continue
            _detect_from_dir(root, hints)

        # Deduplicate preserving insertion order
        return list(dict.fromkeys(hints))

    except Exception:
        logger.warning(
            "detect_tech_hints: failed for project %d, returning empty list",
            project_id,
            exc_info=True,
        )
        return []


def _detect_from_dir(root: Path, hints: list[str]) -> None:
    """Populate *hints* by scanning *root* for technology indicators.

    Searches both the repo root and common subdirectories (``src``, ``apps``,
    ``packages``, ``lib``, ``cmd``) so that nested source trees are detected.
    For file-extension checks, uses ``rglob`` with an early-break ``any()``
    to avoid walking the entire tree unnecessarily.
    """

    # Directories to check for indicator files (config files like
    # pyproject.toml, tsconfig.json, etc.).  The root is always checked;
    # subdirectories cover monorepo / nested-source layouts.
    _SEARCH_DIRS = [
        root,
        root / "src",
        root / "apps",
        root / "packages",
        root / "lib",
        root / "cmd",
    ]

    def _has(name: str) -> bool:
        """True if *name* exists in the root or any search directory."""
        return any((d / name).exists() for d in _SEARCH_DIRS)

    def _any_ext(*exts: str) -> bool:
        """True if any file with one of *exts* exists anywhere in the tree.

        Uses ``rglob`` with ``any()`` so iteration stops at the first match.
        """
        return any(
            any(root.rglob(f"*{ext}"))
            for ext in exts
        )

    def _file_contains(name: str, *needles: str) -> bool:
        """Check if *name* (relative to any search dir) contains a needle."""
        for d in _SEARCH_DIRS:
            p = d / name
            if not p.is_file():
                continue
            try:
                content = p.read_text(errors="ignore")
                if any(n in content for n in needles):
                    return True
            except OSError:
                continue
        return False

    # Languages
    if _has("pyproject.toml") or _has("setup.py") or _has("requirements.txt") or _any_ext(".py"):
        hints.append("python")
    if _has("tsconfig.json"):
        hints.append("typescript")
    elif _has("package.json"):
        hints.append("javascript")
    if _has("Cargo.toml"):
        hints.append("rust")

    has_cpp = _has("CMakeLists.txt") or _any_ext(".cpp", ".cc", ".cxx")
    if has_cpp:
        hints.append("cpp")
    if not has_cpp and _any_ext(".c"):
        hints.append("c")

    if _has("Gemfile"):
        hints.append("ruby")
    if _any_ext(".sql"):
        hints.append("sql")

    # Containers
    if _has("docker-compose.yml") or _has("docker-compose.yaml") or _has("Dockerfile"):
        hints.append("docker")
    if _has("Containerfile"):
        hints.append("podman")

    # Shell
    if _any_ext(".sh"):
        hints.append("bash")

    # Databases / stores (check dependency files)
    deps_files = ("requirements.txt", "package.json", "Cargo.toml")
    if any(_file_contains(f, "redis") for f in deps_files):
        hints.append("redis")
    if any(_file_contains(f, "psycopg", "asyncpg", "postgres") for f in deps_files):
        hints.append("postgres")
    if any(_file_contains(f, "mysql", "pymysql", "mysqlclient") for f in deps_files):
        hints.append("mysql")
