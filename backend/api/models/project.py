"""Pydantic models for project resources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    task_counts: dict[str, int] = Field(default_factory=dict)
    total_tasks: int = 0
    total_epics: int = 0


class ProjectList(BaseModel):
    projects: list[ProjectResponse]
    total: int


class EpicProgressItem(BaseModel):
    id: int
    title: str
    total: int
    done: int
    pct: int


class BlockingTaskInfo(BaseModel):
    id: int
    title: str
    status: str


class BlockedTaskItem(BaseModel):
    id: int
    title: str
    status: str
    blocked_by: list[BlockingTaskInfo] = Field(default_factory=list)


class ProjectProgressResponse(BaseModel):
    total_tasks: int
    done: int
    in_progress: int
    blocked: int
    blocked_tasks: list[BlockedTaskItem] = Field(default_factory=list)
    completion_pct: int
    by_status: dict[str, int] = Field(default_factory=dict)
    epic_progress: list[EpicProgressItem] = Field(default_factory=list)
    milestone_progress: list[EpicProgressItem] = Field(default_factory=list)
