"""Pydantic models for project resources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Owner project metadata with an optional exact original creation identity for response-loss recovery."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=50000)
    operation_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")


class ProjectUpdate(BaseModel):
    """Owner metadata edits can bind the exact displayed scope; completion remains a distinct report decision."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    expected_scope_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ProjectCreationIntent(BaseModel):
    """The original explicit creation scope, unaffected by later project metadata edits."""

    operation_key: str
    name: str
    description: str


class ProjectCreationReceipt(BaseModel):
    """One exact created resource, distinct from current metadata and from any native work admission."""

    project_id: int
    request: ProjectCreationIntent


class ProjectResponse(BaseModel):
    """Project resource metadata; status is a recorded label, while activity and completion validity are separate observations."""
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
    creation: ProjectCreationReceipt | None = None


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
