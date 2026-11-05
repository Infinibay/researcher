"""Typed tool-facing commands; project, task and actor come only from a grant."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.research.investigation import InvestigationSummary
from backend.research.papers import resolve_paper

Identity = Annotated[int, Field(strict=True, gt=0)]


class Command(BaseModel):
    """Reject undeclared fields and bind a stable operation identity for mutation retries."""

    model_config = ConfigDict(extra="forbid")
    operation_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class CaptureCommand(Command):
    """Identify an actual retained job; all output, origin and authority are resolved by the host."""

    job_id: str = Field(min_length=1, max_length=128)


class ProposeResult(Command):
    """Select final persisted research reports without accepting or publishing them."""

    report_ids: list[Identity] = Field(min_length=1, max_length=20)
    summary: str = Field(min_length=1, max_length=12000)
    limitations: list[str] = Field(min_length=1, max_length=20)


class WriteInvestigationSummary(Command):
    """Typed exploratory content only; project, task, author and permissions come from the live native grant."""

    summary: InvestigationSummary


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


class ReviewCheckBody(BaseModel):
    """One explicit reviewer assertion; not_checked is distinct from supported."""

    model_config = ConfigDict(extra="forbid")
    criterion: str = Field(min_length=1, max_length=80)
    outcome: Literal["supported", "concern", "not_checked", "not_applicable"]
    explanation: str = Field(min_length=1, max_length=4000)


class RecordReview(Command):
    """Decide only the reviewer grant's stored subject, with no caller-chosen scope."""

    verdict: Literal["supported", "needs_revision", "inconclusive"]
    rationale: str = Field(min_length=1, max_length=12000)
    checks: list[ReviewCheckBody] = Field(min_length=1, max_length=12)
    evidence: list[Citation] = Field(max_length=20)
    limitations: list[str] = Field(min_length=1, max_length=12)


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


class FindingEvidence(EvidenceResponse):
    """Keep incomplete legacy relationships visible without inventing missing source metadata."""

    kind: str | None
    locator: str | None
    title: str | None
    sha256: str | None
    captured_at: float | None
    finding_status: str | None
    quote_is_exact: bool
    quote_offset: int | None
    source_unavailable: bool
    quote_chars: int
    quote_truncated: bool


class FindingDetail(TextWindow):
    """Page current text and citations; historical status/confidence never certify independent review."""

    finding_id: int
    project_id: int
    task_id: int | None
    topic: str
    agent_id: str | None
    created_at: str | None
    finding_type: str | None
    status: str | None
    confidence: float | None
    scientific_confidence: float | None
    confidence_origin: str
    validation_method: str | None
    reproducibility_score: float | None
    review_status: str
    legacy_review_status: str | None = None
    review: dict[str, Any] | None = None
    legacy_sources_json: str | None
    legacy_sources_total_chars: int
    legacy_sources_next_offset: int | None
    evidence: list[FindingEvidence]
    total_evidence: int
    evidence_offset: int
    next_evidence_offset: int | None


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


class WriteWiki(Command):
    """Write only the grant-bound project's wiki with an observed revision and stable intent."""

    path: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=1200)
    content: str = Field(max_length=200000)
    expected_revision: int = Field(strict=True, ge=0)
    page_id: Identity | None = None
    parent_path: str | None = Field(default=None, max_length=512)


class CaptureWiki(Command):
    """Name one immutable wiki revision and explicit namespace to capture as evidence."""

    page_id: Identity
    revision: Identity
    namespace: Literal["project", "global"] = "project"


class WikiRevision(BaseModel):
    """One explicit authorized project/global revision in a bounded wiki corpus."""

    model_config = ConfigDict(extra="forbid")
    page_id: Identity
    revision: Identity
    namespace: Literal["project", "global"] = "project"


class CaptureWikiCollection(Command):
    """Capture every selected revision for normal exact/semantic source retrieval, or fail as a whole."""

    members: list[WikiRevision] = Field(min_length=1, max_length=50)
