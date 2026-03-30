"""Internal API endpoints for agent pods.

These endpoints are called by the ``infinibay`` CLI and the INFINIBAY MCP server
running inside sandbox containers, providing access to host-side DB
operations that agents need but cannot perform directly from their pod.

Route groups split into separate modules:
- ``internal_findings`` — findings/knowledge CRUD
- ``internal_tasks`` — task approval and rejection
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])


# ── Request/Response models ──────────────────────────────────────────────

class AskTeamLeadRequest(BaseModel):
    project_id: int
    agent_id: str
    question: str


class AskProjectLeadRequest(BaseModel):
    project_id: int
    agent_id: str
    question: str


class ChatSendRequest(BaseModel):
    project_id: int
    from_agent: str
    message: str
    to_agent: str | None = None
    to_role: str | None = None


class QueryRequest(BaseModel):
    sql_query: str
    row_limit: int = Field(default=100, ge=1, le=500)


class CreatePRRequest(BaseModel):
    project_id: int
    title: str
    base: str = "main"
    head: str | None = None
    body: str | None = None


class SessionNoteRequest(BaseModel):
    project_id: int
    agent_id: str
    phase: str
    notes: dict = {}


# ── SQL validation helpers (from NL2SQLTool) ─────────────────────────────

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REPLACE|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)
_ALLOWED_STARTERS = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/ask-team-lead")
async def ask_team_lead(req: AskTeamLeadRequest):
    """Send a question to the team lead via the communication service."""
    from backend.communication.service import CommunicationService

    svc = CommunicationService()
    svc.send(
        project_id=req.project_id,
        from_agent=req.agent_id,
        to_agent=f"team_lead_p{req.project_id}",
        message=req.question,
    )
    return {"status": "sent", "to": f"team_lead_p{req.project_id}"}


@router.post("/ask-project-lead")
async def ask_project_lead(req: AskProjectLeadRequest):
    """Send a question to the project lead via the communication service."""
    from backend.communication.service import CommunicationService

    svc = CommunicationService()
    svc.send(
        project_id=req.project_id,
        from_agent=req.agent_id,
        to_agent=f"project_lead_p{req.project_id}",
        message=req.question,
    )
    return {"status": "sent", "to": f"project_lead_p{req.project_id}"}


@router.post("/chat/send")
async def chat_send(req: ChatSendRequest):
    """Send a message from one agent to another (or to a role)."""
    from backend.communication.service import CommunicationService

    svc = CommunicationService()
    msg_id = svc.send(
        project_id=req.project_id,
        from_agent=req.from_agent,
        message=req.message,
        to_agent=req.to_agent,
        to_role=req.to_role,
    )
    if msg_id == -1:
        return {"error": "Message blocked by loop guard"}
    return {"status": "sent", "message_id": msg_id}


@router.post("/query")
async def query_database(req: QueryRequest):
    """Execute a read-only SQL query against the project database."""
    from backend.config.settings import settings

    # Strip comments before validation
    cleaned = re.sub(r"/\*.*?\*/", " ", req.sql_query, flags=re.DOTALL)
    cleaned = re.sub(r"--[^\n]*", " ", cleaned)

    if not _ALLOWED_STARTERS.match(cleaned):
        return {"error": "Only SELECT and WITH (CTE) queries are allowed."}

    match = _FORBIDDEN_KEYWORDS.search(cleaned)
    if match:
        return {"error": f"Forbidden SQL keyword: {match.group(0)}."}

    row_limit = min(req.row_limit, 500)

    sql = req.sql_query.rstrip().rstrip(";")
    if not re.search(r"\bLIMIT\b", cleaned, re.IGNORECASE):
        sql = f"{sql} LIMIT {row_limit}"

    db_path = settings.DB_PATH
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(row_limit)
        result_rows = [dict(row) for row in rows]
        truncated = len(result_rows) >= row_limit
        conn.close()
    except sqlite3.OperationalError as e:
        return {"error": f"SQL error: {e}"}
    except Exception as e:
        return {"error": f"Query execution failed: {e}"}

    return {
        "query": sql,
        "column_names": columns,
        "rows": result_rows,
        "row_count": len(result_rows),
        "truncated": truncated,
    }


@router.post("/git/create-pr")
async def create_pr(req: CreatePRRequest):
    """Create a pull request on Forgejo and register it in the DB."""
    from backend.config.settings import settings

    if not settings.FORGEJO_API_URL or not settings.FORGEJO_TOKEN:
        return {"error": "Forgejo not configured"}

    import urllib.request

    # Determine head branch
    head = req.head or req.base

    # Resolve the Forgejo repo name from the DB
    repo_name: str | None = None

    def _get_repo(conn: sqlite3.Connection) -> None:
        nonlocal repo_name
        row = conn.execute(
            "SELECT name FROM repositories WHERE project_id = ? AND status = 'active' LIMIT 1",
            (req.project_id,),
        ).fetchone()
        if row:
            repo_name = row[0]

    try:
        execute_with_retry(_get_repo)
    except Exception:
        pass

    if not repo_name:
        return {"error": f"No active repository found for project {req.project_id}"}

    owner = settings.FORGEJO_OWNER or "infinibay"

    # Create PR via Forgejo API
    forgejo_url = f"{settings.FORGEJO_API_URL}/repos/{owner}/{repo_name}/pulls"
    pr_data = json.dumps({
        "title": req.title,
        "head": head,
        "base": req.base,
        "body": req.body or "",
    }).encode()

    api_req = urllib.request.Request(
        forgejo_url,
        data=pr_data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"token {settings.FORGEJO_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(api_req, timeout=15) as resp:
            pr_result = json.loads(resp.read().decode())
    except Exception as exc:
        logger.exception("Failed to create PR on Forgejo")
        return {"error": str(exc)}

    # Register in DB
    pr_number = pr_result.get("number")
    pr_url = pr_result.get("html_url", "")

    def _insert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO pull_requests
                   (project_id, pr_number, title, source_branch, target_branch,
                    url, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)""",
            (req.project_id, pr_number, req.title, head, req.base, pr_url),
        )
        conn.commit()

    try:
        execute_with_retry(_insert)
    except Exception:
        logger.warning("Failed to record PR in DB", exc_info=True)

    return {"pr_number": pr_number, "url": pr_url}


