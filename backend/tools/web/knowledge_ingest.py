"""Helper for ingesting scraped web content into the PABADA knowledge system.

Stores scraped content as findings (type='observation') so it flows through
the existing FindingsKnowledgeSource → RAG pipeline without schema changes.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 50_000  # truncate scraped content to this length


def store_scraped_content_as_finding(
    project_id: int | None,
    task_id: int | None,
    agent_id: str | None,
    agent_run_id: str | None,
    url: str,
    content: str,
    topic: str = "",
) -> int | None:
    """Insert scraped web content as a finding with type='observation'.

    Args:
        project_id: Current project ID.
        task_id: Current task ID (can be None).
        agent_id: Agent performing the scrape.
        agent_run_id: Current agent run ID.
        url: Source URL.
        content: Scraped text content.
        topic: Optional topic/title for the finding.

    Returns:
        The finding ID, or None on failure.
    """
    if not content or not content.strip():
        return None

    # Truncate to reasonable size
    truncated = content[:_MAX_CONTENT_LENGTH]
    sources = json.dumps([url])
    title = topic or f"Scraped content from {url[:100]}"

    finding_id: int | None = None

    def _insert(conn: sqlite3.Connection) -> None:
        nonlocal finding_id
        cursor = conn.execute(
            """INSERT INTO findings
               (project_id, task_id, agent_id, agent_run_id,
                title, content, finding_type, confidence,
                sources_json, status)
               VALUES (?, ?, ?, ?, ?, ?, 'observation', 0.5, ?, 'provisional')""",
            (project_id, task_id, agent_id, agent_run_id,
             title, truncated, sources),
        )
        finding_id = cursor.lastrowid
        conn.commit()

    try:
        execute_with_retry(_insert)
        logger.info(
            "Stored scraped content as finding #%s from %s (%d chars)",
            finding_id, url[:60], len(truncated),
        )
        return finding_id
    except Exception:
        logger.warning("Failed to store scraped content as finding", exc_info=True)
        return None
