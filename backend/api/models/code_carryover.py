"""Strict owner selection of earlier native code input; callers cannot provide replacement bytes or origin claims."""

from pydantic import BaseModel, ConfigDict, Field


class PriorCodeSelection(BaseModel):
    """Observed original attempt and packet fingerprint shared by Tasks and Conversation admissions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def target(self):
        """Translate the validated selection to the runtime's neutral typed contract."""
        from backend.runtime.code_carryover import PriorCodeTarget

        return PriorCodeTarget(self.attempt_id, self.snapshot_sha256)
