"""Plain research contracts and evidence rules; no framework or I/O imports."""

import re
from dataclasses import dataclass, field
from typing import Literal

RESEARCH_PERMISSIONS = frozenset(
    {
        "sources.read",
        "sources.capture",
        "findings.read",
        "findings.write",
        "reports.read",
        "reports.write",
        "results.propose",
        "questions.ask",
        "wiki.read",
        "wiki.write",
    }
)
REVIEW_PERMISSIONS = frozenset(
    {
        "sources.read",
        "findings.read",
        "reports.read",
        "wiki.read",
        "questions.ask",
        "findings.review",
    }
)
DEVELOPMENT_PERMISSIONS = RESEARCH_PERMISSIONS - {"results.propose"}
CODE_REVIEW_PERMISSIONS = REVIEW_PERMISSIONS - {"findings.review"}
PERMISSIONS = RESEARCH_PERMISSIONS | REVIEW_PERMISSIONS


class ResearchInputError(ValueError):
    """A research command violates its input contract."""


class ResearchForbidden(PermissionError):
    """Scope is expired, revoked, stale or lacks the required permission."""


class ResearchNotFound(LookupError):
    """The requested object does not exist within this scope."""


class OperationConflict(RuntimeError):
    """An operation identity was reused for a different intent."""


class InvalidEvidence(ResearchInputError):
    """A citation or report basis does not support the requested record."""


@dataclass(frozen=True)
class ReviewTarget:
    """Owner-observed finding and complete subject fingerprint for review admission."""

    finding_id: int
    subject_sha256: str

    def __post_init__(self):
        """Reject ambiguous identities before constructing a durable review request."""
        positive_id(self.finding_id)
        if not isinstance(self.subject_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.subject_sha256
        ):
            raise ResearchInputError(
                "Review subject requires an observed SHA-256 fingerprint"
            )


def bounded_text(value: str, name: str, max_bytes: int) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > max_bytes
    ):
        raise ResearchInputError(
            f"{name} must be nonempty and at most {max_bytes} UTF-8 bytes"
        )


