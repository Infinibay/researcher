"""Capture confined UTF-8/PDF uploads as immutable research-source snapshots.

File traversal rejects symlinks and cross-project paths before format extraction.
Original byte identity and parser provenance accompany the saved text.
"""

import hashlib
from pathlib import Path

from backend.research.models import (
    ReferenceRecord,
    SourceDraft,
    SourceUnavailable,
)
from backend.research.reference_storage import ReferenceStorage


class BoundedReferenceReader:
    """Read bounded, stable files under one project upload root; never arbitrary paths."""

    def __init__(self, upload_root: Path, *, max_bytes: int = 1000000, pdf_parser=None):
        """Bind the trusted upload root and maximum bytes before opening a reference."""
        if max_bytes <= 0:
            raise ValueError("Attachment byte limit must be positive")
        self.upload_root = upload_root.absolute()
        self.max_bytes = max_bytes
        self.pdf_parser = pdf_parser

    def read(self, reference: ReferenceRecord) -> SourceDraft:
        """Acquire one stable byte snapshot, then extract supported text with provenance."""
        if not (
            reference.mime_type.startswith("text/")
            or reference.mime_type
            in ("application/json", "application/xml", "application/pdf")
        ):
            raise SourceUnavailable(
                "This acquisition route supports UTF-8 text and PDF attachments; this format requires a dedicated parser"
            )
        data = ReferenceStorage(self.upload_root).snapshot(
            reference, max_bytes=self.max_bytes
        )
        if reference.mime_type == "application/pdf":
            from backend.research.parser_process import PDFParser

            content, extraction = (self.pdf_parser or PDFParser()).read(bytes(data))
        else:
            if data.startswith(b"%PDF-"):
                raise SourceUnavailable(
                    "PDF attachment has a non-PDF media type; upload it as application/pdf"
                )
            try:
                content = bytes(data).decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise SourceUnavailable("Attachment is not valid UTF-8 text") from exc
            extraction = {"extraction": "utf8-v1"}
        return SourceDraft(
            kind="attachment",
            locator=f"reference:{reference.id}",
            title=reference.filename,
            content=content,
            provenance={
                "reference_file_id": reference.id,
                "byte_sha256": hashlib.sha256(data).hexdigest(),
                "file_size_bytes": len(data),
                "mime_type": reference.mime_type,
                **extraction,
            },
        )
