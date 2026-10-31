"""Plain research contracts and evidence rules; no framework or I/O imports."""

import re
from dataclasses import dataclass, field
from typing import Literal

PERMISSIONS = frozenset(
    {
        "sources.read",
        "sources.capture",
        "findings.read",
        "findings.write",
        "reports.read",
        "reports.write",
    }
)


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
    grant_id: str
    project_id: int
    task_id: int
    agent_id: str
    context_version: int
    permissions: frozenset[str]


@dataclass(frozen=True)
class SourceDraft:
    kind: Literal["attachment", "web"]
    locator: str
    title: str
    content: str
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in ("attachment", "web"):
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
