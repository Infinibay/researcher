"""Pydantic models for user request resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserRequestResponse(BaseModel):
    id: int
    project_id: int
    agent_id: str | None = None
    agent_run_id: str | None = None
    request_type: str = "question"
    title: str
    body: str
    options_json: str = "[]"
    status: str = "pending"
    response: str | None = None
    created_at: str | None = None
    responded_at: str | None = None


class UserRequestRespond(BaseModel):
    response: str = Field(..., min_length=1)


class UserRequestList(BaseModel):
    requests: list[UserRequestResponse]
    total: int
