#!/usr/bin/env python3
"""PABADA MCP Server — exposes project operations as MCP tools for Claude Code.

Standalone script. Reads env vars and makes HTTP calls to the PABADA backend.
Does NOT import anything from the ``backend`` package.

Env vars (set by PodManager):
    PABADA_API_URL    — Backend base URL (e.g. http://host.containers.internal:8000)
    PABADA_PROJECT_ID — Current project ID
    PABADA_AGENT_ID   — Current agent ID
    PABADA_TASK_ID    — Current task ID (optional)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastmcp import FastMCP

# ── Configuration ────────────────────────────────────────────────────────

API_URL = os.environ.get("PABADA_API_URL", "http://localhost:8000")
PROJECT_ID = os.environ.get("PABADA_PROJECT_ID", "")
AGENT_ID = os.environ.get("PABADA_AGENT_ID", "")
TASK_ID = os.environ.get("PABADA_TASK_ID", "")

mcp = FastMCP(
    "pabada",
    instructions=(
        "PABADA project management tools. Use these to manage tasks, "
        "communicate with teammates, record findings, query the database, "
        "and more."
    ),
)


# ── HTTP helper ──────────────────────────────────────────────────────────

def _api(
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an HTTP request to the PABADA backend API."""
    url = f"{API_URL}{path}"
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url = f"{url}?{urllib.parse.urlencode(filtered)}"

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════
# TASK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def task_get(task_id: int) -> str:
    """Get full task details including comments and dependencies.

    Args:
        task_id: ID of the task to retrieve
    """
    task = _api("GET", f"/api/tasks/{task_id}")
    if "error" in task:
        return json.dumps(task)
    comments = _api("GET", f"/api/tasks/{task_id}/comments")
    deps = _api("GET", f"/api/tasks/{task_id}/dependencies")
    task["comments"] = comments if isinstance(comments, list) else []
    task["dependencies"] = deps if isinstance(deps, list) else []
    return json.dumps(task, default=str)


@mcp.tool()
def task_list(
    status: str | None = None,
    type: str | None = None,
) -> str:
    """List tasks for the current project. Optionally filter by status or type.

    Args:
        status: Filter by status (backlog, pending, in_progress, review_ready, done, rejected, cancelled)
        type: Filter by type (plan, research, code, review, test, design, integrate, documentation, bug_fix)
    """
    params = {"project_id": PROJECT_ID}
    if status:
        params["status"] = status
    if type:
        params["type"] = type
    result = _api("GET", "/api/tasks", params=params)
    return json.dumps(result, default=str)


@mcp.tool()
def task_create(
    title: str,
    description: str,
    type: str = "code",
    milestone_id: int | None = None,
    epic_id: int | None = None,
    priority: str = "medium",
    complexity: int = 3,
) -> str:
    """Create a new task in the current project.

    Args:
        title: Task title
        description: Detailed task description and acceptance criteria
        type: Task type (plan, research, code, review, test, design, integrate, documentation, bug_fix)
        milestone_id: Optional milestone ID to associate with
        epic_id: Optional epic ID to associate with
        priority: Priority level (low, medium, high, critical)
        complexity: Estimated complexity 1-5
    """
    data: dict[str, Any] = {
        "project_id": int(PROJECT_ID),
        "title": title,
        "description": description,
        "type": type,
        "priority": priority,
        "estimated_complexity": complexity,
        "created_by": AGENT_ID,
    }
    if milestone_id is not None:
        data["milestone_id"] = milestone_id
    if epic_id is not None:
        data["epic_id"] = epic_id
    return json.dumps(_api("POST", "/api/tasks", data=data), default=str)


@mcp.tool()
def task_update_status(task_id: int, status: str, comment: str | None = None) -> str:
    """Update the status of a task.

    Args:
        task_id: ID of the task to update
        status: New status (backlog, pending, in_progress, review_ready, done, rejected, cancelled)
        comment: Optional comment explaining the status change
    """
    data: dict[str, Any] = {"status": status}
    result = _api("PUT", f"/api/tasks/{task_id}", data=data)
    if comment and "error" not in result:
        _api("POST", f"/api/tasks/{task_id}/comments", data={
            "author": AGENT_ID,
            "content": comment,
            "comment_type": "status_change",
        })
    return json.dumps(result, default=str)


