"""Strict owner selection of earlier code or file data; callers cannot provide replacement bytes or claim unknown origin."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriorCodeSelection(BaseModel):
    """Observed original attempt and packet fingerprint shared by Tasks and Conversation admissions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def target(self):
        """Translate the validated selection to the runtime's neutral typed contract."""
        from backend.runtime.code_carryover import PriorCodeTarget

        return PriorCodeTarget(self.attempt_id, self.snapshot_sha256)


class FileImportSource(BaseModel):
    """Host-recorded source and explicit relative paths, without replacement bytes or asserted native context."""

    model_config = ConfigDict(extra="forbid", strict=True)
    source_kind: Literal["legacy_worktree", "private_copy"]
    source_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    paths: list[str] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def canonical_selection(self):
        """Reject ambiguous paths and source identities at the HTTP boundary before filesystem access."""
        from backend.runtime.file_imports import PriorFilesTarget

        PriorFilesTarget(self.source_kind, self.source_id, tuple(self.paths), "0" * 64)
        return self


class PreviewFileImport(FileImportSource):
    """Owner preview of selected bytes against a specifically registered canonical source."""

    repository_id: int = Field(gt=0)


class PriorFilesSelection(FileImportSource):
    """Exact observed selected-file data for the next native admission."""

    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def target(self):
        """Keep the original file selection immutable when moving from HTTP to admission policy."""
        from backend.runtime.file_imports import PriorFilesTarget

        return PriorFilesTarget(
            self.source_kind, self.source_id, tuple(self.paths), self.snapshot_sha256
        )
