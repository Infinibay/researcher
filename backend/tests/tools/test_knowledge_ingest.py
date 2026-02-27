"""Tests for knowledge_ingest helper (storing scraped content as findings)."""

import json
import sqlite3

import pytest

from backend.tools.web.knowledge_ingest import store_scraped_content_as_finding


class TestStoreScrapedContent:
    def test_store_scraped_content_creates_finding(self, test_db):
        """Verify that scraped content is stored as a finding row."""
        finding_id = store_scraped_content_as_finding(
            project_id=1,
            task_id=None,
            agent_id="researcher-1",
            agent_run_id="run-1",
            url="https://example.com/article",
            content="This is scraped content about machine learning.",
            topic="ML Article",
        )

        assert finding_id is not None

        # Verify in DB
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["title"] == "ML Article"
        assert row["content"] == "This is scraped content about machine learning."
        assert row["finding_type"] == "observation"
        assert row["confidence"] == 0.5
        assert row["status"] == "provisional"
        sources = json.loads(row["sources_json"])
        assert sources == ["https://example.com/article"]

    def test_store_empty_content_returns_none(self, test_db):
        result = store_scraped_content_as_finding(
            project_id=1,
            task_id=None,
            agent_id="researcher-1",
            agent_run_id="run-1",
            url="https://example.com",
            content="",
        )
        assert result is None

    def test_store_whitespace_content_returns_none(self, test_db):
        result = store_scraped_content_as_finding(
            project_id=1,
            task_id=None,
            agent_id="researcher-1",
            agent_run_id="run-1",
            url="https://example.com",
            content="   \n\t  ",
        )
        assert result is None

    def test_content_truncation(self, test_db):
        """Content longer than 50k chars should be truncated."""
        long_content = "A" * 60_000  # 60k chars, exceeds 50k limit

        finding_id = store_scraped_content_as_finding(
            project_id=1,
            task_id=None,
            agent_id="researcher-1",
            agent_run_id="run-1",
            url="https://example.com/long",
            content=long_content,
        )

        assert finding_id is not None

        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT content FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        conn.close()

        assert len(row[0]) == 50_000

    def test_default_topic_from_url(self, test_db):
        """When no topic is provided, title should be derived from URL."""
        finding_id = store_scraped_content_as_finding(
            project_id=1,
            task_id=None,
            agent_id="researcher-1",
            agent_run_id="run-1",
            url="https://example.com/page",
            content="Some content",
        )

        conn = sqlite3.connect(test_db)
        row = conn.execute(
            "SELECT title FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        conn.close()

        assert "example.com" in row[0]