@mcp.tool()
def task_take(task_id: int) -> str:
    """Take ownership of a task (set status to in_progress and assign to self).

    Args:
        task_id: ID of the task to take
    """
    result = _api("PUT", f"/api/tasks/{task_id}", data={
        "status": "in_progress",
        "assigned_to": AGENT_ID,
    })
    return json.dumps(result, default=str)


@mcp.tool()
def task_add_comment(
    task_id: int,
    comment: str,
    comment_type: str = "comment",
) -> str:
    """Add a comment to a task.

    Args:
        task_id: ID of the task
        comment: Comment text
        comment_type: Type of comment (comment, change_request, approval, question, answer)
    """
    result = _api("POST", f"/api/tasks/{task_id}/comments", data={
        "author": AGENT_ID,
        "content": comment,
        "comment_type": comment_type,
    })
    return json.dumps(result, default=str)


@mcp.tool()
def task_set_dependencies(
    task_id: int,
    depends_on: list[int],
    dependency_type: str = "blocks",
) -> str:
    """Set dependencies for a task.

    Args:
        task_id: ID of the task
        depends_on: List of task IDs that this task depends on
        dependency_type: Type of dependency (blocks, required_by)
    """
    result = _api("POST", f"/api/tasks/{task_id}/dependencies", data={
        "depends_on": depends_on,
        "dependency_type": dependency_type,
    })
    return json.dumps(result, default=str)


@mcp.tool()
def task_approve(task_id: int, comment: str | None = None) -> str:
    """Approve a task that is in review_ready status, moving it to done.

    Args:
        task_id: ID of the task to approve
        comment: Optional approval comment
    """
    return json.dumps(
        _api("POST", f"/api/internal/tasks/{task_id}/approve", data={
            "agent_id": AGENT_ID,
            "comment": comment,
        }),
        default=str,
    )


@mcp.tool()
def task_reject(task_id: int, reason: str) -> str:
    """Reject a task in review_ready status with feedback for the developer.

    Args:
        task_id: ID of the task to reject
        reason: Detailed reason for rejection / change request
    """
    return json.dumps(
        _api("POST", f"/api/internal/tasks/{task_id}/reject", data={
            "agent_id": AGENT_ID,
            "reason": reason,
        }),
        default=str,
    )


# ═══════════════════════════════════════════════════════════════════════
# PROJECT STRUCTURE
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def epic_create(
    title: str,
    description: str = "",
    priority: str = "medium",
) -> str:
    """Create a new epic in the current project.

    Args:
        title: Epic title
        description: Epic description
        priority: Priority level (low, medium, high, critical)
    """
    return json.dumps(
        _api("POST", "/api/epics", data={
            "project_id": int(PROJECT_ID),
            "title": title,
            "description": description,
            "priority": priority,
            "created_by": AGENT_ID,
        }),
        default=str,
    )


@mcp.tool()
def milestone_create(
    title: str,
    epic_id: int,
    description: str = "",
    due_date: str | None = None,
) -> str:
    """Create a new milestone within an epic.

    Args:
        title: Milestone title
        epic_id: ID of the parent epic
        description: Milestone description
        due_date: Optional due date (ISO format, e.g. 2026-04-01)
    """
    data: dict[str, Any] = {
        "project_id": int(PROJECT_ID),
        "title": title,
        "epic_id": epic_id,
        "description": description,
    }
    if due_date:
        data["due_date"] = due_date
    return json.dumps(_api("POST", "/api/milestones", data=data), default=str)


