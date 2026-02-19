"""Tests for task tools."""

import json
import sqlite3

import pytest

from backend.tools.base.context import set_context
from backend.tools.base.db import get_db_path, get_connection
from backend.tools.task import (
    AddCommentTool,
    ApproveTaskTool,
    CreateTaskTool,
    GetTaskTool,
    ReadTasksTool,
    RejectTaskTool,
    SetTaskDependenciesTool,
    TakeTaskTool,
    UpdateTaskStatusTool,
)


class TestCreateTaskTool:
    def test_create_task(self, test_db, agent_context):
        tool = CreateTaskTool()
        result = json.loads(tool._run(
            title="Test Task",
            description="A test task",
            type="code",
            priority=3,
        ))
        assert "task_id" in result
        assert result["status"] == "backlog"
        assert result["type"] == "code"

    def test_create_with_dependencies(self, test_db, agent_context):
        tool = CreateTaskTool()
        # Create first task
        r1 = json.loads(tool._run(title="Task 1", description="First", type="code"))
        task1_id = r1["task_id"]

        # Create dependent task
        r2 = json.loads(tool._run(
            title="Task 2", description="Second", type="code",
            depends_on=[task1_id],
        ))
        assert "task_id" in r2
        assert r2["dependencies"] == [task1_id]

    def test_invalid_type(self, test_db, agent_context):
        tool = CreateTaskTool()
        result = tool._run(title="Bad", description="Bad type", type="invalid")
        assert "error" in result

    def test_invalid_complexity(self, test_db, agent_context):
        tool = CreateTaskTool()
        result = tool._run(
            title="Bad", description="Bad complexity",
            type="code", complexity="impossible",
        )
        assert "error" in result


