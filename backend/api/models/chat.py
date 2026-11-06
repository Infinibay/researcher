"""Pydantic models for chat resources."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.models.code_carryover import PriorBranchSelection, PriorCodeSelection, PriorFilesSelection


class ChatMessageCreate(BaseModel):
    """Explanatory note only; native instructions and corrections have their own typed endpoints."""

    model_config = ConfigDict(extra="forbid", strict=True)
    operation_key: str | None = Field(None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    message: str = Field(..., min_length=1, max_length=50000)
    to_agent: str | None = None
    to_role: str = Field(default="project_lead")
    thread_id: str | None = Field(None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")


class ChatMessageResponse(BaseModel):
    """Persisted attributed conversation and its delivery receipt, independent of task activation."""

    operation_key: str | None = None
    id: int
    project_id: int
    thread_id: str | None = None
    from_agent: str
    to_agent: str | None = None
    to_role: str | None = None
    message: str
    conversation_type: str
    created_at: str | None = None
    runtime_run_id: str | None = None
    runtime_status: str | None = None
    context_version: int | None = None
    task_id: int | None = None
    delivery: Literal[
        "recorded", "instruction_admitted", "proposal", "question", "answer"
    ] = "recorded"

    @model_validator(mode="after")
    def delivery_receipt(self):
        if self.runtime_run_id is not None and self.delivery == "recorded":
            self.delivery = (
                "instruction_admitted"
                if self.conversation_type == "user_to_agent"
                else "proposal"
            )
        return self


class NativeInstruction(BaseModel):
    """Fresh owner instruction with an exact optional prior-code input selection, never inherited approval."""

    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: int = Field(gt=0)
    context_version: int = Field(gt=0)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    thread_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    message: str = Field(min_length=1, max_length=50000)
    repository_id: int | None = Field(None, gt=0)
    prior_code: PriorCodeSelection | PriorFilesSelection | PriorBranchSelection | None = None


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
