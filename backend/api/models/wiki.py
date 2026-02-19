"""Pydantic models for wiki resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WikiPageCreate(BaseModel):
    project_id: int
    path: str = Field(..., min_length=1)
    title: str | None = None
    content: str = Field(default="")


class WikiPageUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class WikiPageResponse(BaseModel):
    id: int | None = None
    project_id: int | None = None
    path: str
    title: str
    content: str | None = None
    parent_path: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WikiSearchResult(BaseModel):
    path: str
    title: str
    snippet: str | None = None
    updated_at: str | None = None
