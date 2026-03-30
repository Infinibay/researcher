"""Internal API endpoints for findings/knowledge management.

Endpoints for recording, querying, validating, and rejecting research findings.
These are called by the ``infinibay`` CLI and the INFINIBAY MCP server running
inside sandbox containers.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal-findings"])


# ── Request/Response models ──────────────────────────────────────────────

class RecordFindingRequest(BaseModel):
    project_id: int
    agent_id: str
    task_id: int
    title: str
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    finding_type: str = "observation"
    sources: list[str] = Field(default_factory=list)
    artifact_id: int | None = None
    wiki_page_id: int | None = None


class ValidateFindingRequest(BaseModel):
    agent_id: str


class RejectFindingRequest(BaseModel):
    agent_id: str
    reason: str = ""


_FINDING_TYPES = ("observation", "hypothesis", "experiment", "proof", "conclusion")


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/findings")
async def record_finding(req: RecordFindingRequest):
    """Record a research finding."""
    if req.finding_type not in _FINDING_TYPES:
        return {"error": f"Invalid finding_type '{req.finding_type}'. Must be one of: {', '.join(_FINDING_TYPES)}"}

    def _record(conn: sqlite3.Connection) -> int:
        cursor = conn.execute(
            """INSERT INTO findings
               (project_id, task_id, agent_run_id, topic, content,
                sources_json, confidence, agent_id, status, finding_type,
                artifact_id, wiki_page_id)
               VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'provisional', ?, ?, ?)""",
            (
                req.project_id, req.task_id, req.title, req.content,
                json.dumps(req.sources), req.confidence, req.agent_id,
                req.finding_type, req.artifact_id, req.wiki_page_id
            ),
        )
        conn.commit()
        return cursor.lastrowid

    try:
        finding_id = execute_with_retry(_record)
    except Exception as e:
        return {"error": f"Failed to record finding: {e}"}

    return {
        "finding_id": finding_id,
        "title": req.title,
        "finding_type": req.finding_type,
        "confidence": req.confidence,
        "status": "provisional",
    }


@router.get("/findings")
async def read_findings(
    project_id: int,
    query: str | None = Query(default=None),
    task_id: int | None = Query(default=None),
    min_confidence: float | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Search/list findings. Uses FTS5 if query is provided."""

    def _query_findings(conn: sqlite3.Connection) -> list[dict]:
        if query:
            # FTS5 search
            rows = conn.execute(
                """SELECT f.* FROM findings f
                   JOIN findings_fts fts ON f.id = fts.rowid
                   WHERE fts.findings_fts MATCH ?
                     AND f.project_id = ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, project_id, limit),
            ).fetchall()
        else:
            clauses = ["project_id = ?"]
            params: list = [project_id]
            if task_id is not None:
                clauses.append("task_id = ?")
                params.append(task_id)
            if min_confidence is not None:
                clauses.append("confidence >= ?")
                params.append(min_confidence)
            params.append(limit)
            where = " AND ".join(clauses)
            rows = conn.execute(
                f"SELECT * FROM findings WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    try:
        results = execute_with_retry(_query_findings)
    except Exception as e:
        return {"error": str(e), "findings": []}

    return {"findings": results, "count": len(results)}


@router.post("/findings/{finding_id}/validate")
async def validate_finding(finding_id: int, req: ValidateFindingRequest):
    """Validate a provisional finding, changing status to active."""

    def _validate(conn: sqlite3.Connection) -> dict:
        row = conn.execute(
            "SELECT id, status, topic FROM findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Finding {finding_id} not found")
        if row["status"] != "provisional":
            raise ValueError(
                f"Finding {finding_id} is not provisional (current: '{row['status']}')"
            )
        conn.execute(
            "UPDATE findings SET status = 'active' WHERE id = ?",
            (finding_id,),
        )
        conn.commit()
        return {"topic": row["topic"]}

    try:
        result = execute_with_retry(_validate)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "finding_id": finding_id,
        "topic": result["topic"],
        "status": "active",
        "validated_by": req.agent_id,
    }


@router.post("/findings/{finding_id}/reject")
async def reject_finding(finding_id: int, req: RejectFindingRequest):
    """Reject a finding, changing status to superseded."""

    def _reject(conn: sqlite3.Connection) -> dict:
        row = conn.execute(
            "SELECT id, status, topic FROM findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Finding {finding_id} not found")
        conn.execute(
            "UPDATE findings SET status = 'superseded' WHERE id = ?",
            (finding_id,),
        )
        if req.reason:
            conn.execute(
                """INSERT INTO task_comments
                   (task_id, author, comment_type, content)
                   VALUES (
                       (SELECT task_id FROM findings WHERE id = ?),
                       ?, 'note',
                       ?
                   )""",
                (finding_id, req.agent_id, f"Finding #{finding_id} rejected: {req.reason}"),
            )
        conn.commit()
        return {"topic": row["topic"]}

    try:
        result = execute_with_retry(_reject)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "finding_id": finding_id,
        "topic": result["topic"],
        "status": "superseded",
        "rejected_by": req.agent_id,
    }
