"""Readonly candidate-source windows reuse the bounded no-follow reference-storage traversal.

Only source path policy differs from uploads. Hashing complete bytes does not
mean the model inspected them all; every returned text window declares its range.
"""

import hashlib
from dataclasses import asdict
from pathlib import Path

from backend.research.models import (
    InvalidEvidence,
    ResearchInputError,
    SourceTooLarge,
    SourceUnavailable,
)
from backend.research.reference_storage import ReferenceStorage
from backend.runtime.code_review_models import (
    CodeReviewReference,
    candidate_source_path,
)
from backend.runtime.development_workspace import _source_identity

MAX_CODE_FILE_BYTES = 4 * 1024**2


class _CandidateStorage(ReferenceStorage):
    """Private traversal adapter: retain safe FD acquisition while replacing upload-specific project/path policy."""

    def _parts(self, reference):
        """Use an already validated relative source reference, not an arbitrary upload record or host filename."""
        return candidate_source_path(reference)


def verify_source_quote(reference, data):
    """Verify complete raw SHA and a quote beginning within its declared source line; return attributed observation only."""
    if (
        not isinstance(reference, CodeReviewReference)
        or hashlib.sha256(data).hexdigest() != reference.sha256
    ):
        raise InvalidEvidence("Review reference belongs to another source version")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise InvalidEvidence(
            "Text review references require UTF-8 source bytes"
        ) from exc
    lines = text.splitlines(keepends=True)
    index = reference.start_line - 1
    if index >= len(lines):
        raise InvalidEvidence("Review quotation line does not exist")
    offset = "".join(lines[index:]).find(reference.quote)
    if not 0 <= offset < len(lines[index]):
        raise InvalidEvidence(
            "Review quotation does not match its declared source line"
        )
    return {
        **asdict(reference),
        "start_character_column": offset + 1,
        "source_bytes": len(data),
    }


class CodeReviewFiles:
    """Expose bounded readonly source acquisition without inheriting the upload storage's mutation API."""

    def __init__(self, view):
        """Bind a host-selected candidate directory identity, retaining all path confinement inside the private adapter."""
        self.view = view
        self._storage = _CandidateStorage(Path(view.workspace))

    def _bytes(self, path):
        """Read stable finite regular-file bytes through pinned no-follow directory descriptors and recheck root identity."""
        candidate_source_path(path)
        _source_identity(self.view)
        try:
            data = self._storage.snapshot(path, max_bytes=MAX_CODE_FILE_BYTES)
        except SourceTooLarge as exc:
            raise SourceTooLarge(
                "Candidate source exceeds the four MiB complete-file limit"
            ) from exc
        except (OSError, SourceUnavailable) as exc:
            raise SourceUnavailable(
                "Candidate source is unavailable, redirected or changing"
            ) from exc
        _source_identity(self.view)
        return data

    def read(self, path, *, offset=0, max_chars=12000):
        """Return a complete-byte hash plus one explicit character window, never an unmarked truncation or a read-all claim."""
        if (
            type(offset) is not int
            or offset < 0
            or type(max_chars) is not int
            or not 1 <= max_chars <= 24000
        ):
            raise ResearchInputError("Code source requires a bounded character window")
        data = self._bytes(path)
        try:
            text = data.decode("utf-8")
        except UnicodeError as exc:
            raise SourceUnavailable(
                "Candidate file is not UTF-8 text; inspect its captured binary diff"
            ) from exc
        if offset > len(text):
            raise ResearchInputError("Code source offset exceeds its complete text")
        end = min(len(text), offset + max_chars)
        return {
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "offset": offset,
            "end_offset": end,
            "total_chars": len(text),
            "text": text[offset:end],
            "next_offset": end if end < len(text) else None,
            "complete_file": offset == 0 and end == len(text),
        }

    def verify(self, reference):
        """Bind a file quotation to its actual stable bytes; diff references use their immutable captured bytes separately."""
        if not isinstance(reference, CodeReviewReference) or reference.kind != "file":
            raise InvalidEvidence("Expected a candidate-file review reference")
        return verify_source_quote(reference, self._bytes(reference.path))
