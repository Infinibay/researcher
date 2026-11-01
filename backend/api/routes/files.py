"""Owner reference uploads, scoped metadata, confined downloads and honest previews.

Previewing extracts a point-in-time revision, without granting agent authority or
creating a research source. New uploads are bounded; legacy downloads can stream.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
import re
import sqlite3
import time
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from backend.api import config as api_config
from backend.api.exceptions import FileNotFoundError_
from backend.api.models.file import ReferenceFileResponse, ReferencePreviewResponse
from backend.db.connection import connect
from backend.research.acquisition import BoundedReferenceReader
from backend.research.models import ReferenceRecord, SourceTooLarge
from backend.research.parser_process import PDFParser
from backend.research.reference_storage import ReferenceStorage

router = APIRouter(prefix="/api/files", tags=["files"])
MAX_UPLOAD = 1000000
COLUMNS = "id,project_id,file_name AS filename,file_path AS filepath,file_size,file_type AS mime_type,description,uploaded_at"


@contextmanager
def _connection(request):
    """Use the serving research database when bound; never initialize a missing source."""
    store = getattr(request.app.state, "runtime_research_store", None)
    runtime = getattr(request.app.state, "runtime_service", None)
    if store is None and runtime is not None:
        store = runtime.research
    if store is None:
        from backend.tools.base.db import get_db_path

        database = get_db_path()
    else:
        database = store.database
    with closing(connect(database, existing_only=True)) as conn, conn:
        yield conn


def _get(conn, file_id, project_id=None):
    """Resolve file and optional visible-project identity before exposing any content."""
    row = conn.execute(
        f"SELECT {COLUMNS} FROM reference_files WHERE id=? AND (? IS NULL OR project_id=?)",
        (file_id, project_id, project_id),
    ).fetchone()
    if row is None:
        raise FileNotFoundError_(file_id)
    return dict(row)


def _reference(row):
    """Translate stored metadata to the acquisition contract without accepting request paths."""
    return ReferenceRecord(
        row["id"],
        row["project_id"],
        row["filename"],
        row["filepath"],
        row["mime_type"] or "application/octet-stream",
    )


@router.get("", response_model=list[ReferenceFileResponse])
def list_files(
    request: Request,
    project_id: int = Query(..., gt=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=200),
):
    """Page one project's metadata, with literal name/description search and stable ordering."""
    with _connection(request) as conn:
        return [
            dict(row)
            for row in conn.execute(
                f"SELECT {COLUMNS} FROM reference_files WHERE project_id=? AND instr(lower(file_name || ' ' || coalesce(description,'')),lower(?))>0 ORDER BY uploaded_at DESC,id DESC LIMIT ? OFFSET ?",
                (project_id, q.strip(), limit, offset),
            ).fetchall()
        ]


def _save_upload(request, project_id, filename, content, mime_type, description):
    """Commit metadata after a private file is durable; preserve bytes on uncertain commit."""
    storage = ReferenceStorage(Path(api_config.UPLOAD_DIR))
    with _connection(request) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if (
            conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
            is None
        ):
            raise HTTPException(404, "Project not found")
        path = storage.save(project_id, content)
        try:
            cursor = conn.execute(
                "INSERT INTO reference_files(project_id,file_name,file_path,file_size,file_type,description) VALUES(?,?,?,?,?,?)",
                (project_id, filename, str(path), len(content), mime_type, description),
            )
            row = _get(conn, cursor.lastrowid, project_id)
        except sqlite3.Error:
            storage.remove(
                ReferenceRecord(1, project_id, filename, str(path), mime_type)
            )
            raise
        # A commit failure can be uncertain: do not remove bytes already referenced
        # by a possibly durable row. The API must not report successful upload.
    return row


@router.post("", response_model=ReferenceFileResponse, status_code=201)
async def upload_file(
    request: Request,
    file: Annotated[UploadFile, File()],
    project_id: int = Query(..., gt=0),
    description: str = Form("", max_length=2000),
):
    """Store one bounded multipart attachment; uploading never starts inference or capture."""
    raw = (file.filename or "upload").replace("\\", "/")
    filename = "".join(c for c in Path(raw).name if c.isprintable())
    if not filename or filename in (".", "..") or len(filename) > 255:
        raise HTTPException(400, "Invalid filename")
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise SourceTooLarge("Reference upload exceeds 1000000 bytes")
    mime_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if not re.fullmatch(r"[a-z0-9.+_-]+/[a-z0-9.+_-]+", mime_type):
        mime_type = "application/octet-stream"
    if content.startswith(b"%PDF-"):
        mime_type = "application/pdf"
    elif mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(filename)[0] or mime_type
    return await asyncio.to_thread(
        _save_upload, request, project_id, filename, content, mime_type, description
    )


@router.get("/{file_id}", response_model=ReferenceFileResponse)
def get_file_metadata(
    file_id: int, request: Request, project_id: int | None = Query(None, gt=0)
):
    """Read metadata only in the requested project; old unscoped owner callers remain valid."""
    with _connection(request) as conn:
        return _get(conn, file_id, project_id)


@router.get("/{file_id}/preview", response_model=ReferencePreviewResponse)
def preview_file(file_id: int, request: Request, project_id: int = Query(..., gt=0)):
    """Extract a bounded owner preview with hash/provenance; do not mint a source receipt."""
    with _connection(request) as conn:
        row = _get(conn, file_id, project_id)
    parser = PDFParser(
        owner=request.app.state.live_grants, grant_id="owner-preview:" + uuid4().hex
    )
    draft = BoundedReferenceReader(Path(api_config.UPLOAD_DIR), pdf_parser=parser).read(
        _reference(row)
    )
    return ReferencePreviewResponse(
        file_id=file_id,
        project_id=project_id,
        title=draft.title,
        content=draft.content,
        content_sha256=hashlib.sha256(draft.content.encode("utf-8")).hexdigest(),
        provenance=draft.provenance,
        previewed_at=time.time(),
    )


@router.get("/{file_id}/download")
def download_file(
    file_id: int, request: Request, project_id: int | None = Query(None, gt=0)
):
    """Stream the pinned upload FD, including large legacy files, without reopening paths."""
    with _connection(request) as conn:
        row = _get(conn, file_id, project_id)
    stack = ExitStack()
    try:
        fd = stack.enter_context(
            ReferenceStorage(Path(api_config.UPLOAD_DIR)).open(_reference(row))
        )
    except FileNotFoundError as exc:
        stack.close()
        raise FileNotFoundError_(file_id) from exc
    except BaseException:
        stack.close()
        raise
    size = os.fstat(fd).st_size

    def content():
        """Read only the opened revision's size, then close even after client disconnect."""
        try:
            remaining = size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            stack.close()

    return StreamingResponse(
        content(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename*=utf-8''"
            + quote(row["filename"], safe=""),
            "Content-Length": str(size),
        },
        background=BackgroundTask(stack.close),
    )


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: int, request: Request, project_id: int | None = Query(None, gt=0)
):
    """Remove a scoped upload and its metadata; existing captured sources/reports survive."""
    with _connection(request) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get(conn, file_id, project_id)
        ReferenceStorage(Path(api_config.UPLOAD_DIR)).remove(_reference(row))
        conn.execute("DELETE FROM reference_files WHERE id=?", (file_id,))
