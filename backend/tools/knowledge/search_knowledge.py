"""Tool for unified cross-source knowledge search using FTS5."""

import sqlite3
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., description="Full-text search query")
    sources: list[str] = Field(
        default=["findings", "wiki", "reference_files"],
        description="Sources to search: findings, wiki, reference_files",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results per source")
    min_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Minimum confidence filter (findings only)",
    )


class SearchKnowledgeTool(PabadaBaseTool):
    name: str = "search_knowledge"
    description: str = (
        "Unified search across knowledge sources (findings, wiki, reference files). "
        "Uses full-text search for fast, relevant results."
    )
    args_schema: Type[BaseModel] = SearchKnowledgeInput

    def _run(
        self,
        query: str,
        sources: list[str] | None = None,
        limit: int = 20,
        min_confidence: float = 0.0,
    ) -> str:
        if sources is None:
            sources = ["findings", "wiki", "reference_files"]

        project_id = self.project_id
        all_results: list[dict] = []

        def _search(conn: sqlite3.Connection) -> list[dict]:
            results = []

            if "findings" in sources:
                try:
                    rows = conn.execute(
                        """SELECT f.id, f.topic AS title,
                                  snippet(findings_fts, 1, '<b>', '</b>', '...', 64) AS snippet,
                                  f.confidence, f.finding_type, f.status
                           FROM findings f
                           JOIN findings_fts fts ON f.id = fts.rowid
                           WHERE fts.findings_fts MATCH ?
                             AND (f.project_id = ? OR f.project_id IS NULL)
                             AND f.confidence >= ?
                             AND f.status != 'rejected'
                           ORDER BY rank
                           LIMIT ?""",
                        (query, project_id, min_confidence, limit),
                    ).fetchall()
                    for r in rows:
                        results.append({
                            "source_type": "findings",
                            "id": r["id"],
                            "title": r["title"],
                            "snippet": r["snippet"],
                            "confidence": r["confidence"],
                            "finding_type": r["finding_type"],
                        })
                except sqlite3.OperationalError:
                    pass  # FTS table may not exist

            if "wiki" in sources:
                try:
                    rows = conn.execute(
                        """SELECT wp.id, wp.title,
                                  snippet(wiki_fts, 2, '<b>', '</b>', '...', 64) AS snippet,
                                  wp.path
                           FROM wiki_pages wp
                           JOIN wiki_fts ON wp.id = wiki_fts.rowid
                           WHERE wiki_fts MATCH ?
                             AND (wp.project_id = ? OR wp.project_id IS NULL)
                           ORDER BY rank
                           LIMIT ?""",
                        (query, project_id, limit),
                    ).fetchall()
                    for r in rows:
                        results.append({
                            "source_type": "wiki",
                            "id": r["id"],
                            "title": r["title"],
                            "snippet": r["snippet"],
                            "path": r["path"],
                        })
                except sqlite3.OperationalError:
                    pass

            if "reference_files" in sources:
                try:
                    rows = conn.execute(
                        """SELECT rf.id, rf.file_name AS title,
                                  rf.description AS snippet,
                                  rf.file_type
                           FROM reference_files rf
                           WHERE rf.project_id = ?
                             AND (rf.file_name LIKE ? OR rf.description LIKE ?)
                           LIMIT ?""",
                        (project_id, f"%{query}%", f"%{query}%", limit),
                    ).fetchall()
                    for r in rows:
                        results.append({
                            "source_type": "reference_files",
                            "id": r["id"],
                            "title": r["title"],
                            "snippet": r["snippet"] or "",
                            "file_type": r["file_type"],
                        })
                except sqlite3.OperationalError:
                    pass

            return results

        try:
            all_results = execute_with_retry(_search)
        except Exception as e:
            return self._error(f"Knowledge search failed: {e}")

        self._log_tool_usage(
            f"Searched '{query}' across {sources} — {len(all_results)} results"
        )
        return self._success({
            "query": query,
            "results": all_results,
            "count": len(all_results),
        })