class TestTakeTaskTool:
    def test_take_backlog_task(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Take me", description="Test", type="code"))
        task_id = r["task_id"]

        take = TakeTaskTool()
        result = json.loads(take._run(task_id=task_id))
        assert result["status"] == "in_progress"
        assert result["assigned_to"] == "agent-1"

    def test_cannot_take_in_progress_task(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Taken", description="Test", type="code"))
        task_id = r["task_id"]

        take = TakeTaskTool()
        take._run(task_id=task_id)

        # Try to take again
        result = take._run(task_id=task_id)
        assert "error" in result


class TestUpdateTaskStatusTool:
    def test_valid_transition(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Progress", description="Test", type="code"))
        task_id = r["task_id"]

        # backlog -> pending
        update = UpdateTaskStatusTool()
        result = json.loads(update._run(task_id=task_id, status="pending"))
        assert result["new_status"] == "pending"

    def test_invalid_transition(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Skip", description="Test", type="code"))
        task_id = r["task_id"]

        # backlog -> done (invalid)
        update = UpdateTaskStatusTool()
        result = update._run(task_id=task_id, status="done")
        assert "error" in result
        assert "invalid transition" in result.lower()

    def test_with_comment(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Comment", description="Test", type="code"))
        task_id = r["task_id"]

        update = UpdateTaskStatusTool()
        update._run(task_id=task_id, status="pending", comment="Moving to pending")

        # Verify comment exists
        get = GetTaskTool()
        task = json.loads(get._run(task_id=task_id, include_comments=True))
        assert len(task["comments"]) > 0


class TestCodeReviewEnforcement:
    """Tests that code/bug_fix tasks require an approved code_review to reach done."""

    def _to_review_ready(self, task_id):
        update = UpdateTaskStatusTool()
        update._run(task_id=task_id, status="pending")
        update._run(task_id=task_id, status="in_progress")
        update._run(task_id=task_id, status="review_ready")

    def test_code_task_blocked_without_review(self, test_db, agent_context):
        """A code task in review_ready cannot go to done via UpdateTaskStatus without review."""
        create = CreateTaskTool()
        r = json.loads(create._run(title="Code work", description="Test", type="code"))
        task_id = r["task_id"]
        self._to_review_ready(task_id)

        update = UpdateTaskStatusTool()
        result = update._run(task_id=task_id, status="done")
        assert "error" in result
        assert "approved code review" in result.lower()

    def test_bug_fix_task_blocked_without_review(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Fix bug", description="Test", type="bug_fix"))
        task_id = r["task_id"]
        self._to_review_ready(task_id)

        update = UpdateTaskStatusTool()
        result = update._run(task_id=task_id, status="done")
        assert "error" in result
        assert "approved code review" in result.lower()

    def test_code_task_allowed_with_review(self, test_db, agent_context):
        """A code task can reach done when an approved code_review exists."""
        create = CreateTaskTool()
        r = json.loads(create._run(title="Reviewed code", description="Test", type="code"))
        task_id = r["task_id"]
        self._to_review_ready(task_id)

        # Insert an approved code_review for this task
        conn = get_connection()
        conn.execute(
            """INSERT INTO code_reviews
               (project_id, task_id, branch, agent_run_id, repo_name, status)
               VALUES (1, ?, 'feature-branch', 'run-1', '.', 'approved')""",
            (task_id,),
        )
        conn.commit()
        conn.close()

        update = UpdateTaskStatusTool()
        result = json.loads(update._run(task_id=task_id, status="done"))
        assert result["new_status"] == "done"

    def test_research_task_not_blocked(self, test_db, agent_context):
        """Non-code tasks should not require a code review."""
        create = CreateTaskTool()
        r = json.loads(create._run(title="Research work", description="Test", type="research"))
        task_id = r["task_id"]
        self._to_review_ready(task_id)

        update = UpdateTaskStatusTool()
        result = json.loads(update._run(task_id=task_id, status="done"))
        assert result["new_status"] == "done"


class TestApproveRejectTask:
    def _create_review_ready_task(self, agent_context):
        """Helper to create a task in review_ready state."""
        create = CreateTaskTool()
        r = json.loads(create._run(title="Review me", description="Test", type="code"))
        task_id = r["task_id"]

        update = UpdateTaskStatusTool()
        update._run(task_id=task_id, status="pending")
        update._run(task_id=task_id, status="in_progress")
        # need to take first then mark in_progress
        # Actually backlog->pending->in_progress->review_ready
        # Let's re-check transitions
        # backlog->pending, pending->in_progress, in_progress->review_ready

        update._run(task_id=task_id, status="review_ready")
        return task_id

    def test_approve_task(self, test_db, agent_context):
        task_id = self._create_review_ready_task(agent_context)

        approve = ApproveTaskTool()
        result = json.loads(approve._run(task_id=task_id))
        assert result["status"] == "done"

    def test_reject_task(self, test_db, agent_context):
        task_id = self._create_review_ready_task(agent_context)

        reject = RejectTaskTool()
        result = json.loads(reject._run(task_id=task_id, reason="Needs changes"))
        assert result["status"] == "rejected"
        assert result["retry_count"] == 1

    def test_cannot_approve_non_review_task(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Not ready", description="Test", type="code"))
        task_id = r["task_id"]

        approve = ApproveTaskTool()
        result = approve._run(task_id=task_id)
        assert "error" in result


class TestSetDependencies:
    def test_set_dependencies(self, test_db, agent_context):
        create = CreateTaskTool()
        r1 = json.loads(create._run(title="Task A", description="First", type="code"))
        r2 = json.loads(create._run(title="Task B", description="Second", type="code"))

        deps = SetTaskDependenciesTool()
        result = json.loads(deps._run(
            task_id=r2["task_id"], depends_on=[r1["task_id"]],
        ))
        assert result["depends_on"] == [r1["task_id"]]

    def test_self_dependency_rejected(self, test_db, agent_context):
        create = CreateTaskTool()
        r = json.loads(create._run(title="Self", description="Test", type="code"))

        deps = SetTaskDependenciesTool()
        result = deps._run(task_id=r["task_id"], depends_on=[r["task_id"]])
        assert "error" in result

    def test_cycle_detection(self, test_db, agent_context):
        create = CreateTaskTool()
        r1 = json.loads(create._run(title="A", description="Test", type="code"))
        r2 = json.loads(create._run(title="B", description="Test", type="code"))

        deps = SetTaskDependenciesTool()
        # A depends on B
        deps._run(task_id=r1["task_id"], depends_on=[r2["task_id"]])
        # B depends on A (cycle!)
        result = deps._run(task_id=r2["task_id"], depends_on=[r1["task_id"]])
        assert "error" in result
        assert "cycle" in result.lower()


class TestReadTasks:
    def test_read_all(self, test_db, agent_context):
        create = CreateTaskTool()
        create._run(title="Task 1", description="Test", type="code")
        create._run(title="Task 2", description="Test", type="research")

        read = ReadTasksTool()
        result = json.loads(read._run())
        assert result["count"] == 2

    def test_filter_by_type(self, test_db, agent_context):
        create = CreateTaskTool()
        create._run(title="Code Task", description="Test", type="code")
        create._run(title="Research Task", description="Test", type="research")

        read = ReadTasksTool()
        result = json.loads(read._run(type="code"))
        assert result["count"] == 1
        assert result["tasks"][0]["type"] == "code"
