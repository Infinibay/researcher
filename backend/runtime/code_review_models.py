"""Immutable attributed code-review assertions and exact source references, without acceptance or execution authority."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from backend.research.models import (
    InvalidEvidence,
    ResearchInputError,
    ReviewCheck,
    bounded_text,
)


def candidate_source_path(value):
    """Accept only canonical relative source files, excluding Git/Ken metadata and traversal aliases."""
    bounded_text(value, "Candidate source path", 4096)
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or str(path) != value
        or not path.parts
        or any(part in ("..", ".git", ".ken") for part in path.parts)
    ):
        raise ResearchInputError(
            "Candidate source requires a canonical relative code path"
        )
    return path.parts


@dataclass(frozen=True)
class CodeReviewReference:
    """One exact quoted source line and complete file/diff hash, not evidence that its claim is logically supported."""

    kind: str
    path: str
    sha256: str
    start_line: int
    quote: str

    def __post_init__(self):
        """Reject ambiguous source identity, metadata aliases, invalid positions and unbounded quotations."""
        if self.kind == "file":
            candidate_source_path(self.path)
        elif self.kind != "diff" or self.path != "":
            raise ResearchInputError(
                "Review reference must identify a candidate file or its complete diff"
            )
        if not isinstance(self.sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.sha256
        ):
            raise ResearchInputError("Review reference requires a complete SHA-256")
        if type(self.start_line) is not int or self.start_line <= 0:
            raise ResearchInputError(
                "Review reference requires an actual positive source line"
            )
        bounded_text(self.quote, "Review quotation", 4000)


@dataclass(frozen=True)
class CodeReviewDecision:
    """Bounded reviewer assertions with explicit checks, exact references and scope limitations; never a task approval."""

    verdict: str
    rationale: str
    checks: tuple[ReviewCheck, ...]
    references: tuple[CodeReviewReference, ...]
    limitations: tuple[str, ...]

    @classmethod
    def from_data(cls, value):
        """Reconstruct neutral JSON data through the same immutable validation used for a native proposal."""
        try:
            return cls(
                value["verdict"],
                value["rationale"],
                tuple(ReviewCheck(**item) for item in value["checks"]),
                tuple(CodeReviewReference(**item) for item in value["references"]),
                tuple(value["limitations"]),
            )
        except (KeyError, TypeError) as exc:
            raise ResearchInputError("Malformed code-review decision data") from exc

    def __post_init__(self):
        """Require internally consistent immutable evidence rather than converting fluent prose into a positive verdict."""
        if self.verdict not in ("supported", "needs_revision", "inconclusive"):
            raise ResearchInputError("Unsupported code-review verdict")
        bounded_text(self.rationale, "Code-review rationale", 12000)
        if (
            not isinstance(self.checks, tuple)
            or not 1 <= len(self.checks) <= 12
            or any(not isinstance(check, ReviewCheck) for check in self.checks)
            or len({check.criterion for check in self.checks}) != len(self.checks)
        ):
            raise ResearchInputError(
                "A code review requires 1–12 distinct immutable explained checks"
            )
        if (
            not isinstance(self.references, tuple)
            or len(self.references) > 20
            or any(not isinstance(ref, CodeReviewReference) for ref in self.references)
            or len(set(self.references)) != len(self.references)
        ):
            raise InvalidEvidence(
                "A code review permits at most20 distinct exact source references"
            )
        if (
            not isinstance(self.limitations, tuple)
            or not 1 <= len(self.limitations) <= 12
        ):
            raise ResearchInputError(
                "A code review requires 1–12 immutable explicit limitations"
            )
        for value in self.limitations:
            bounded_text(value, "Code-review limitation", 2000)
        if self.verdict == "supported" and (
            not self.references
            or not any(check.outcome == "supported" for check in self.checks)
            or any(check.outcome in ("concern", "not_checked") for check in self.checks)
        ):
            raise InvalidEvidence(
                "Supported code review needs exact evidence and no explicitly unresolved checks"
            )
