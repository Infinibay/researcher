"""Typed tool-facing commands; project, task and actor come only from a grant."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.research.papers import resolve_paper

Identity = Annotated[int, Field(strict=True, gt=0)]


class Command(BaseModel):
    """Reject undeclared fields and bind a stable operation identity for mutation retries."""

    model_config = ConfigDict(extra="forbid")
    operation_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class CaptureReference(Command):
    """Capture an attachment id; project and actor are provided by host credentials."""

    reference_file_id: Identity


class CaptureWeb(Command):
    """Capture a supplied URL through the bounded public HTTPS policy."""

    url: str = Field(min_length=1, max_length=4096)


class CapturePaper(Command):
    """Capture exactly one supplied URL/DOI/arXiv locator in the credential-bound project."""

    url: str | None = Field(default=None, max_length=4096)
    doi: str | None = Field(default=None, max_length=2048)
    arxiv_id: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def single_locator(self):
        """Reject ambiguous or malformed identifiers before starting acquisition."""
        resolve_paper(url=self.url, doi=self.doi, arxiv_id=self.arxiv_id)
        return self


class Citation(BaseModel):
    """Refer to one exact saved-source excerpt, not a generated quotation."""

    model_config = ConfigDict(extra="forbid")
    source_id: Identity
    quote: str = Field(min_length=1, max_length=8000)


class RecordFinding(Command):
    """Persist a provisional evidence-backed finding without invented validation confidence."""

    topic: str = Field(min_length=1, max_length=1200)
    content: str = Field(min_length=1, max_length=100000)
    finding_type: Literal[
        "observation", "hypothesis", "experiment", "proof", "conclusion"
    ] = "observation"
    evidence: list[Citation] = Field(min_length=1, max_length=20)


class WriteReport(Command):
    """Persist a draft linked to retained findings; this command does not accept a task."""

    title: str = Field(min_length=1, max_length=1200)
    content: str = Field(min_length=1, max_length=500000)
    finding_ids: list[Identity] = Field(min_length=1, max_length=50)
    report_type: Literal["research", "analysis", "summary"] = "research"


class SourceReceipt(BaseModel):
    """Recover the committed source identity and content hash after an uncertain response."""

    source_id: int
    sha256: str
    kind: str
    locator: str
    operation_key: str


class FindingReceipt(BaseModel):
    """Return persisted finding identity and its actual validation state."""

    finding_id: int
    status: str
    confidence: float | None = None
    operation_key: str


class ReportReceipt(BaseModel):
    """Identify a persisted report draft without implying user acceptance."""

    artifact_id: int
    title: str
    status: str
    operation_key: str


class TextWindow(BaseModel):
    """Bound text by character offsets, exposing an unread tail explicitly."""

    content: str
    total_chars: int
    offset: int
    next_offset: int | None


class SourceWindow(TextWindow):
    """Expose one saved revision and its provenance without host filesystem paths."""

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
    """Keep each exact quotation linked to its source hash and finding status."""

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
    """Read a scoped finding with evidence and the stored, possibly unknown confidence."""

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
    """Page report content and evidence independently so omitted citations remain visible."""

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
