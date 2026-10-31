"""Artifact list and detail endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query

from backend.api.models.artifact import ArtifactDetailResponse, ArtifactListResponse
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api", tags=["artifacts"])


@router.get("/artifacts", response_model=list[ArtifactListResponse])
async def list_artifacts(
    project_id: int = Query(...),
    type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List artifacts for a project (without content for performance)."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        clauses = ["a.project_id = ?"]
        params: list = [project_id]
        if type is not None:
            clauses.append("a.type = ?")
            params.append(type)
        params.append(limit)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"""SELECT a.id, a.project_id, a.task_id, a.type, a.file_path, a.description, a.created_at, r.title, r.status AS research_status
                FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id
                WHERE {where}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    results = execute_with_retry(_query)
    return [ArtifactListResponse(**r) for r in results]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetailResponse)
async def get_artifact(artifact_id: int, project_id: int = Query(..., gt=0)):
    """Get a single artifact with content."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT a.*,r.title,r.status AS research_status FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id WHERE a.id=? AND a.project_id=?",
            (artifact_id, project_id),
        ).fetchone()
        return dict(row) if row else None

    result = execute_with_retry(_query)
    if not result:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactDetailResponse(**result)
