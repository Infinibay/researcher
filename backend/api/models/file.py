"""Pydantic models for reference file resources."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ReferenceFileResponse(BaseModel):
    """Stored reference metadata; it does not establish successful reading or capture."""

    id: int
    project_id: int
    filename: str
    filepath: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    description: str | None = None
    uploaded_at: str | None = None


class ReferencePreviewResponse(BaseModel):
    """Point-in-time extracted text for its owner, without a persisted research source."""

    file_id: int
    project_id: int
    title: str
    content: str
    content_sha256: str
    provenance: dict[str, Any]
    previewed_at: float
    persisted_source: Literal[False] = False
