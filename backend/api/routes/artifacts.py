"""Read project-scoped saved artifacts and report citations for the owner.

Authentication is supplied by the API's owner-session middleware. These readers
do not issue agent grants, open source files, or trigger model/source captures.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.api.models.artifact import (
    ArtifactDetailResponse,
    ArtifactEvidenceResponse,
    ArtifactListResponse,
)
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api", tags=["artifacts"])

# The immutable proposal contains the exact selected report and its original hash.
# Keeping this read projection separate preserves the report's original draft flag.
_OWNER_ACCEPTANCE = """(
    SELECT json_object('run_id',decision.run_id,'task_id',decision.task_id,
        'context_version',proposal.context_version,'accepted_at',decision.accepted_at,
        'report_sha256',json_extract(report.value,'$.content_sha256'),
        'validity','not_rechecked','matches_current_content',NULL)
    FROM runtime_result_acceptances decision
    JOIN runtime_result_proposals proposal ON proposal.id=decision.proposal_id
        AND proposal.project_id=decision.project_id AND proposal.task_id=decision.task_id
        AND proposal.run_id=decision.run_id
    JOIN json_each(proposal.snapshot_json,'$.reports') report
    WHERE decision.project_id=a.project_id AND decision.task_id=a.task_id
        AND json_extract(report.value,'$.artifact_id')=a.id
    ORDER BY decision.id DESC LIMIT 1
)"""


def _artifact_record(row):
    """Decode historical identity, hashing only a requested detail body without certifying context validity."""
    result = dict(row)
    acceptance = result.get("owner_acceptance")
    if acceptance is not None:
        acceptance = json.loads(acceptance)
        if "content" in result:
            acceptance["matches_current_content"] = (
                isinstance(result["content"], str)
                and hashlib.sha256(result["content"].encode()).hexdigest()
                == acceptance["report_sha256"]
            )
        result["owner_acceptance"] = acceptance
    return result


@router.get("/artifacts", response_model=list[ArtifactListResponse])
def list_artifacts(
    project_id: int = Query(...),
    type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
    research_status: Literal["draft", "accepted", "superseded"] | None = None,
):
    """Page scoped metadata, separating original document flags from historical owner acceptance.

    Search matches the case-insensitive title/path plus description, not bodies.
    Creation time and ID give deterministic ordering for equal timestamps.
    Accepted includes original accepted flags and exact owner decisions; draft
    excludes owner-accepted results without rewriting their original draft flag.
    """

    def _query(conn: sqlite3.Connection) -> list[dict]:
        """Apply bound filter values and return one metadata-only catalog page."""
        clauses = ["a.project_id = ?"]
        params: list = [project_id]
        if type is not None:
            clauses.append("a.type = ?")
            params.append(type)
        if research_status == "accepted":
            clauses.append(f"(r.status='accepted' OR {_OWNER_ACCEPTANCE} IS NOT NULL)")
        elif research_status == "draft":
            clauses.append(f"(r.status='draft' AND {_OWNER_ACCEPTANCE} IS NULL)")
        elif research_status is not None:
            clauses.append("r.status = ?")
            params.append(research_status)
        if q and q.strip():
            clauses.append(
                "instr(lower(coalesce(r.title,a.file_path) || ' ' || coalesce(a.description,'')),lower(?)) > 0"
            )
            params.append(q.strip())
        params.extend((limit, offset))
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"""SELECT a.id, a.project_id, a.task_id, a.type, a.file_path, a.description, a.created_at, r.title, r.status AS research_status, {_OWNER_ACCEPTANCE} AS owner_acceptance
                FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id
                WHERE {where}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()
        return [_artifact_record(r) for r in rows]

    results = execute_with_retry(_query)
    return [ArtifactListResponse(**r) for r in results]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetailResponse)
def get_artifact(artifact_id: int, project_id: int = Query(..., gt=0)):
    """Read the stored body for a matching project, or return 404 without it."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        """Resolve both artifact and project identity before returning content."""
        row = conn.execute(
            f"SELECT a.*,r.title,r.status AS research_status,{_OWNER_ACCEPTANCE} AS owner_acceptance FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id WHERE a.id=? AND a.project_id=?",
            (artifact_id, project_id),
        ).fetchone()
        return _artifact_record(row) if row else None

    result = execute_with_retry(_query)
    if not result:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactDetailResponse(**result)


@router.get(
    "/artifacts/{artifact_id}/evidence", response_model=ArtifactEvidenceResponse
)
def get_artifact_evidence(
    artifact_id: int,
    project_id: int = Query(..., gt=0),
    offset: int = Query(default=0, ge=0),
):
    """Owner-only citation reader. No tool grant, file access or new capture.

    All relations retain project identity, including in legacy inconsistent data.
    One read transaction keeps header/count/page on the same SQLite snapshot.
    """

    def _query(conn):
        """Read hash, count and up to 20 citations in one SQLite snapshot."""
        conn.execute("BEGIN")
        artifact = conn.execute(
            "SELECT r.content_sha256 FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id WHERE a.id=? AND a.project_id=?",
            (artifact_id, project_id),
        ).fetchone()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        relations = """FROM report_findings rf
            JOIN finding_sources fs ON fs.project_id=rf.project_id AND fs.finding_id=rf.finding_id
            JOIN research_sources s ON s.project_id=fs.project_id AND s.id=fs.source_id
            JOIN findings f ON f.project_id=rf.project_id AND f.id=rf.finding_id
            WHERE rf.project_id=? AND rf.artifact_id=?"""
        total = conn.execute(
            "SELECT count(*) " + relations, (project_id, artifact_id)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT fs.finding_id,fs.source_id,fs.quote,s.kind,s.locator,s.title,s.sha256,s.captured_at,f.status AS finding_status "
            + relations
            + " ORDER BY fs.finding_id,fs.source_id,fs.quote LIMIT 20 OFFSET ?",
            (project_id, artifact_id, offset),
        ).fetchall()
        end = offset + len(rows)
        return {
            "artifact_id": artifact_id,
            "project_id": project_id,
            "content_sha256": artifact[0],
            "evidence": [dict(row) for row in rows],
            "total_evidence": total,
            "offset": offset,
            "next_offset": end if end < total else None,
        }

    return execute_with_retry(_query)
