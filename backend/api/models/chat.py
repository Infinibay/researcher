"""Pydantic models for chat resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)
    to_agent: str | None = None
    to_role: str = Field(default="project_lead")


class ChatMessageResponse(BaseModel):
    id: int
    project_id: int
    thread_id: str | None = None
    from_agent: str
    to_agent: str | None = None
    to_role: str | None = None
    message: str
    conversation_type: str
    created_at: str | None = None


class ChatThreadResponse(BaseModel):
    thread_id: str
    project_id: int
    thread_type: str | None = None
    created_at: str | None = None
    last_message: str | None = None
    message_count: int = 0


class UnreadCountsResponse(BaseModel):
    counts: dict[str, int]


class ThreadArchiveResponse(BaseModel):
    thread_id: str
    status: str
