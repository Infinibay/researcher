"""Integration tests exercising complete lifecycle paths through the tool layer.

These tests use real DB and tool implementations — no LLM calls.
Each test creates its own project and epic within the test body via
helper functions and tools, covering the full create-project ->
create-epic -> tasks -> development/review/done path.
"""

import json
import sqlite3

import pytest

from backend.communication.service import CommunicationService
from backend.flows.helpers import create_project
from backend.state.completion import CompletionDetector, CompletionState
from backend.state.dependency_validator import DependencyValidator
from backend.tools.base.context import set_context
from backend.tools.base.db import execute_with_retry
from backend.tools.communication.read_messages import ReadMessagesTool
from backend.tools.communication.send_message import SendMessageTool
from backend.tools.knowledge.record_finding import RecordFindingTool
from backend.tools.knowledge.validate_finding import ValidateFindingTool
from backend.tools.project.create_epic import CreateEpicTool
from backend.tools.task.create_task import CreateTaskTool
from backend.tools.task.reject_task import RejectTaskTool
from backend.tools.task.set_dependencies import SetTaskDependenciesTool
from backend.tools.task.take_task import TakeTaskTool
from backend.tools.task.update_status import UpdateTaskStatusTool


# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_tool_result(result: str) -> dict:
    """Parse the JSON tool result string."""
    return json.loads(result)


def _get_task_row(db_conn: sqlite3.Connection, task_id: int) -> dict:
    row = db_conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else {}


def _seed_roster():
    """Insert roster agents into the DB."""
    def _insert(conn):
        conn.execute(
            """INSERT OR IGNORE INTO roster (agent_id, name, role, status)
               VALUES ('agent-1', 'Developer', 'developer', 'active')"""
        )
        conn.execute(
            """INSERT OR IGNORE INTO roster (agent_id, name, role, status)
               VALUES ('lead-1', 'Team Lead', 'team_lead', 'active')"""
        )
        conn.commit()
    execute_with_retry(_insert)


def _create_project_and_epic():
    """Create a project and epic via the helper/tool layer.

    Returns (project_id, epic_id).
    """
    # Create project via flows helper (the same path the API uses)
    project_id = create_project(
        name="Integration Test Project",
        description="Created within the integration test",
    )

    # Seed roster so agent tools can operate
    _seed_roster()

    # Set context to the new project so CreateEpicTool can use it
    set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

    # Create epic via the tool layer
    epic_tool = CreateEpicTool()
    result = epic_tool._run(
        title="Integration Epic",
        description="Epic created in the integration test",
        priority=1,
    )
    parsed = _parse_tool_result(result)
    assert parsed.get("status") == "success", f"Failed to create epic: {result}"
    epic_id = parsed["data"]["epic_id"]

    return project_id, epic_id


# ── Test: Development Lifecycle ────────────────────────────────────────────


class TestDevelopmentLifecycle:
    def test_development_lifecycle(self, _isolated_db, db_conn):
        # Create project and epic within the test
        project_id, epic_id = _create_project_and_epic()

        # Set agent context on the created project
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

        # 1. Create task under the epic
        create_tool = CreateTaskTool()
        result = create_tool._run(
            title="Build login page",
            description="Create a login page with email/password",
            type="code",
            epic_id=epic_id,
        )
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"
        task_id = parsed["data"]["task_id"]

        task = _get_task_row(db_conn, task_id)
        assert task["status"] == "backlog"
        assert task["project_id"] == project_id

        # 2. Move to pending
        update_tool = UpdateTaskStatusTool()
        result = update_tool._run(task_id=task_id, status="pending")
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        # 3. Take task (moves to in_progress)
        take_tool = TakeTaskTool()
        result = take_tool._run(task_id=task_id)
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        task = _get_task_row(db_conn, task_id)
        assert task["status"] == "in_progress"
        assert task["assigned_to"] == "agent-1"

        # 4. Move to review_ready
        result = update_tool._run(task_id=task_id, status="review_ready")
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        # 5. Insert approved code_review directly
        db_conn.execute(
            """INSERT INTO code_reviews
               (project_id, task_id, branch_name, reviewer, status, created_at)
               VALUES (?, ?, 'feature/login', 'reviewer-1', 'approved', CURRENT_TIMESTAMP)""",
            (project_id, task_id),
        )
        db_conn.commit()

        # 6. Move to done
        result = update_tool._run(task_id=task_id, status="done")
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        # 7. Check completion state
        state = CompletionDetector.detect(project_id=project_id)
        assert state == CompletionState.IDLE_OBJECTIVES_PENDING

        # 8. Verify final task state
        task = _get_task_row(db_conn, task_id)
        assert task["status"] == "done"
        assert task["completed_at"] is not None

        # Cleanup context
        set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


