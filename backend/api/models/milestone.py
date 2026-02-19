"""Pydantic models for milestone resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MilestoneCreate(BaseModel):
    epic_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    due_date: str | None = None


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    due_date: str | None = None


class MilestoneResponse(BaseModel):
    id: int
    project_id: int | None = None
    epic_id: int
    title: str
    description: str | None = None
    status: str
    due_date: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    task_count: int = 0
    tasks_done: int = 0
