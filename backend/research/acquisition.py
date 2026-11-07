"""Capture confined text, PDF and structured uploads as immutable research-source snapshots.

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

STRUCTURED_MIMES = {
    "text/csv": "csv",
    "application/csv": "csv",
    "application/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


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
            or reference.mime_type in (*STRUCTURED_MIMES, "application/pdf")
        ):
            raise SourceUnavailable(
                "This acquisition route supports UTF-8 text, PDF, DOCX, CSV, JSON and XML attachments"
            )
        data = ReferenceStorage(self.upload_root).snapshot(
            reference, max_bytes=self.max_bytes
        )
        byte_hash=hashlib.sha256(data).hexdigest()
        imported=getattr(reference,'imported_provenance',None)
        if imported is not None and byte_hash!=imported['sha256']:
            raise SourceUnavailable('Imported fragment bytes changed; its historical provenance cannot describe this revision')
        if reference.mime_type in STRUCTURED_MIMES:
            from backend.research.parser_process import DocumentParser

            parser = self.pdf_parser or DocumentParser()
            content, extraction = parser.for_format(
                STRUCTURED_MIMES[reference.mime_type]
            ).read(bytes(data))
        elif reference.mime_type == "application/pdf":
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
                "byte_sha256": byte_hash,
                "file_size_bytes": len(data),
                "mime_type": reference.mime_type,
                **extraction,
                **({'imported_history':imported['details']} if imported is not None else {}),
            },
        )
