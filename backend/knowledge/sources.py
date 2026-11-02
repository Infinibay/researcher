"""Custom CrewAI knowledge sources backed by INFINIBAY's SQLite database."""

from __future__ import annotations

import logging
import os
import sqlite3

from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource

from backend.config.settings import settings
from backend.knowledge.wiki import WikiConflict, verify_current_revision

logger = logging.getLogger(__name__)


def execute_with_retry(*args, **kwargs):
    """Defer the legacy registry import until a source loads data, after its classes are defined.

    Keep this narrow patch point for existing consumers/tests; all database behavior
    still belongs to the shared legacy helper, not a second retry implementation.
    """
    from backend.tools.base.db import execute_with_retry as execute

    return execute(*args, **kwargs)


def _chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split *text* into overlapping chunks.

    Returns the original text as a single-element list when it fits
    within *chunk_size*.
    """
    if chunk_size is None:
        chunk_size = settings.KNOWLEDGE_CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = settings.KNOWLEDGE_CHUNK_OVERLAP

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks


class FindingsKnowledgeSource(BaseKnowledgeSource):
    """Deprecated mutable-finding index: use canonical current readers and attributed feedback.

    Constructor compatibility is retained so old callers receive an actionable error.
    No finding rows, embedding model, vector collection or old cache is loaded here.
    """

    project_id: int
    min_confidence: float | None = None
    status_filter: str = "active"

    def load_content(self) -> list[dict[str, str]]:
        """Refuse unversioned finding injection instead of silently dropping unknowns or reviving old claims."""
        raise RuntimeError(
            "Mutable finding vector context is retired; use read_findings, search_findings "
            "and read_finding_reviews for scoped current records, citations and review currentness"
        )

    def validate_content(self) -> list[dict[str, str]]:
        """Return the same explicit migration failure as a direct content load."""
        return self.load_content()

    def add(self) -> None:
        """Refuse new vector writes; existing stored collections are not deleted or reused."""
        self.load_content()

    async def aadd(self) -> None:
        """Keep asynchronous obsolete callers from silently rebuilding the retired index."""
        self.add()


class WikiKnowledgeSource(BaseKnowledgeSource):
    """Legacy context includes project/global candidates, each with explicit identity; native reads select one scope."""

    project_id: int

    def load_content(self) -> list[dict[str, str]]:
        """Retain distinct namespace/id/revision evidence without inferring precedence or validation."""
        pid = self.project_id

        def _query(conn: sqlite3.Connection) -> list[dict]:
            """Label independent project/global candidates and reject unrecorded content changes."""
            rows = conn.execute(
                """SELECT id, project_id, revision, path, title, content, parent_path
                   FROM wiki_pages
                   WHERE project_id = ? OR project_id IS NULL
                   ORDER BY path""",
                (pid,),
            ).fetchall()
            pages = [dict(row) for row in rows]
            for page in pages:
                namespace = "global" if page["project_id"] is None else "project"
                verify_current_revision(conn, page, pid, namespace)
            return pages

        try:
            pages = execute_with_retry(_query)
        except WikiConflict:
            raise
        except Exception:
            logger.exception("Failed to load wiki pages for project %d", pid)
            return []

        content_chunks = []
        for page in pages:
            namespace = "global" if page["project_id"] is None else "project"
            text = (
                f"# {page['title']}\nNamespace: {namespace}\nPage ID: {page['id']}\n"
                f"Revision: {page['revision']}\nPath: {page['path']}\n\n{page['content']}"
            )
            content_chunks.append(
                {
                    "content": text,
                    "metadata": {
                        "namespace": namespace,
                        "project_id": page["project_id"],
                        "page_id": page["id"],
                        "revision": page["revision"],
                        "path": page["path"],
                        "title": page["title"],
                        "source": "wiki",
                    },
                }
            )
        return content_chunks

    def validate_content(self) -> list[dict[str, str]]:
        """Load and return wiki content."""
        return self.load_content()

    def add(self) -> None:
        """Chunk and save wiki content to the vector store."""
        content_chunks = self.load_content()
        if not content_chunks:
            return
        self.chunks = []
        for chunk in content_chunks:
            self.chunks.extend(_chunk_text(chunk["content"]))
        if self.chunks and self.storage:
            self._save_documents()

    async def aadd(self) -> None:
        """Async version — delegates to synchronous add."""
        self.add()


class ReferenceFilesKnowledgeSource(BaseKnowledgeSource):
    """Knowledge source backed by the ``reference_files`` table."""

    project_id: int

    def load_content(self) -> list[dict[str, str]]:
        """Fetch reference file metadata and read file contents from disk."""
        pid = self.project_id

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, file_name, file_path, file_type, description
                   FROM reference_files
                   WHERE project_id = ?""",
                (pid,),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            refs = execute_with_retry(_query)
        except Exception:
            logger.exception("Failed to load reference files for project %d", pid)
            return []

        content_chunks = []
        for ref in refs:
            fpath = ref.get("file_path", "")
            if not fpath or not os.path.exists(fpath):
                logger.debug("Skipping missing reference file: %s", fpath)
                continue

            try:
                file_size = os.path.getsize(fpath)
            except OSError:
                continue

            if file_size > settings.MAX_FILE_SIZE_BYTES:
                logger.debug(
                    "Skipping oversized reference file: %s (%d bytes)",
                    fpath,
                    file_size,
                )
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    file_content = f.read()
            except Exception:
                logger.debug("Failed to read reference file: %s", fpath, exc_info=True)
                continue

            description = ref.get("description", "")
            text = (
                f"File: {ref['file_name']}\n"
                f"Description: {description}\n\n"
                f"{file_content}"
            )
            content_chunks.append(
                {
                    "content": text,
                    "metadata": {
                        "file_name": ref["file_name"],
                        "file_type": ref.get("file_type", ""),
                        "description": description,
                        "source": "reference_files",
                    },
                }
            )
        return content_chunks

    def validate_content(self) -> list[dict[str, str]]:
        """Load and return reference file content."""
        return self.load_content()

    def add(self) -> None:
        """Chunk and save reference file content to the vector store."""
        content_chunks = self.load_content()
        if not content_chunks:
            return
        self.chunks = []
        for chunk in content_chunks:
            self.chunks.extend(_chunk_text(chunk["content"]))
        if self.chunks and self.storage:
            self._save_documents()

    async def aadd(self) -> None:
        """Async version — delegates to synchronous add."""
        self.add()


