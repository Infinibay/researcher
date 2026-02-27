"""Tool for reading wiki pages."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry, sanitize_fts5_query


class ReadWikiInput(BaseModel):
    page: str | None = Field(
        default=None, description="Wiki page path to read (e.g. 'architecture/overview')"
    )
    search: str | None = Field(
        default=None, description="Full-text search query across wiki pages"
    )


class ReadWikiTool(PabadaBaseTool):
    name: str = "read_wiki"
    description: str = (
        "Read wiki pages. Specify a page path for a specific page, "
        "use search for full-text search, or call with no args for the index."
    )
    args_schema: Type[BaseModel] = ReadWikiInput

    def _run(
        self, page: str | None = None, search: str | None = None
    ) -> str:
        project_id = self.project_id

        def _read(conn: sqlite3.Connection):
            if page:
                # Read specific page
                row = conn.execute(
                    """SELECT id, path, title, content, parent_path,
                              created_by, updated_by, created_at, updated_at
                       FROM wiki_pages
                       WHERE path = ? AND (project_id = ? OR project_id IS NULL)""",
                    (page, project_id),
                ).fetchone()

                if not row:
                    raise ValueError(f"Wiki page '{page}' not found")
                return dict(row)

            elif search:
                # Full-text search
                safe_search = sanitize_fts5_query(search)
                rows = conn.execute(
                    """SELECT wp.id, wp.path, wp.title,
                              snippet(wiki_fts, 2, '<b>', '</b>', '...', 64) AS snippet,
                              wp.updated_at
                       FROM wiki_pages wp
                       JOIN wiki_fts ON wp.id = wiki_fts.rowid
                       WHERE wiki_fts MATCH ?
                         AND (wp.project_id = ? OR wp.project_id IS NULL)
                       ORDER BY rank
                       LIMIT 20""",
                    (safe_search, project_id),
                ).fetchall()
                return {"results": [dict(r) for r in rows], "count": len(rows)}

            else:
                # Return index of all pages
                rows = conn.execute(
                    """SELECT id, path, title, parent_path, updated_at
                       FROM wiki_pages
                       WHERE project_id = ? OR project_id IS NULL
                       ORDER BY path""",
                    (project_id,),
                ).fetchall()
                return {"pages": [dict(r) for r in rows], "count": len(rows)}

        try:
            result = execute_with_retry(_read)
        except ValueError as e:
            return self._error(str(e))

        return self._success(result)
