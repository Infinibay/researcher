"""Custom CrewAI knowledge sources backed by PABADA's SQLite database."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Any

from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource

from backend.config.settings import settings
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


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
    """Knowledge source backed by the ``findings`` table."""

    project_id: int
    min_confidence: float = 0.0
    status_filter: str = "active"

    def load_content(self) -> list[dict[str, str]]:
        """Fetch findings from SQLite and format them as content chunks."""
        status = self.status_filter
        min_conf = self.min_confidence
        pid = self.project_id

        def _query(conn: sqlite3.Connection) -> list[dict]:
            # 'active' means any non-rejected status
            if status == "active":
                rows = conn.execute(
                    """SELECT id, topic, content, confidence, finding_type,
                              sources_json, status
                       FROM findings
                       WHERE project_id = ?
                         AND status != 'rejected'
                         AND confidence >= ?
                       ORDER BY confidence DESC""",
                    (pid, min_conf),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, topic, content, confidence, finding_type,
                              sources_json, status
                       FROM findings
                       WHERE project_id = ? AND status = ? AND confidence >= ?
                       ORDER BY confidence DESC""",
                    (pid, status, min_conf),
                ).fetchall()
            return [dict(r) for r in rows]

        try:
            findings = execute_with_retry(_query)
        except Exception:
            logger.exception("Failed to load findings for project %d", pid)
            return []

        content_chunks = []
        for f in findings:
            sources = f.get("sources_json", "[]")
            text = (
                f"[{f['finding_type']}] {f['topic']} "
                f"(confidence={f['confidence']})\n"
                f"{f['content']}\n"
                f"Sources: {sources}"
            )
            content_chunks.append({
                "content": text,
                "metadata": {
                    "finding_id": f["id"],
                    "topic": f["topic"],
                    "confidence": f["confidence"],
                    "finding_type": f["finding_type"],
                    "source": "findings",
                },
            })
        return content_chunks

    def validate_content(self) -> list[dict[str, str]]:
        """Load and return findings content."""
        return self.load_content()

    def add(self) -> None:
        """Chunk and save findings content to the vector store."""
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


class WikiKnowledgeSource(BaseKnowledgeSource):
    """Knowledge source backed by the ``wiki_pages`` table."""

    project_id: int

    def load_content(self) -> list[dict[str, str]]:
        """Fetch wiki pages and format them as content chunks."""
        pid = self.project_id

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, path, title, content
                   FROM wiki_pages
                   WHERE project_id = ? OR project_id IS NULL
                   ORDER BY path""",
                (pid,),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            pages = execute_with_retry(_query)
        except Exception:
            logger.exception("Failed to load wiki pages for project %d", pid)
            return []

        content_chunks = []
        for page in pages:
            text = f"# {page['title']}\nPath: {page['path']}\n\n{page['content']}"
            content_chunks.append({
                "content": text,
                "metadata": {
                    "path": page["path"],
                    "title": page["title"],
                    "source": "wiki",
                },
            })
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
                    fpath, file_size,
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
            content_chunks.append({
                "content": text,
                "metadata": {
                    "file_name": ref["file_name"],
                    "file_type": ref.get("file_type", ""),
                    "description": description,
                    "source": "reference_files",
                },
            })
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
        """Fetch report artifacts and read their content from disk."""
        pid = self.project_id

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT id, file_path, description
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
            content_chunks.append({
                "content": file_content,
                "metadata": {
                    "artifact_id": report["id"],
                    "description": description,
                    "source": "reports",
                },
            })
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
