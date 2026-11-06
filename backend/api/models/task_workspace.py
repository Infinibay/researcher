"""Typed advisory task writes with host-owned identity and explicit revision checks."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.api.models.research import Command

Statement = Annotated[str, Field(min_length=1, max_length=2000)]
Phase = Literal["thinking", "locating", "implementing", "testing", "decomposing",
                "searching", "evaluating", "synthesizing", "reporting"]
CommentType = Literal["comment", "change_request", "question", "answer"]


class ContinuityNote(BaseModel):
    """Separate an agent's observations from assumptions and proposed next actions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(min_length=1, max_length=8000)
    observations: list[Statement] = Field(default_factory=list, max_length=16)
    assumptions: list[Statement] = Field(default_factory=list, max_length=16)
    next_steps: list[Statement] = Field(default_factory=list, max_length=16)


class AddTaskComment(Command):
    """Append advisory text to the current task, without model-chosen authors or approval."""

    content: str = Field(min_length=1, max_length=12000)
    comment_type: CommentType = "comment"


class SaveContinuity(Command):
    """Compare the observed note hash before replacing the current actor/task record."""

    phase: Phase
    note: ContinuityNote
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    last_file: str | None = Field(default=None, min_length=1, max_length=1024)
