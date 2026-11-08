"""Pydantic models for task resources."""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, model_validator

CommentType = Literal["comment", "change_request", "approval", "question", "answer"]


class TaskCreate(BaseModel):
    """Owner task metadata and optional stable creation key; accept the former complexity field explicitly."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    type: str = Field(default="code")
    milestone_id: int | None = None
    epic_id: int | None = None
    project_id: int | None = None
    priority: int = Field(default=2, ge=1, le=5)
    complexity: str = Field(default="medium", validation_alias=AliasChoices("complexity", "estimated_complexity"))
    depends_on: list[int] = Field(default_factory=list)
    operation_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")

    @model_validator(mode='before')
    @classmethod
    def unambiguous_complexity(cls, value):
        """Reject contradictory old/new fields rather than silently discarding the owner's selected value."""
        if isinstance(value, dict) and 'complexity' in value and 'estimated_complexity' in value and value['complexity'] != value['estimated_complexity']:
            raise ValueError('complexity and estimated_complexity must agree when both are supplied')
        return value


class TaskUpdate(BaseModel):
    """Selective owner metadata edits; native lifecycle changes require distinct execution controls."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    assigned_to: str | None = None
    reviewer: str | None = None
    branch_name: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class TaskResponse(BaseModel):
    """Task record; a creation response additionally identifies the original owner's request."""

    operation_key: str | None = None
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
    """Owner note data and a claimed author label; the note grants no acceptance or execution authority."""

    author: str = Field(default="user")
    content: str = Field(..., min_length=1)
    comment_type: CommentType = Field(default="comment")


class TaskCommentResponse(BaseModel):
    """Persisted note without interpreting its approval/change label as a native control receipt."""

    id: int
    task_id: int
    author: str
    comment_type: CommentType
    content: str
    created_at: str | None = None


class TaskDependencyCreate(BaseModel):
    """Replace one typed outgoing relation set; the owner store validates each target in its project."""

    depends_on: list[int]
    dependency_type: str = Field(default="blocks")


class TaskDependencyResponse(BaseModel):
    """Original directed relation endpoints; incoming queries retain their original direction."""

    task_id: int
    depends_on_task_id: int
    dependency_type: str
