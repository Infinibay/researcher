"""Pydantic models for milestone resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MilestoneCreate(BaseModel):
    """Owner milestone intent; an explicit project scope and stable key enable exact recovery."""

    epic_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    due_date: str | None = None
    project_id: int | None = Field(default=None, ge=1)
    operation_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    due_date: str | None = None


class MilestoneResponse(BaseModel):
    """Registered milestone data with an original request key only when returning a creation receipt."""

    operation_key: str | None = None
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
