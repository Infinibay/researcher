"""Capture confined UTF-8/PDF uploads as immutable research-source snapshots.

File traversal rejects symlinks and cross-project paths before format extraction.
Original byte identity and parser provenance accompany the saved text.
"""

import hashlib
import os
import stat
from pathlib import Path

from backend.research.models import (
    ReferenceRecord,
    SourceDraft,
    SourceTooLarge,
    SourceUnavailable,
)


class BoundedReferenceReader:
    """Read bounded, stable files under one project upload root; never arbitrary paths."""

    def __init__(self, upload_root: Path, *, max_bytes: int = 1000000):
        """Bind the trusted upload root and maximum bytes before opening a reference."""
        if max_bytes <= 0:
            raise ValueError("Attachment byte limit must be positive")
        self.upload_root = upload_root.absolute()
        self.max_bytes = max_bytes

    def read(self, reference: ReferenceRecord) -> SourceDraft:
        """Acquire one stable byte snapshot, then extract supported text with provenance."""
        path = Path(reference.path)
        try:
            parts = path.relative_to(self.upload_root).parts
        except ValueError as exc:
            raise SourceUnavailable(
                "Reference is outside the configured project uploads"
            ) from exc
        if (
            ".." in parts
            or len(parts) < 3
            or parts[:2] != (str(reference.project_id), "uploads")
        ):
            raise SourceUnavailable(
                "Reference is outside the configured project uploads"
            )
        if not (
            reference.mime_type.startswith("text/")
            or reference.mime_type
            in ("application/json", "application/xml", "application/pdf")
        ):
            raise SourceUnavailable(
                "This acquisition route supports UTF-8 text and PDF attachments; this format requires a dedicated parser"
            )
        handles = []
        try:
            parent = os.open(
                self.upload_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            handles.append(parent)
            for component in parts[:-1]:
                parent = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent,
                )
                handles.append(parent)
            fd = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            handles.append(fd)
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise SourceUnavailable("Attachment is not a regular file")
            if before.st_size > self.max_bytes:
                raise SourceTooLarge("Attachment exceeds the configured byte limit")
            data = bytearray()
            while len(data) <= self.max_bytes:
                chunk = os.read(fd, min(65536, self.max_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > self.max_bytes:
                raise SourceTooLarge("Attachment exceeds the configured byte limit")
            after = os.fstat(fd)
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ):
                raise SourceUnavailable(
                    "Attachment changed during acquisition; capture a stable revision"
                )
        except OSError as exc:
            raise SourceUnavailable(
                "Attachment is unavailable or contains a symlink outside the allowed file traversal"
            ) from exc
        finally:
            for handle in reversed(handles):
                os.close(handle)
        if reference.mime_type == "application/pdf":
            from backend.research.pdf_text import extract_pdf

            content, extraction = extract_pdf(bytes(data))
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
