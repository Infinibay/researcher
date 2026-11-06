"""Typed advisory peer-message commands without caller-selected sender or project authority."""

from typing import Annotated, Literal

from pydantic import Field

from backend.api.models.research import Command

MessageIntent = Literal["note", "question", "answer"]
MessageStatement = Annotated[str, Field(min_length=1, max_length=1000)]


class SendAgentMessage(Command):
    """Address one admitted run and distinguish attributed observations from assumptions."""

    recipient_run_id: str = Field(min_length=1, max_length=128)
    intent: MessageIntent = "note"
    message: str = Field(min_length=1, max_length=12000)
    observations: list[MessageStatement] = Field(default_factory=list, max_length=8)
    assumptions: list[MessageStatement] = Field(default_factory=list, max_length=8)
    source_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=16)
    in_reply_to: int | None = Field(default=None, gt=0)


class AcknowledgeAgentMessage(Command):
    """Acknowledge the original content hash as receipt, never comprehension or approval."""

    message_id: int = Field(gt=0)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