def positive_id(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ResearchInputError("Expected a positive integer identity")


def operation_key(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        raise ResearchInputError(
            "Operation key must contain 1–128 ASCII letters, numbers, dots, colons, dashes or underscores"
        )


@dataclass(frozen=True)
class ResearchScope:
    """Host-issued project/task/context identity; every adapter must recheck stored grant authority."""

    grant_id: str
    project_id: int
    task_id: int
    agent_id: str
    context_version: int
    permissions: frozenset[str]


@dataclass(frozen=True)
class SourceDraft:
    """Bound exact captured document text and provenance before an immutable scoped source commit."""

    kind: Literal["attachment", "web", "wiki"]
    locator: str
    title: str
    content: str
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate supported source kind and UTF-8 limits; provenance is evidence, not authorization."""
        if self.kind not in ("attachment", "web", "wiki"):
            raise ResearchInputError("Unsupported source kind")
        bounded_text(self.locator, "locator", 4096)
        bounded_text(self.title, "title", 1200)
        bounded_text(self.content, "source content", 200000)


@dataclass(frozen=True)
class EvidenceReference:
    source_id: int
    quote: str

    def __post_init__(self):
        positive_id(self.source_id)
        bounded_text(self.quote, "quote", 8000)

    def validate_against(self, source: dict) -> None:
        if self.quote not in source["content"]:
            raise InvalidEvidence(
                "Citation is not an exact excerpt of the captured source"
            )


@dataclass(frozen=True)
class ReviewCheck:
    """One attributed reviewer check, explicitly distinguishing missing assessment."""

    criterion: str
    outcome: str
    explanation: str

    def __post_init__(self):
        """Bound named checks without inferring quality from a checkbox count."""
        bounded_text(self.criterion, "review criterion", 80)
        bounded_text(self.explanation, "review explanation", 4000)
        if self.outcome not in (
            "supported",
            "concern",
            "not_checked",
            "not_applicable",
        ):
            raise ResearchInputError("Unsupported review check outcome")


@dataclass(frozen=True)
class ReviewDecision:
    """Version-specific reviewer assertions and exact evidence, never task acceptance."""

    verdict: str
    rationale: str
    checks: tuple[ReviewCheck, ...]
    evidence: tuple[EvidenceReference, ...]
    limitations: tuple[str, ...]

    def __post_init__(self):
        """Require a bounded, internally consistent explanation and explicit limits."""
        if self.verdict not in ("supported", "needs_revision", "inconclusive"):
            raise ResearchInputError("Unsupported review verdict")
        bounded_text(self.rationale, "review rationale", 12000)
        if not 1 <= len(self.checks) <= 12 or len(
            {c.criterion for c in self.checks}
        ) != len(self.checks):
            raise ResearchInputError("A review needs 1–12 distinct explained checks")
        if len(self.evidence) > 20 or len(set(self.evidence)) != len(self.evidence):
            raise InvalidEvidence(
                "A review permits at most 20 distinct exact citations"
            )
        if not 1 <= len(self.limitations) <= 12:
            raise ResearchInputError("A review needs 1–12 explicit scope limitations")
        for limit in self.limitations:
            bounded_text(limit, "review limitation", 2000)
        if self.verdict == "supported" and (
            not self.evidence
            or any(c.outcome in ("concern", "not_checked") for c in self.checks)
        ):
            raise InvalidEvidence(
                "A supported verdict needs exact evidence and no explicitly unresolved checks"
            )


@dataclass(frozen=True)
class FindingDraft:
    topic: str
    content: str
    evidence: tuple[EvidenceReference, ...]
    finding_type: str = "observation"

    def __post_init__(self):
        bounded_text(self.topic, "topic", 1200)
        bounded_text(self.content, "finding content", 100000)
        if self.finding_type not in (
            "observation",
            "hypothesis",
            "experiment",
            "proof",
            "conclusion",
        ):
            raise ResearchInputError("Unsupported finding type")
        if not 1 <= len(self.evidence) <= 20:
            raise InvalidEvidence("A finding needs 1–20 exact source excerpts")
        if len(set(self.evidence)) != len(self.evidence):
            raise InvalidEvidence("Duplicate citations")


@dataclass(frozen=True)
class ReportDraft:
    title: str
    content: str
    finding_ids: tuple[int, ...]
    report_type: str = "research"

    def __post_init__(self):
        bounded_text(self.title, "title", 1200)
        if "\n" in self.title or "\r" in self.title:
            raise ResearchInputError("Report title must be a single line")
        bounded_text(self.content, "report content", 500000)
        if self.report_type not in ("research", "analysis", "summary"):
            raise ResearchInputError("Unsupported report type")
        if not 1 <= len(self.finding_ids) <= 50 or len(set(self.finding_ids)) != len(
            self.finding_ids
        ):
            raise InvalidEvidence("A report needs 1–50 distinct findings")
        for identity in self.finding_ids:
            positive_id(identity)

    @property
    def markdown(self) -> str:
        return f"# {self.title}\n\n{self.content}"


@dataclass(frozen=True)
class ResultDraft:
    """Select actual final reports and attributed limitations; this declaration never accepts a task."""

    report_ids: tuple[int, ...]
    summary: str
    limitations: tuple[str, ...]

    def __post_init__(self):
        """Refuse ambiguous/oversized selections without inferring final drafts from writer activity."""
        if (
            not isinstance(self.report_ids, tuple)
            or not 1 <= len(self.report_ids) <= 20
            or len(set(self.report_ids)) != len(self.report_ids)
        ):
            raise ResearchInputError("Select 1–20 distinct report ids for delivery")
        for report_id in self.report_ids:
            positive_id(report_id)
        bounded_text(self.summary, "delivery summary", 12000)
        if (
            not isinstance(self.limitations, tuple)
            or not 1 <= len(self.limitations) <= 20
        ):
            raise ResearchInputError(
                "State 1–20 actual limitations of the delivered work"
            )
        for limitation in self.limitations:
            bounded_text(limitation, "delivery limitation", 4000)


class SourceUnavailable(RuntimeError):
    """A source cannot be safely acquired or decoded; do not fabricate content."""


class SourceTooLarge(ResearchInputError):
    """Acquisition refused its size bound rather than silently truncating."""


@dataclass(frozen=True)
class ReferenceRecord:
    id: int
    project_id: int
    filename: str
    path: str
    mime_type: str


def validate_report_finding(finding: dict, evidence: list[dict]) -> None:
    if finding["status"] == "superseded":
        raise InvalidEvidence("Report cannot use a superseded finding")
    if not evidence:
        raise InvalidEvidence("Finding has no captured source excerpts")
