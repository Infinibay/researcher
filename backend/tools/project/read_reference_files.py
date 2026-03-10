"""Tool for reading project reference files."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry, sanitize_fts5_query


class ReadReferenceFilesInput(BaseModel):
    project_id: int | None = Field(
        default=None, description="Project ID (uses current if None)"
    )
    search: str | None = Field(
        default=None,
        description=(
            "Full-text search query. "
            "Supports: | for OR, & for AND, * for prefix, \"quotes\" for exact phrases."
        ),
    )


class ReadReferenceFilesTool(InfinibayBaseTool):
    name: str = "read_reference_files"
    description: str = (
        "List and search project reference files (PDFs, papers, etc.). "
        "Use search for full-text matching across file names and descriptions."
    )
    args_schema: Type[BaseModel] = ReadReferenceFilesInput

    def _run(
        self,
        project_id: int | None = None,
        search: str | None = None,
    ) -> str:
        if project_id is None:
            project_id = self._validate_project_context()

        def _read(conn: sqlite3.Connection) -> list[dict]:
            if search:
                safe_search = sanitize_fts5_query(search)
                rows = conn.execute(
                    """SELECT rf.id, rf.file_name, rf.file_path, rf.file_type,
                              rf.file_size, rf.description, rf.uploaded_by,
                              rf.uploaded_at, rf.tags_json
                       FROM reference_files rf
                       JOIN reference_files_fts fts ON rf.id = fts.rowid
                       WHERE fts.reference_files_fts MATCH ?
                         AND rf.project_id = ?
                       ORDER BY rank
                       LIMIT 50""",
                    (safe_search, project_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, file_name, file_path, file_type,
                              file_size, description, uploaded_by,
                              uploaded_at, tags_json
                       FROM reference_files
                       WHERE project_id = ?
                       ORDER BY uploaded_at DESC""",
                    (project_id,),
                ).fetchall()

            return [dict(r) for r in rows]

        try:
            files = execute_with_retry(_read)
        except Exception as e:
            return self._error(f"Failed to read reference files: {e}")

        return self._success({"files": files, "count": len(files)})