# ═══════════════════════════════════════════════════════════════════════
# COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def chat_send(
    message: str,
    to_agent: str | None = None,
    to_role: str | None = None,
) -> str:
    """Send a message to a specific agent or role.

    Args:
        message: Message content
        to_agent: Target agent ID (e.g. 'developer_1_p1')
        to_role: Target role (e.g. 'developer', 'team_lead') — used if to_agent is not set
    """
    return json.dumps(
        _api("POST", "/api/internal/chat/send", data={
            "project_id": int(PROJECT_ID),
            "from_agent": AGENT_ID,
            "message": message,
            "to_agent": to_agent,
            "to_role": to_role,
        }),
        default=str,
    )


@mcp.tool()
def chat_read(unread_only: bool = True, limit: int = 50) -> str:
    """Read messages directed to you.

    Args:
        unread_only: Only return unread messages
        limit: Maximum number of messages to return
    """
    params = {
        "unread_only": str(unread_only).lower(),
        "limit": str(limit),
    }
    result = _api("GET", f"/api/chat/{PROJECT_ID}/agent/{AGENT_ID}", params=params)
    return json.dumps(result, default=str)


@mcp.tool()
def chat_ask_team_lead(question: str) -> str:
    """Ask a question to the Team Lead.

    Args:
        question: Your question or request for the Team Lead
    """
    return json.dumps(
        _api("POST", "/api/internal/ask-team-lead", data={
            "project_id": int(PROJECT_ID),
            "agent_id": AGENT_ID,
            "question": question,
        }),
        default=str,
    )


@mcp.tool()
def chat_ask_project_lead(question: str) -> str:
    """Ask a question to the Project Lead (for high-level decisions, scope changes, priorities).

    Args:
        question: Your question or request for the Project Lead
    """
    return json.dumps(
        _api("POST", "/api/internal/ask-project-lead", data={
            "project_id": int(PROJECT_ID),
            "agent_id": AGENT_ID,
            "question": question,
        }),
        default=str,
    )


# ═══════════════════════════════════════════════════════════════════════
# KNOWLEDGE (FINDINGS)
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def finding_record(
    title: str,
    content: str,
    confidence: float = 0.5,
    finding_type: str = "observation",
    sources: list[str] | None = None,
) -> str:
    """Record a research finding with confidence level and sources.

    Args:
        title: Finding title/topic
        content: Detailed finding content
        confidence: Confidence level 0.0 to 1.0
        finding_type: Type: observation, hypothesis, experiment, proof, conclusion
        sources: List of source URLs or references
    """
    task_id = TASK_ID
    if not task_id:
        return json.dumps({"error": "No PABADA_TASK_ID set. Findings must be associated with a task."})
    return json.dumps(
        _api("POST", "/api/internal/findings", data={
            "project_id": int(PROJECT_ID),
            "agent_id": AGENT_ID,
            "task_id": int(task_id),
            "title": title,
            "content": content,
            "confidence": confidence,
            "finding_type": finding_type,
            "sources": sources or [],
        }),
        default=str,
    )


@mcp.tool()
def finding_read(
    query: str | None = None,
    task_id: int | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
) -> str:
    """Search or list findings. Uses full-text search if query is provided.

    Args:
        query: Full-text search query (optional)
        task_id: Filter by task ID (optional)
        min_confidence: Minimum confidence threshold (optional)
        limit: Maximum results to return
    """
    params: dict[str, Any] = {"project_id": PROJECT_ID, "limit": limit}
    if query:
        params["query"] = query
    if task_id is not None:
        params["task_id"] = task_id
    if min_confidence is not None:
        params["min_confidence"] = min_confidence
    return json.dumps(_api("GET", "/api/internal/findings", params=params), default=str)


@mcp.tool()
def finding_validate(finding_id: int) -> str:
    """Validate a provisional finding, changing its status to active.

    Args:
        finding_id: ID of the finding to validate
    """
    return json.dumps(
        _api("POST", f"/api/internal/findings/{finding_id}/validate", data={
            "agent_id": AGENT_ID,
        }),
        default=str,
    )