# ── Test: Research Lifecycle ───────────────────────────────────────────────


class TestResearchLifecycle:
    def test_research_lifecycle(self, _isolated_db, db_conn):
        project_id, epic_id = _create_project_and_epic()
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

        # 1. Create research task
        create_tool = CreateTaskTool()
        result = create_tool._run(
            title="Research auth patterns",
            description="Survey authentication patterns",
            type="research",
            epic_id=epic_id,
        )
        parsed = _parse_tool_result(result)
        task_id = parsed["data"]["task_id"]

        # 2. Take task
        take_tool = TakeTaskTool()
        take_tool._run(task_id=task_id)

        task = _get_task_row(db_conn, task_id)
        assert task["status"] == "in_progress"

        # 3. Record a finding
        record_tool = RecordFindingTool()
        result = record_tool._run(
            title="OAuth2 best practices",
            content="OAuth2 with PKCE is recommended for SPAs",
            confidence=0.8,
            finding_type="observation",
        )
        finding_result = _parse_tool_result(result)
        assert finding_result.get("status") == "success"
        finding_id = finding_result["data"]["finding_id"]

        # 4. Validate finding
        validate_tool = ValidateFindingTool()
        result = validate_tool._run(
            finding_id=finding_id,
            validation_method="literature_review",
            reproducibility_score=0.9,
        )
        validate_result = _parse_tool_result(result)
        assert validate_result.get("status") == "success"

        # 5. Move to review_ready
        update_tool = UpdateTaskStatusTool()
        update_tool._run(task_id=task_id, status="review_ready")

        # 6. Move to done (no code review required for research)
        result = update_tool._run(task_id=task_id, status="done")
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        # 7. Completion state
        state = CompletionDetector.detect(project_id=project_id)
        assert state == CompletionState.IDLE_OBJECTIVES_PENDING

        set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


# ── Test: Rejection and Retry ──────────────────────────────────────────────


class TestRejectionAndRetryLifecycle:
    def test_rejection_and_retry(self, _isolated_db, db_conn):
        project_id, epic_id = _create_project_and_epic()
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

        create_tool = CreateTaskTool()
        update_tool = UpdateTaskStatusTool()
        take_tool = TakeTaskTool()

        # 1. Create code task
        result = create_tool._run(
            title="Build API endpoint",
            description="REST endpoint",
            type="code",
            epic_id=epic_id,
        )
        task_id = _parse_tool_result(result)["data"]["task_id"]

        # 2. Take task
        take_tool._run(task_id=task_id)

        # 3. Move to review_ready
        update_tool._run(task_id=task_id, status="review_ready")

        # 4. Reject the task
        reject_tool = RejectTaskTool()
        result = reject_tool._run(task_id=task_id, reason="Missing error handling")
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        task = _get_task_row(db_conn, task_id)
        assert task["status"] == "rejected"
        assert task["retry_count"] == 1

        # 5. Re-open after rejection (rejected -> in_progress)
        result = update_tool._run(task_id=task_id, status="in_progress")
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        # 6. Move to review_ready again
        update_tool._run(task_id=task_id, status="review_ready")

        # 7. Insert approved code review
        db_conn.execute(
            """INSERT INTO code_reviews
               (project_id, task_id, branch_name, reviewer, status, created_at)
               VALUES (?, ?, 'feature/api', 'reviewer-1', 'approved', CURRENT_TIMESTAMP)""",
            (project_id, task_id),
        )
        db_conn.commit()

        # 8. Move to done
        result = update_tool._run(task_id=task_id, status="done")
        assert _parse_tool_result(result).get("status") == "success"

        task = _get_task_row(db_conn, task_id)
        assert task["status"] == "done"

        set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


# ── Test: Dependency Blocks Task ───────────────────────────────────────────


