"""Reference file upload/download endpoints."""

from __future__ import annotations

import mimetypes
import os
import re
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse

from backend.api import config as api_config
from backend.api.exceptions import FileNotFoundError_
from backend.api.models.file import ReferenceFileResponse
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[ReferenceFileResponse])
async def list_files(project_id: int = Query(...)):
    """List reference files for a project."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT id, project_id, file_name AS filename,
                      file_path AS filepath, file_size,
                      file_type AS mime_type, description, uploaded_at
               FROM reference_files
               WHERE project_id = ?
               ORDER BY uploaded_at DESC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    files = execute_with_retry(_query)
    return [ReferenceFileResponse(**f) for f in files]


@router.post("", response_model=ReferenceFileResponse, status_code=201)
async def upload_file(
    project_id: int = Query(...),
    file: UploadFile = File(...),
    description: str = Form(default=""),
):
    """Upload a reference file."""
    # Sanitize filename: strip path components, reject traversal patterns
    raw_name = file.filename or "upload"
    safe_name = Path(raw_name).name  # strips directory components like ../../
    if not safe_name or safe_name in (".", "..") or ".." in safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Remove any remaining non-printable or shell-special characters
    safe_name = re.sub(r'[^\w.\-]', '_', safe_name)
    if not safe_name:
        safe_name = "upload"

    # Prefix with UUID to avoid collisions and make names unpredictable
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"

    # Determine upload path
    upload_dir = Path(api_config.UPLOAD_DIR) / str(project_id) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filepath = (upload_dir / unique_name).resolve()
    # Verify resolved path is still under upload_dir
    if not str(filepath).startswith(str(upload_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")

    content = await file.read()
    file_size = len(content)

    # Write file
    with open(filepath, "wb") as f:
        f.write(content)

    mime_type = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

    def _insert(conn: sqlite3.Connection) -> dict:
        cursor = conn.execute(
            """INSERT INTO reference_files
               (project_id, file_name, file_path, file_size, file_type, description, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (project_id, safe_name, str(filepath), file_size, mime_type, description),
        )
        conn.commit()
        row = conn.execute(
            """SELECT id, project_id, file_name AS filename,
                      file_path AS filepath, file_size,
                      file_type AS mime_type, description, uploaded_at
               FROM reference_files WHERE id = ?""",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(row)

    result = execute_with_retry(_insert)
    return ReferenceFileResponse(**result)


@router.get("/{file_id}", response_model=ReferenceFileResponse)
async def get_file_metadata(file_id: int):
    """Get file metadata."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            """SELECT id, project_id, file_name AS filename,
                      file_path AS filepath, file_size,
                      file_type AS mime_type, description, uploaded_at
               FROM reference_files WHERE id = ?""",
            (file_id,),
        ).fetchone()
        return dict(row) if row else None

    result = execute_with_retry(_query)
    if not result:
        raise FileNotFoundError_(file_id)
    return ReferenceFileResponse(**result)


@router.get("/{file_id}/download")
async def download_file(file_id: int):
    """Download a reference file."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            """SELECT id, file_name, file_path, file_type
               FROM reference_files WHERE id = ?""",
            (file_id,),
        ).fetchone()
        return dict(row) if row else None

    result = execute_with_retry(_query)
    if not result:
        raise FileNotFoundError_(file_id)

    filepath = result.get("file_path")
    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError_(file_id)

    return FileResponse(
        path=filepath,
        filename=result["file_name"],
        media_type=result.get("file_type", "application/octet-stream"),
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(file_id: int):
    """Delete a reference file from DB and filesystem."""

    def _delete(conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT file_path FROM reference_files WHERE id = ?", (file_id,)
        ).fetchone()
        if not row:
            return None
        filepath = row["file_path"]
        conn.execute("DELETE FROM reference_files WHERE id = ?", (file_id,))
        conn.commit()
        return filepath

    filepath = execute_with_retry(_delete)
    if filepath is None:
        raise FileNotFoundError_(file_id)

    # Remove from filesystem
    if filepath and os.path.exists(filepath):
        os.remove(filepath)