@mcp.tool()
def finding_reject(finding_id: int, reason: str = "") -> str:
    """Reject a finding, marking it as superseded.

    Args:
        finding_id: ID of the finding to reject
        reason: Reason for rejection
    """
    return json.dumps(
        _api("POST", f"/api/internal/findings/{finding_id}/reject", data={
            "agent_id": AGENT_ID,
            "reason": reason,
        }),
        default=str,
    )


# ═══════════════════════════════════════════════════════════════════════
# WIKI
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def wiki_read(path: str | None = None, search: str | None = None) -> str:
    """Read a wiki page by path, or search wiki content.

    Args:
        path: Wiki page path (e.g. 'architecture/overview'). Omit to list all pages.
        search: Search query to find wiki pages by content
    """
    if search:
        return json.dumps(
            _api("GET", "/api/wiki-search", params={"project_id": PROJECT_ID, "q": search}),
            default=str,
        )
    if path:
        return json.dumps(_api("GET", f"/api/wiki/{path}"), default=str)
    return json.dumps(
        _api("GET", "/api/wiki", params={"project_id": PROJECT_ID}),
        default=str,
    )


@mcp.tool()
def wiki_write(
    path: str,
    title: str,
    content: str,
) -> str:
    """Create or update a wiki page.

    Args:
        path: Wiki page path (e.g. 'architecture/overview')
        title: Page title
        content: Page content (markdown)
    """
    # Try PUT first (update), fall back to POST (create)
    result = _api("PUT", f"/api/wiki/{path}", data={
        "project_id": int(PROJECT_ID),
        "title": title,
        "content": content,
        "updated_by": AGENT_ID,
    })
    if "error" in result:
        result = _api("POST", "/api/wiki", data={
            "project_id": int(PROJECT_ID),
            "path": path,
            "title": title,
            "content": content,
            "created_by": AGENT_ID,
        })
    return json.dumps(result, default=str)


# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def query_database(sql_query: str, row_limit: int = 100) -> str:
    """Execute a read-only SQL query against the project database.

    Only SELECT and WITH (CTE) statements are allowed. Useful for analytics,
    progress tracking, and data exploration.

    Key tables: tasks, epics, milestones, findings, chat_messages, wiki_pages,
    agent_runs, code_reviews, artifacts.

    Args:
        sql_query: A SELECT SQL query
        row_limit: Maximum rows to return (1-500, default 100)
    """
    return json.dumps(
        _api("POST", "/api/internal/query", data={
            "sql_query": sql_query,
            "row_limit": row_limit,
        }),
        default=str,
    )


# ═══════════════════════════════════════════════════════════════════════
# GIT
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_pr(
    title: str,
    base: str = "main",
    head: str | None = None,
    body: str | None = None,
) -> str:
    """Create a pull request on Forgejo.

    Args:
        title: PR title
        base: Target branch (default: main)
        head: Source branch (default: current branch)
        body: PR description
    """
    return json.dumps(
        _api("POST", "/api/internal/git/create-pr", data={
            "project_id": int(PROJECT_ID),
            "title": title,
            "base": base,
            "head": head,
            "body": body,
        }),
        default=str,
    )


# ═══════════════════════════════════════════════════════════════════════
# SESSION
# ═══════════════════════════════════════════════════════════════════════

@mcp.tool()
def session_save(phase: str, notes: dict | None = None) -> str:
    """Save a session note for context continuity across runs.

    Args:
        phase: Current work phase (e.g. 'implementation', 'review')
        notes: Key-value pairs to persist (progress, decisions, blockers)
    """
    return json.dumps(
        _api("POST", "/api/internal/session-note", data={
            "project_id": int(PROJECT_ID),
            "agent_id": AGENT_ID,
            "phase": phase,
            "notes": notes or {},
        }),
        default=str,
    )


@mcp.tool()
def session_load() -> str:
    """Load your previous session note (phase, notes, timestamp)."""
    return json.dumps(
        _api("GET", "/api/internal/session-note", params={
            "project_id": PROJECT_ID,
            "agent_id": AGENT_ID,
        }),
        default=str,
    )


# ── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
