"""Pydantic models for user request resources."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserRequestResponse(BaseModel):
    """Expose a stored human request, its options and any recorded response independently of native admission."""
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
    """Validate one nonempty owner response to the original stored request."""
    response: str = Field(..., min_length=1)


class UserRequestList(BaseModel):
    """Pair returned human-request records with their reported total."""
    requests: list[UserRequestResponse]
    total: int
