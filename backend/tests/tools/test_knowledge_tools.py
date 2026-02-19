"""Tests for knowledge tools."""

import json

import pytest

from backend.tools.base.context import set_context
from backend.tools.knowledge import (
    ReadFindingsTool,
    RecordFindingTool,
    RejectFindingTool,
    ValidateFindingTool,
    ReadWikiTool,
    WriteWikiTool,
)
from backend.tools.task import CreateTaskTool


class TestRecordFindingTool:
    def test_record_finding(self, test_db, agent_context):
        # Create a task first (findings need a task_id)
        create_task = CreateTaskTool()
        r = json.loads(create_task._run(
            title="Research task", description="Test", type="research",
        ))
        set_context(task_id=r["task_id"])

        tool = RecordFindingTool()
        result = json.loads(tool._run(
            title="Test Finding",
            content="We found that X is true.",
            confidence=0.8,
            finding_type="observation",
        ))
        assert "finding_id" in result
        assert result["status"] == "provisional"
        assert result["confidence"] == 0.8

    def test_invalid_finding_type(self, test_db, agent_context):
        set_context(task_id=1)
        tool = RecordFindingTool()
        result = tool._run(
            title="Bad", content="Bad type",
            confidence=0.5, finding_type="invalid",
        )
        assert "error" in result

    def test_requires_task_context(self, test_db, agent_context):
        set_context(task_id=None)
        tool = RecordFindingTool()
        result = tool._run(
            title="No task", content="Test", confidence=0.5,
        )
        assert "error" in result


class TestValidateRejectFinding:
    def _create_finding(self, test_db, agent_context):
        create_task = CreateTaskTool()
        r = json.loads(create_task._run(
            title="Research", description="Test", type="research",
        ))
        set_context(task_id=r["task_id"])

        tool = RecordFindingTool()
        result = json.loads(tool._run(
            title="Finding", content="Content", confidence=0.7,
        ))
        return result["finding_id"]

    def test_validate_finding(self, test_db, agent_context):
        finding_id = self._create_finding(test_db, agent_context)

        tool = ValidateFindingTool()
        result = json.loads(tool._run(
            finding_id=finding_id,
            validation_method="peer_review",
            reproducibility_score=0.9,
        ))
        assert result["status"] == "active"

    def test_reject_finding(self, test_db, agent_context):
        finding_id = self._create_finding(test_db, agent_context)

        tool = RejectFindingTool()
        result = json.loads(tool._run(
            finding_id=finding_id,
            reason="Insufficient evidence",
        ))
        assert result["status"] == "superseded"


class TestWikiTools:
    def test_write_and_read_wiki(self, test_db, agent_context):
        write = WriteWikiTool()
        result = json.loads(write._run(
            page="architecture/overview",
            content="# Architecture Overview\nThis is the overview.",
            title="Architecture Overview",
        ))
        assert result["action"] == "created"

        read = ReadWikiTool()
        page = json.loads(read._run(page="architecture/overview"))
        assert "Architecture Overview" in page["content"]

    def test_update_wiki_page(self, test_db, agent_context):
        write = WriteWikiTool()
        write._run(page="test/page", content="V1")
        result = json.loads(write._run(page="test/page", content="V2"))
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
