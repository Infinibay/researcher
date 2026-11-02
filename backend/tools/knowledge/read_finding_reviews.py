"""Retained read-only access to actual version-bound finding reviews and immutable subjects."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.knowledge._finding_reader import FINDING_READ_ERRORS, finding_reader


class ReadFindingReviewsInput(BaseModel):
    """Select actual review history, a paged decision or its original frozen subject."""

    model_config = ConfigDict(extra="forbid")
    finding_id: int = Field(ge=1)
    request_id: int | None = Field(None, ge=1)
    part: Literal["decision", "subject"] = "decision"
    after_id: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=50)
    offset: int = Field(0, ge=0)
    max_chars: int = Field(12000, ge=1, le=20000)


class ReadFindingReviewsTool(InfinibayBaseTool):
    """Inspect attributed feedback in the bound project; a role name does not admit a reviewer."""

    name: str = "read_finding_reviews"
    description: str = "Read actual independent-review history for finding_id, then choose request_id to inspect decision or original frozen subject. Follow next_after_id/next_offset. subject_current false means a changed version; null means currentness could not be verified. Historical flags and stored presence do not certify science. This reader cannot record a decision, accept a task or obtain reviewer authority."
    args_schema: type[BaseModel] = ReadFindingReviewsInput

    def _run(
        self,
        finding_id,
        request_id=None,
        part="decision",
        after_id=0,
        limit=20,
        offset=0,
        max_chars=12000,
    ):
        """Read immutable attributed data under explicit project identity with recoverable windows."""
        try:
            store, project, _ = finding_reader(self, 0)
            return self._success(
                store.reviews(
                    project,
                    finding_id,
                    request_id=request_id,
                    part=part,
                    after_id=after_id,
                    limit=limit,
                    offset=offset,
                    max_chars=max_chars,
                )
            )
        except FINDING_READ_ERRORS as exc:
            return self._error(f"Finding review read failed: {exc}")
