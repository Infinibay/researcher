"""Pydantic models for finding resources."""

from __future__ import annotations

from pydantic import BaseModel


class FindingResponse(BaseModel):
    """Expose a stored claim and declared confidence or validation labels, without asserting scientific verification."""
    id: int
    project_id: int | None = None
    task_id: int
    agent_run_id: str | None = None
    topic: str
    content: str
    sources_json: str | None = None
    confidence: float | None = None
    agent_id: str
    status: str | None = None
    finding_type: str | None = None
    validation_method: str | None = None
    reproducibility_score: float | None = None
    created_at: str | None = None


class FindingSearchResult(BaseModel):
    """Carry a ranked stored-claim match; similarity and declared confidence do not validate its truth."""
    id: int
    topic: str
    content: str
    confidence: float | None = None
    status: str | None = None
    finding_type: str | None = None
    agent_id: str
    created_at: str | None = None
    similarity: float
