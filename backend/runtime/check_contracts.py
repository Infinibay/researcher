"""Immutable candidate and recipe identities for host-observed checks, without execution or acceptance authority."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from backend.runtime.contracts import identity, text

_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _digest(value):
    """Fingerprint a complete neutral value without mutable refs, ambient paths or dictionary ordering."""
    return hashlib.sha256(
        json.dumps(asdict(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class CandidateSubject:
    """Exact original candidate scope; checks for another repository, tree, attempt or context are unrelated evidence."""

    project_id: int
    task_id: int
    repository_id: int
    run_id: str
    attempt_id: str
    context_version: int
    fence: int
    base_sha: str
    head_sha: str
    tree_sha: str
    diff_sha256: str

    def __post_init__(self):
        """Require complete positive scope and full Git/content identities before deriving a fingerprint."""
        for value in (
            self.project_id,
            self.task_id,
            self.repository_id,
            self.context_version,
            self.fence,
        ):
            identity(value)
        for value in (self.run_id, self.attempt_id):
            text(value, "Candidate scope identifier", 128)
        if any(
            not isinstance(value, str) or not _SHA.fullmatch(value)
            for value in (self.base_sha, self.head_sha, self.tree_sha)
        ):
            raise ValueError("Candidate requires full Git identities")
        if not isinstance(self.diff_sha256, str) or not _DIGEST.fullmatch(
            self.diff_sha256
        ):
            raise ValueError("Candidate requires a complete diff digest")

    @classmethod
    def from_row(cls, row):
        """Read a ready historical candidate as data; current authority still requires a separate live validation."""
        if row.get("state") != "ready":
            raise ValueError("Candidate is not ready")
        try:
            return cls(**{name: row[name] for name in cls.__dataclass_fields__})
        except KeyError as exc:
            raise ValueError("Candidate scope is incomplete") from exc

    @property
    def sha256(self):
        """Return the canonical exact-subject fingerprint, never a branch name or latest-result alias."""
        return _digest(self)


@dataclass(frozen=True)
class CheckSpec:
    """Host-selected immutable command recipe and explicit environment; this value does not authorize launching it."""

    argv: tuple[str, ...]
    framework: str
    timeout_seconds: float = 60
    output_bytes: int = 65536
    environment_id: str = "system"

    def __post_init__(self):
        """Reject implicit executable resolution, mutable argv, unsupported result protocols and unbounded work."""
        if not isinstance(self.argv, tuple) or not 1 <= len(self.argv) <= 256:
            raise ValueError("Check argv must be a bounded immutable tuple")
        if (
            any(not isinstance(value, str) or "\0" in value for value in self.argv)
            or sum(len(value.encode()) for value in self.argv) > 64000
        ):
            raise ValueError("Check argv exceeds its complete input budget")
        program = PurePosixPath(self.argv[0])
        if not program.is_absolute() or ".." in program.parts:
            raise ValueError("Check executable must be an explicit absolute path")
        if self.framework not in ("command", "pytest"):
            raise ValueError("Unsupported check result protocol")
        if (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 300
        ):
            raise ValueError("Check requires a finite deadline of at most 300 seconds")
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        if (
            type(self.output_bytes) is not int
            or not 1 <= self.output_bytes <= 4 * 1024**2
        ):
            raise ValueError("Check output requires an explicit byte bound")
        text(self.environment_id, "Check environment identity", 128)

    @property
    def sha256(self):
        """Bind outcomes to the complete command, protocol, environment and resource policy."""
        return _digest(self)


@dataclass(frozen=True)
class CheckObservation:
    """Host-collected terminal evidence; model assertions cannot stand in for owned process and workspace observations."""

    subject: CandidateSubject
    spec_sha256: str
    exit_code: int | None
    execution_closed: bool
    output_complete: bool
    workspace_matches: bool
    junit_xml: bytes | None = None

    def __post_init__(self):
        """Keep unknown termination explicit and reject ambiguous boolean or text report representations."""
        if not isinstance(self.subject, CandidateSubject):
            raise TypeError("A candidate subject is required")
        if not isinstance(self.spec_sha256, str) or not _DIGEST.fullmatch(
            self.spec_sha256
        ):
            raise ValueError("Check recipe digest is incomplete")
        if self.exit_code is not None and type(self.exit_code) is not int:
            raise ValueError("Exit code must be an integer or unknown")
        if any(
            type(value) is not bool
            for value in (
                self.execution_closed,
                self.output_complete,
                self.workspace_matches,
            )
        ):
            raise ValueError("Check evidence flags must be explicit booleans")
        if self.junit_xml is not None and not isinstance(self.junit_xml, bytes):
            raise TypeError("Report must be complete bytes or absent")


@dataclass(frozen=True)
class CheckOutcome:
    """Typed check classification, not independent review, owner acceptance or permission to publish."""

    subject: CandidateSubject
    spec_sha256: str
    status: str
    reason: str
    exit_code: int | None
    tests: int | None = None
    failures: int | None = None
    errors: int | None = None
    skipped: int | None = None