@router.post("/session-note")
async def save_session_note(req: SessionNoteRequest):
    """Save a session note for an agent (for context continuity across runs)."""

    def _upsert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """INSERT INTO session_notes (project_id, agent_id, phase, notes_json, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(project_id, agent_id) DO UPDATE SET
                   phase = excluded.phase,
                   notes_json = excluded.notes_json,
                   updated_at = CURRENT_TIMESTAMP""",
            (req.project_id, req.agent_id, req.phase, json.dumps(req.notes)),
        )
        conn.commit()

    try:
        execute_with_retry(_upsert)
    except Exception:
        # Table may not exist yet — create it
        def _create_and_upsert(conn: sqlite3.Connection) -> None:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_notes (
                    project_id INTEGER NOT NULL,
                    agent_id TEXT NOT NULL,
                    phase TEXT NOT NULL DEFAULT '',
                    notes_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, agent_id)
                )
            """)
            conn.execute(
                """INSERT INTO session_notes (project_id, agent_id, phase, notes_json, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(project_id, agent_id) DO UPDATE SET
                       phase = excluded.phase,
                       notes_json = excluded.notes_json,
                       updated_at = CURRENT_TIMESTAMP""",
                (req.project_id, req.agent_id, req.phase, json.dumps(req.notes)),
            )
            conn.commit()

        execute_with_retry(_create_and_upsert)

    return {"status": "saved"}


@router.get("/session-note")
async def load_session_note(project_id: int, agent_id: str):
    """Load the latest session note for an agent."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            """SELECT phase, notes_json, updated_at FROM session_notes
               WHERE project_id = ? AND agent_id = ?""",
            (project_id, agent_id),
        ).fetchone()
        if row:
            return {
                "phase": row["phase"],
                "notes": json.loads(row["notes_json"]),
                "updated_at": row["updated_at"],
            }
        return None

    try:
        result = execute_with_retry(_query)
    except Exception:
        result = None

    return result or {"phase": "", "notes": {}, "updated_at": None}
