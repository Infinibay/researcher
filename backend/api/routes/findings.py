"""Findings list, FTS search, semantic search, and detail endpoints."""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Query

from backend.api.models.finding import FindingResponse, FindingSearchResult
from backend.tools.base.db import execute_with_retry, sanitize_fts5_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["findings"])


@router.get("/findings", response_model=list[FindingResponse])
async def list_findings(
    project_id: int = Query(...),
    q: str | None = Query(default=None),
    finding_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    min_confidence: float | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List/search findings. Uses FTS5 when q is provided."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        if q:
            safe_q = sanitize_fts5_query(q)
            try:
                rows = conn.execute(
                    """SELECT f.* FROM findings f
                       JOIN findings_fts fts ON f.id = fts.rowid
                       WHERE fts.findings_fts MATCH ?
                         AND f.project_id = ?
                       ORDER BY rank
                       LIMIT ?""",
                    (safe_q, project_id, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                # Fallback to LIKE
                like_q = f"%{q}%"
                rows = conn.execute(
                    """SELECT * FROM findings
                       WHERE project_id = ?
                         AND (topic LIKE ? OR content LIKE ?)
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (project_id, like_q, like_q, limit),
                ).fetchall()
                return [dict(r) for r in rows]

        clauses = ["project_id = ?"]
        params: list = [project_id]
        if finding_type is not None:
            clauses.append("finding_type = ?")
            params.append(finding_type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
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

    results = execute_with_retry(_query)
    return [FindingResponse(**r) for r in results]


@router.get("/findings/search", response_model=list[FindingSearchResult])
async def search_findings_semantic(
    project_id: int = Query(...),
    query: str = Query(..., min_length=1),
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Semantic search across findings using embeddings."""
    import numpy as np
    from backend.tools.base.dedup import _cosine_similarity, _get_embed_fn

    def _get_findings(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT id, topic, content, confidence, status, finding_type,
                      agent_id, created_at
               FROM findings
               WHERE project_id = ?
               ORDER BY created_at DESC
               LIMIT 500""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    findings = execute_with_retry(_get_findings)
    if not findings:
        return []

    try:
        embed_fn = _get_embed_fn()
        texts = [f"{f['topic']}: {f['content'][:500]}" for f in findings]
        all_texts = [query] + texts
        embeddings = embed_fn(all_texts)
        query_vec = np.asarray(embeddings[0])

        results = []
        for i, finding in enumerate(findings):
            sim = _cosine_similarity(query_vec, np.asarray(embeddings[i + 1]))
            if sim >= threshold:
                results.append(FindingSearchResult(**finding, similarity=sim))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]
    except Exception as e:
        logger.warning("Semantic search failed, falling back to FTS: %s", e)
        # Fallback to FTS
        def _fts_fallback(conn: sqlite3.Connection) -> list[dict]:
            safe_q = sanitize_fts5_query(query)
            try:
                rows = conn.execute(
                    """SELECT f.id, f.topic, f.content, f.confidence, f.status,
                              f.finding_type, f.agent_id, f.created_at
                       FROM findings f
                       JOIN findings_fts fts ON f.id = fts.rowid
                       WHERE fts.findings_fts MATCH ?
                         AND f.project_id = ?
                       ORDER BY rank
                       LIMIT ?""",
                    (safe_q, project_id, limit),
                ).fetchall()
            except Exception:
                like_q = f"%{query}%"
                rows = conn.execute(
                    """SELECT id, topic, content, confidence, status,
                              finding_type, agent_id, created_at
                       FROM findings
                       WHERE project_id = ? AND (topic LIKE ? OR content LIKE ?)
                       ORDER BY created_at DESC LIMIT ?""",
                    (project_id, like_q, like_q, limit),
                ).fetchall()
            return [dict(r) for r in rows]

        fallback_results = execute_with_retry(_fts_fallback)
        return [FindingSearchResult(**r, similarity=0.0) for r in fallback_results]


@router.get("/findings/{finding_id}", response_model=FindingResponse)
async def get_finding(finding_id: int):
    """Get a single finding by ID."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT * FROM findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
        return dict(row) if row else None

    result = execute_with_retry(_query)
    if not result:
        raise HTTPException(status_code=404, detail="Finding not found")
    return FindingResponse(**result)
