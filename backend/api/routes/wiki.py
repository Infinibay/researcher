"""Wiki page CRUD and search endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Query

from backend.api.exceptions import WikiPageNotFound
from backend.api.models.wiki import (
    WikiPageCreate,
    WikiPageResponse,
    WikiPageUpdate,
    WikiSearchResult,
)
from backend.tools.base.db import execute_with_retry, sanitize_fts5_query

router = APIRouter(prefix="/api", tags=["wiki"])


@router.get("/wiki", response_model=list[WikiPageResponse])
async def list_wiki_pages(project_id: int = Query(...)):
    """List all wiki pages for a project."""

    def _query(conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """SELECT id, project_id, path, title, parent_path,
                      created_by, updated_by, created_at, updated_at
               FROM wiki_pages
               WHERE project_id = ? OR project_id IS NULL
               ORDER BY path ASC""",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    pages = execute_with_retry(_query)
    return [WikiPageResponse(**p) for p in pages]


@router.post("/wiki", response_model=WikiPageResponse, status_code=201)
async def create_wiki_page(body: WikiPageCreate):
    """Create a new wiki page."""
    title = body.title
    if title is None:
        title = body.path.split("/")[-1].replace("-", " ").replace("_", " ").title()

    def _create(conn: sqlite3.Connection) -> dict:
        # Check if path already exists
        existing = conn.execute(
            "SELECT id FROM wiki_pages WHERE path = ? AND project_id = ?",
            (body.path, body.project_id),
        ).fetchone()
        if existing:
            raise ValueError(f"Wiki page at path '{body.path}' already exists")

        cursor = conn.execute(
            """INSERT INTO wiki_pages
               (project_id, path, title, content, created_by, updated_by)
               VALUES (?, ?, ?, ?, 'api', 'api')""",
            (body.project_id, body.path, title, body.content),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM wiki_pages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    page = execute_with_retry(_create)
    return WikiPageResponse(**page)


@router.get("/wiki/{path:path}", response_model=WikiPageResponse)
async def get_wiki_page(path: str, project_id: int = Query(...)):
    """Get a wiki page by its path."""

    def _query(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            """SELECT * FROM wiki_pages
               WHERE path = ? AND (project_id = ? OR project_id IS NULL)""",
            (path, project_id),
        ).fetchone()
        return dict(row) if row else None

    page = execute_with_retry(_query)
    if not page:
        raise WikiPageNotFound(path)
    return WikiPageResponse(**page)


@router.put("/wiki/{path:path}", response_model=WikiPageResponse)
async def update_wiki_page(path: str, body: WikiPageUpdate, project_id: int = Query(...)):
    """Update a wiki page."""

    def _update(conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT * FROM wiki_pages WHERE path = ? AND (project_id = ? OR project_id IS NULL)",
            (path, project_id),
        ).fetchone()
        if not row:
            return None

        updates = []
        params = []
        if body.title is not None:
            updates.append("title = ?")
            params.append(body.title)
        if body.content is not None:
            updates.append("content = ?")
            params.append(body.content)

        if updates:
            updates.append("updated_by = 'api'")
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(row["id"])
            conn.execute(
                f"UPDATE wiki_pages SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        row = conn.execute("SELECT * FROM wiki_pages WHERE id = ?", (row["id"],)).fetchone()
        return dict(row)

    page = execute_with_retry(_update)
    if not page:
        raise WikiPageNotFound(path)
    return WikiPageResponse(**page)


@router.delete("/wiki/{path:path}", status_code=204)
async def delete_wiki_page(path: str, project_id: int = Query(...)):
    """Delete a wiki page."""

    def _delete(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT id FROM wiki_pages WHERE path = ? AND (project_id = ? OR project_id IS NULL)",
            (path, project_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM wiki_pages WHERE id = ?", (row["id"],))
        conn.commit()
        return True

    found = execute_with_retry(_delete)
    if not found:
        raise WikiPageNotFound(path)


@router.get("/wiki-search", response_model=list[WikiSearchResult])
async def search_wiki(q: str = Query(..., min_length=1), project_id: int = Query(...)):
    """Search wiki pages using full-text search with LIKE fallback."""

    def _search(conn: sqlite3.Connection) -> list[dict]:
        # Try FTS first
        try:
            safe_q = sanitize_fts5_query(q)
            rows = conn.execute(
                """SELECT wp.path, wp.title,
                          snippet(wiki_fts, 2, '<b>', '</b>', '...', 64) AS snippet,
                          wp.updated_at
                   FROM wiki_pages wp
                   JOIN wiki_fts ON wp.id = wiki_fts.rowid
                   WHERE wiki_fts MATCH ?
                     AND (wp.project_id = ? OR wp.project_id IS NULL)
                   ORDER BY rank
                   LIMIT 20""",
                (safe_q, project_id),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            # Fallback to LIKE
            like_q = f"%{q}%"
            rows = conn.execute(
                """SELECT path, title,
                          SUBSTR(content, 1, 200) as snippet,
                          updated_at
                   FROM wiki_pages
                   WHERE (project_id = ? OR project_id IS NULL)
                     AND (title LIKE ? OR content LIKE ?)
                   ORDER BY updated_at DESC
                   LIMIT 20""",
                (project_id, like_q, like_q),
            ).fetchall()
            return [dict(r) for r in rows]

    results = execute_with_retry(_search)
    return [WikiSearchResult(**r) for r in results]