class ReportsKnowledgeSource(BaseKnowledgeSource):
    """Knowledge source backed by the ``artifacts`` table (type='report')."""

    project_id: int

    def load_content(self) -> list[dict[str, str]]:
        """Fetch report artifacts — prefer DB content, fall back to file."""
        pid = self.project_id

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, file_path, description, content
                   FROM artifacts
                   WHERE type = 'report' AND project_id = ?""",
                (pid,),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            reports = execute_with_retry(_query)
        except Exception:
            logger.exception("Failed to load reports for project %d", pid)
            return []

        content_chunks = []
        for report in reports:
            # Prefer content stored in DB
            file_content = report.get("content")

            # Fall back to filesystem when DB content is empty
            if not file_content:
                fpath = report.get("file_path", "")
                if not fpath or not os.path.exists(fpath):
                    logger.debug("Skipping missing report file: %s", fpath)
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        file_content = f.read()
                except Exception:
                    logger.debug("Failed to read report file: %s", fpath, exc_info=True)
                    continue

            description = report.get("description", "")
            content_chunks.append(
                {
                    "content": file_content,
                    "metadata": {
                        "artifact_id": report["id"],
                        "description": description,
                        "source": "reports",
                    },
                }
            )
        return content_chunks

    def validate_content(self) -> list[dict[str, str]]:
        """Load and return report content."""
        return self.load_content()

    def add(self) -> None:
        """Chunk and save report content to the vector store."""
        content_chunks = self.load_content()
        if not content_chunks:
            return
        self.chunks = []
        for chunk in content_chunks:
            self.chunks.extend(_chunk_text(chunk["content"]))
        if self.chunks and self.storage:
            self._save_documents()

    async def aadd(self) -> None:
        """Async version — delegates to synchronous add."""
        self.add()
