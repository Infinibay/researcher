"""Pydantic models for task resources."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CommentType = Literal["comment", "change_request", "approval", "question", "answer"]


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    type: str = Field(default="code")
    milestone_id: int | None = None
    epic_id: int | None = None
    project_id: int | None = None
    priority: int = Field(default=2, ge=1, le=5)
    complexity: str = Field(default="medium")
    depends_on: list[int] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    reviewer: str | None = None
    branch_name: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class TaskResponse(BaseModel):
    id: int
    project_id: int | None = None
    epic_id: int | None = None
    milestone_id: int | None = None
    type: str | None = None
    status: str
    title: str
    description: str | None = None
    priority: int | None = None
    estimated_complexity: str | None = None
    assigned_to: str | None = None
    reviewer: str | None = None
    branch_name: str | None = None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0


class TaskCommentCreate(BaseModel):
    author: str = Field(default="user")
    content: str = Field(..., min_length=1)
    comment_type: CommentType = Field(default="comment")


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    author: str
    comment_type: CommentType
    content: str
    created_at: str | None = None


class TaskDependencyCreate(BaseModel):
    depends_on: list[int]
    dependency_type: str = Field(default="blocks")


class TaskDependencyResponse(BaseModel):
    task_id: int
    depends_on_task_id: int
    dependency_type: str
