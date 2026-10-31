"""Typed tool-facing commands; project, task and actor come only from a grant."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Identity = Annotated[int, Field(strict=True, gt=0)]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class CaptureReference(Command):
    reference_file_id: Identity


class CaptureWeb(Command):
    url: str = Field(min_length=1, max_length=4096)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: Identity
    quote: str = Field(min_length=1, max_length=8000)


class RecordFinding(Command):
    topic: str = Field(min_length=1, max_length=1200)
    content: str = Field(min_length=1, max_length=100000)
    finding_type: Literal[
        "observation", "hypothesis", "experiment", "proof", "conclusion"
    ] = "observation"
    evidence: list[Citation] = Field(min_length=1, max_length=20)


class WriteReport(Command):
    title: str = Field(min_length=1, max_length=1200)
    content: str = Field(min_length=1, max_length=500000)
    finding_ids: list[Identity] = Field(min_length=1, max_length=50)
    report_type: Literal["research", "analysis", "summary"] = "research"


class SourceReceipt(BaseModel):
    source_id: int
    sha256: str
    kind: str
    locator: str
    operation_key: str


class FindingReceipt(BaseModel):
    finding_id: int
    status: str
    confidence: float | None = None
    operation_key: str


class ReportReceipt(BaseModel):
    artifact_id: int
    title: str
    status: str
    operation_key: str


class TextWindow(BaseModel):
    content: str
    total_chars: int
    offset: int
    next_offset: int | None


class SourceWindow(TextWindow):
    source_id: int
    project_id: int
    captured_for_task_id: int
    kind: str
    locator: str
    title: str
    sha256: str
    captured_at: float
    provenance: dict[str, Any]


class EvidenceResponse(BaseModel):
    finding_id: int
    source_id: int
    quote: str
    kind: str
    locator: str
    title: str
    sha256: str
    captured_at: float
    finding_status: str


class FindingDetail(BaseModel):
    finding_id: int
    project_id: int
    task_id: int
    topic: str
    content: str
    finding_type: str
    status: str
    confidence: float | None
    evidence: list[EvidenceResponse]


class ReportWindow(TextWindow):
    artifact_id: int
    project_id: int
    title: str
    status: str
    report_type: str
    content_sha256: str
    finding_ids: list[int]
    evidence: list[EvidenceResponse]
    total_evidence: int
    evidence_offset: int
    next_evidence_offset: int | None
