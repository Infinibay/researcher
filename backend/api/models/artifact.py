"""Pydantic models for artifact resources."""

from __future__ import annotations

from pydantic import BaseModel


class ArtifactListResponse(BaseModel):
    id: int
    project_id: int | None = None
    task_id: int | None = None
    type: str
    file_path: str
    description: str | None = None
    created_at: str | None = None


class ArtifactDetailResponse(ArtifactListResponse):
    content: str | None = None
