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


class PeerMessageSource(BaseModel):
    """Identify the captured source bytes without endorsing the sender's interpretation."""

    source_id: int
    sha256: str


class PeerMessageReceipt(BaseModel):
    """Expose exact sender/recipient context and receipt without asserting understanding or approval."""

    message_id: int
    parent_message_id: int | None
    sender_run_id: str
    sender_attempt_id: str
    sender_task_id: int
    sender_context_version: int
    recipient_run_id: str
    recipient_task_id: int
    recipient_context_version: int
    recipient_context_current: bool
    recipient_status: str
    intent: Literal["note", "question", "answer"]
    body_sha256: str
    delivery: Literal["recorded", "receipt_acknowledged"]
    acknowledged_by_attempt: str | None
    acknowledged_at: float | None
    observations: list[str]
    assumptions: list[str]
    evidence_refs: list[PeerMessageSource]
    authorizes_work: Literal[False] = False
    understood: Literal["not_verified"] = "not_verified"
    applied: Literal["not_verified"] = "not_verified"


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
    peer_message: PeerMessageReceipt | None = None
    delivery: Literal[
        "recorded", "instruction_admitted", "proposal", "question", "answer"
    ] = "recorded"

    @model_validator(mode="after")
    def delivery_receipt(self):
        """Derive native owner delivery from canonical run links, never from advisory peer metadata."""
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
    """Expose a stored conversation identity, scope, last message and message count."""
    thread_id: str
    project_id: int
    thread_type: str | None = None
    created_at: str | None = None
    last_message: str | None = None
    message_count: int = 0


class UnreadCountsResponse(BaseModel):
    """Carry per-conversation unread counts rather than agent-message acknowledgement authority."""
    counts: dict[str, int]


class ThreadArchiveResponse(BaseModel):
    """Identify the thread and the recorded result of its archive operation."""
    thread_id: str
    status: str