class TestDependencyBlocksTask:
    def test_dependency_blocks_task(self, _isolated_db, db_conn):
        project_id, epic_id = _create_project_and_epic()
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

        create_tool = CreateTaskTool()
        update_tool = UpdateTaskStatusTool()

        # 1. Create task A and task B
        result_a = create_tool._run(title="Task A", description="First task", type="code", epic_id=epic_id)
        task_a = _parse_tool_result(result_a)["data"]["task_id"]

        result_b = create_tool._run(title="Task B", description="Second task", type="code", epic_id=epic_id)
        task_b = _parse_tool_result(result_b)["data"]["task_id"]

        # 2. Set dependency: B depends on A
        dep_tool = SetTaskDependenciesTool()
        dep_tool._run(task_id=task_b, depends_on=[task_a], dependency_type="blocks")

        # 3. B cannot start yet
        assert DependencyValidator.can_start(task_b) is False

        # 4. Complete A
        update_tool._run(task_id=task_a, status="pending")
        take_tool = TakeTaskTool()
        take_tool._run(task_id=task_a)
        update_tool._run(task_id=task_a, status="review_ready")
        update_tool._run(task_id=task_a, status="done")

        # 5. Now B can start
        assert DependencyValidator.can_start(task_b) is True

        set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


# ── Test: Communication During Lifecycle ───────────────────────────────────


class TestCommunicationDuringLifecycle:
    def test_communication_during_lifecycle(self, _isolated_db, db_conn):
        project_id, epic_id = _create_project_and_epic()
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

        send_tool = SendMessageTool()
        read_tool = ReadMessagesTool()

        # 1. Developer sends message to team lead
        result = send_tool._run(
            message="Starting task X",
            to_agent="lead-1",
        )
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"

        # 2. Switch to lead context and read messages
        set_context(project_id=project_id, agent_id="lead-1", agent_run_id="run-2", task_id=None)
        result = read_tool._run(unread_only=True)
        parsed = _parse_tool_result(result)
        assert parsed.get("status") == "success"
        messages = parsed.get("data", {}).get("messages", [])
        assert any("Starting task X" in m.get("message", "") for m in messages)

        # 3. Lead replies to developer
        result = send_tool._run(
            message="Proceed",
            to_agent="agent-1",
        )
        assert _parse_tool_result(result).get("status") == "success"

        # 4. Switch back to developer context and read
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)
        result = read_tool._run(unread_only=True)
        parsed = _parse_tool_result(result)
        messages = parsed.get("data", {}).get("messages", [])
        assert any("Proceed" in m.get("message", "") for m in messages)

        # 5. Verify unread count is 0 after reading
        comms = CommunicationService()
        count = comms.get_unread_count(project_id=project_id, agent_id="agent-1")
        assert count == 0

        set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


# ── Test: All Tasks Done Triggers Completion ───────────────────────────────


class TestAllTasksDoneTriggerCompletion:
    def test_all_tasks_done_triggers_completion(self, _isolated_db, db_conn):
        project_id, epic_id = _create_project_and_epic()
        set_context(project_id=project_id, agent_id="agent-1", agent_run_id="run-1", task_id=None)

        create_tool = CreateTaskTool()
        update_tool = UpdateTaskStatusTool()
        take_tool = TakeTaskTool()

        # 1. Create 2 tasks
        result1 = create_tool._run(title="Task 1", description="First", type="code", epic_id=epic_id)
        task1 = _parse_tool_result(result1)["data"]["task_id"]

        result2 = create_tool._run(title="Task 2", description="Second", type="code", epic_id=epic_id)
        task2 = _parse_tool_result(result2)["data"]["task_id"]

        # Complete both tasks
        for tid in [task1, task2]:
            update_tool._run(task_id=tid, status="pending")
            take_tool._run(task_id=tid)
            update_tool._run(task_id=tid, status="review_ready")
            update_tool._run(task_id=tid, status="done")

        # 2. Completion state with open epics
        state = CompletionDetector.detect(project_id=project_id)
        assert state == CompletionState.IDLE_OBJECTIVES_PENDING

        # 3. Complete all epics
        db_conn.execute("UPDATE epics SET status = 'completed' WHERE project_id = ?", (project_id,))
        db_conn.commit()

        # 4. Completion state with completed epics
        state = CompletionDetector.detect(project_id=project_id)
        assert state == CompletionState.IDLE_OBJECTIVES_MET

        set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)
