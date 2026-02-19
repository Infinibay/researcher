"""Pydantic models for epic resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EpicCreate(BaseModel):
    project_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    priority: int = Field(default=2, ge=1, le=5)


class EpicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class EpicResponse(BaseModel):
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
