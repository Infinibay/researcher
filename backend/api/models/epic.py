"""Pydantic models for epic resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EpicCreate(BaseModel):
    """Owner group metadata with an optional stable delivery identity for existing clients."""

    project_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    priority: int = Field(default=2, ge=1, le=5)
    operation_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")


class EpicUpdate(BaseModel):
    """Validate optional planning-group metadata edits; guarded routes own history and lifecycle checks."""
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class EpicResponse(BaseModel):
    """Registered group data; creation replies additionally identify the exact original owner request."""

    operation_key: str | None = None
    id: int
    project_id: int
    title: str
    description: str | None = None
    status: str
    priority: int
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    task_count: int = 0
    tasks_done: int = 0
    milestone_count: int = 0
