"""Tests for knowledge tools."""

import json
import sqlite3
from contextlib import closing

from backend.tools.base.context import set_context
from backend.tools.knowledge import (
    ReadWikiTool,
    RecordFindingTool,
    RejectFindingTool,
    ValidateFindingTool,
    WriteWikiTool,
)


def _seed_research_task(database):
    """Create historical fixture data directly without depending on a retired task tool."""
    with closing(sqlite3.connect(database)) as conn, conn:
        return conn.execute(
            "INSERT INTO tasks(project_id,type,title,description,status,created_by) VALUES(1,'research','Research','Test','backlog','agent-1')"
        ).lastrowid


class TestRecordFindingTool:
    """Characterize legacy provisional finding/category/task constraints, not scientific validity."""

    def test_record_finding(self, test_db, agent_context):
        """A legacy finding retains caller confidence but begins provisional; native review remains separate."""
        set_context(task_id=_seed_research_task(test_db))

        tool = RecordFindingTool()
        result = json.loads(
            tool._run(
                title="Test Finding",
                content="We found that X is true.",
                confidence=0.8,
                finding_type="observation",
            )
        )
        assert "finding_id" in result
        assert result["status"] == "provisional"
        assert result["confidence"] == 0.8

    def test_invalid_finding_type(self, test_db, agent_context):
        """Reject an unsupported category before pretending a research record was accepted."""
        set_context(task_id=1)
        tool = RecordFindingTool()
        result = tool._run(
            title="Bad",
            content="Bad type",
            confidence=0.5,
            finding_type="invalid",
        )
        assert "error" in result

    def test_requires_task_context(self, test_db, agent_context):
        """A missing legacy task binding cannot create an apparently attributed finding."""
        set_context(task_id=None)
        tool = RecordFindingTool()
        result = tool._run(
            title="No task",
            content="Test",
            confidence=0.5,
        )
        assert "error" in result


class TestValidateRejectFinding:
    """Retained legacy review flags are compatibility behavior, not proof of independent review."""

    def _create_finding(self, test_db, agent_context):
        """Bind a real fixture task and persist the provisional candidate used by review adapters."""
        set_context(task_id=_seed_research_task(test_db))

        tool = RecordFindingTool()
        result = json.loads(
            tool._run(
                title="Finding",
                content="Content",
                confidence=0.7,
            )
        )
        return result["finding_id"]

    def test_validate_finding(self, test_db, agent_context):
        """Record the old active transition with a named method; independence/quality are not tested here."""
        finding_id = self._create_finding(test_db, agent_context)

        tool = ValidateFindingTool()
        result = json.loads(
            tool._run(
                finding_id=finding_id,
                validation_method="peer_review",
                reproducibility_score=0.9,
            )
        )
        assert result["status"] == "active"

    def test_reject_finding(self, test_db, agent_context):
        """Preserve the legacy superseded transition and its explicit rejection reason."""
        finding_id = self._create_finding(test_db, agent_context)

        tool = RejectFindingTool()
        result = json.loads(
            tool._run(
                finding_id=finding_id,
                reason="Insufficient evidence",
            )
        )
        assert result["status"] == "superseded"


class TestWikiTools:
    """Legacy wiki callers use the shared recorded identity/revision contract."""

    def test_write_and_read_wiki(self, test_db, agent_context):
        """Round-trip a project wiki through shared recorded storage and its exact logical path."""
        write = WriteWikiTool()
        result = json.loads(
            write._run(
                page="architecture/overview",
                content="# Architecture Overview\nThis is the overview.",
                title="Architecture Overview",
            )
        )
        assert result["action"] == "created"

        read = ReadWikiTool()
        page = json.loads(read._run(page="architecture/overview"))
        assert "Architecture Overview" in page["content"]

    def test_update_wiki_page(self, test_db, agent_context):
        """An edit names the page and revision actually read, instead of an unguarded path overwrite."""
        write = WriteWikiTool()
        first = json.loads(write._run(page="test/page", content="V1"))
        observed = json.loads(ReadWikiTool()._run(page="test/page"))
        result = json.loads(
            write._run(
                page="test/page",
                content="V2",
                page_id=observed["id"],
                expected_revision=observed["revision"],
                operation_key="wiki-v2",
            )
        )
        assert result["page_id"] == first["page_id"]
        assert result["action"] == "updated"

    def test_wiki_index(self, test_db, agent_context):
        write = WriteWikiTool()
        write._run(page="page-a", content="A")
        write._run(page="page-b", content="B")

        read = ReadWikiTool()
        result = json.loads(read._run())
        assert result["count"] >= 2

    def test_wiki_not_found(self, test_db, agent_context):
        read = ReadWikiTool()
        result = read._run(page="nonexistent/page")
        assert "error" in result
