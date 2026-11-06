"""Cross-source lexical projection with explicit project scope, cursors and partial coverage.

Each result is a bounded preview. Finding assessments share the canonical registry;
no vector index, document acquisition or inference is invoked by this reader.
"""

import sqlite3
from contextlib import closing, contextmanager

from backend.db.connection import connect
from backend.knowledge.findings import list_findings
from backend.research.models import ResearchInputError, bounded_text, positive_id
from backend.tools.base.db import sanitize_fts5_query

SOURCES = {"findings", "wiki", "reference_files", "reports"}
READ_FAILURES = (ValueError, LookupError, RuntimeError, OSError, sqlite3.Error)


def select_sources(sources):
    """Validate a complete requested source set before authorization or any database reads."""
    selected = (
        ["findings", "wiki", "reference_files", "reports"]
        if sources is None
        else sources
    )
    if (
        not isinstance(selected, list)
        or not selected
        or len(selected) != len(set(selected))
        or not set(selected) <= SOURCES
    ):
        raise ResearchInputError("Choose distinct supported knowledge sources")
    return selected


class KnowledgeSearchStore:
    """Own a read-only source snapshot while disclosing unavailable coverage separately from absence."""

    def __init__(self, database):
        """Bind the existing serving database selected by the authorized composition boundary."""
        self.database = str(database)

    @contextmanager
    def _transaction(self):
        """Keep every selected source count, cursor and preview in one read-only SQL snapshot."""
        with closing(connect(self.database, existing_only=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            yield conn

    def query(self, project, query, **selection):
        """Keep the owner reader's original database binding while sharing the authenticated snapshot implementation."""
        with self._transaction() as conn:
            return self.query_snapshot(conn, project, query, **selection)

    @staticmethod
    def query_snapshot(
        conn,
        project,
        query,
        *,
        sources=None,
        limit=20,
        min_confidence=None,
        namespace="project",
        cursors=None,
    ):
        """Search only explicit scope and preserve each requested source's complete/failed coverage."""
        positive_id(project)
        bounded_text(query, "knowledge lexical query", 1000)
        selected = select_sources(sources)
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or namespace not in ("project", "global")
        ):
            raise ResearchInputError("Invalid knowledge page or wiki namespace")
        positions = {} if cursors is None else cursors
        if (
            not isinstance(positions, dict)
            or not set(positions) <= set(selected)
            or any(type(value) is not int or value < 0 for value in positions.values())
        ):
            raise ResearchInputError(
                "Knowledge cursors must be nonnegative ids for selected sources"
            )
        expression = sanitize_fts5_query(query)
        if expression == '""':
            raise ResearchInputError("Knowledge query contains no searchable words")
        results = []
        coverage = {}
        for source in selected:
            after = positions.get(source, 0)
            try:
                if source == "findings":
                    page = list_findings(
                        conn,
                        project,
                        query=query,
                        min_confidence=min_confidence,
                        after_id=after,
                        limit=limit,
                    )
                    rows = [
                        {
                            **item,
                            "source_type": "findings",
                            "title": item["topic"],
                            "snippet": item["content_excerpt"],
                            "snippet_scope": "bounded current claim preview, not complete claim or captured evidence",
                        }
                        for item in page["items"]
                    ]
                    total = page["total_matching"]
                    following = page["next_after_id"]
                else:
                    rows, total, following = KnowledgeSearchStore._source_page(
                        conn,
                        source,
                        project,
                        namespace,
                        expression,
                        after,
                        limit,
                    )
                results.extend(rows)
                coverage[source] = {
                    "status": "searched",
                    "returned": len(rows),
                    "total_matching": total,
                    "next_after_id": following,
                }
            except READ_FAILURES as exc:
                coverage[source] = {
                    "status": "failed",
                    "error": str(exc)[:600],
                    "returned": 0,
                    "total_matching": None,
                    "next_after_id": None,
                }
        partial = any(item["status"] == "failed" for item in coverage.values())
        result = {
            "project_id": project,
            "query": query,
            "results": results,
            "count": len(results),
            "coverage": coverage,
            "partial": partial,
            "scientific_confidence": None,
        }
        if all(item["status"] == "failed" for item in coverage.values()):
            result["error"] = (
                "No requested knowledge source could be searched; inspect coverage instead of inferring absence"
            )
        return result

    @staticmethod
    def _source_page(conn, source, project, namespace, expression, after, limit):
        """Disclose exact source identity and preview scope without silently broadening namespaces."""
        if source == "wiki":
            clause = (
                "wp.project_id=?" if namespace == "project" else "wp.project_id IS NULL"
            )
            params = [expression, project] if namespace == "project" else [expression]
            base = f"FROM wiki_pages wp JOIN wiki_fts ON wp.id=wiki_fts.rowid WHERE wiki_fts MATCH ? AND {clause}"
            fields = "wp.id,wp.project_id,substr(wp.title,1,1200) AS title,substr(wp.path,1,512) AS path,wp.revision,substr(wp.content,1,240) AS snippet"
            alias = "wp"
            scope = "wiki text preview; read exact namespace/id/revision before reuse"
        elif source == "reference_files":
            base = "FROM reference_files rf JOIN reference_files_fts ON rf.id=reference_files_fts.rowid WHERE reference_files_fts MATCH ? AND rf.project_id=?"
            fields = "rf.id,rf.project_id,substr(rf.file_name,1,1200) AS title,substr(rf.file_type,1,128) AS file_type,substr(rf.description,1,240) AS snippet"
            params = [expression, project]
            alias = "rf"
            scope = (
                "attachment metadata only; file content was not searched or captured"
            )
        else:
            base = "FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id JOIN artifacts_fts ON a.id=artifacts_fts.rowid WHERE artifacts_fts MATCH ? AND a.type='report' AND a.project_id=?"
            fields = "a.id,a.project_id,substr(coalesce(r.title,a.file_path),1,1200) AS title,substr(a.content,1,240) AS snippet,r.status"
            params = [expression, project]
            alias = "a"
            scope = "saved report text preview; draft or publication status does not certify its claims"
        total = conn.execute("SELECT count(*) " + base, params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {fields} {base} AND {alias}.id>? ORDER BY {alias}.id LIMIT ?",
            (*params, after, limit + 1),
        ).fetchall()
        shown = [
            {
                **dict(row),
                "source_type": source,
                "snippet_scope": scope,
                **({"namespace": namespace} if source == "wiki" else {}),
            }
            for row in rows[:limit]
        ]
        return shown, total, shown[-1]["id"] if len(rows) > limit else None
