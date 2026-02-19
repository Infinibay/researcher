"""Pydantic models for reference file resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceFileResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    filepath: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    description: str | None = None
    uploaded_at: str | None = None
