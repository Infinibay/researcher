"""Tests for the AgentLoop core functionality."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from backend.autonomy.agent_loop import AgentLoop, AgentLoopManager
from backend.autonomy.events import (
    create_system_event,
    get_event_by_id,
    load_loop_state,
    save_loop_state,
    update_event_status,
)
from backend.tests.autonomy.conftest import seed_roster, seed_task


class TestAgentLoop:
    def test_loop_picks_up_and_completes_event(self, db_conn, executing_project):
        """AgentLoop picks up a pending event and marks it completed."""
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        # Create an event that the loop will pick up
        eid = create_system_event(pid, agent_id, "message_received", {
            "from_agent": "system",
            "message": "test message",
        })

        # Mock the handler to avoid actually dispatching
        mock_handler = MagicMock()
        mock_handlers = {"message_received": mock_handler}

        loop = AgentLoop(agent_id, pid, "developer")
        loop.handlers = mock_handlers

        # Override interval for fast testing
        loop._base_interval = 0.1
        loop._current_interval = 0.1

        loop.start()
        time.sleep(1.5)  # Give the loop time to poll and execute
        loop.stop()

        # The handler should have been called
        assert mock_handler.execute.called

        # Event should be completed
        event = get_event_by_id(eid)
        assert event["status"] == "completed"

    def test_loop_crash_recovery(self, db_conn, executing_project):
        """AgentLoop recovers an in-progress event on startup."""
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        # Simulate a crash: create an in-progress event
        eid = create_system_event(pid, agent_id, "message_received", {
            "from_agent": "system",
            "message": "interrupted",
        })
        update_event_status(eid, "in_progress")
        save_loop_state(agent_id, pid, eid, "processing")

        # Create loop with mocked handler
        mock_handler = MagicMock()
        mock_handlers = {"message_received": mock_handler}

        loop = AgentLoop(agent_id, pid, "developer")
        loop.handlers = mock_handlers
        loop._base_interval = 100  # Long interval so only recovery fires

        loop.start()
        time.sleep(1.0)
        loop.stop()

        # Recovery should have called the handler
        assert mock_handler.execute.called

        # Event should be completed
        event = get_event_by_id(eid)
        assert event["status"] == "completed"

    def test_loop_marks_failed_on_handler_error(self, db_conn, executing_project):
        """AgentLoop marks event as failed when handler raises."""
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        eid = create_system_event(pid, agent_id, "message_received", {
            "from_agent": "system",
            "message": "will fail",
        })

        mock_handler = MagicMock()
        mock_handler.execute.side_effect = RuntimeError("test error")

        loop = AgentLoop(agent_id, pid, "developer")
        loop.handlers = {"message_received": mock_handler}
        loop._base_interval = 0.1
        loop._current_interval = 0.1

        loop.start()
        time.sleep(1.5)
        loop.stop()

        event = get_event_by_id(eid)
        assert event["status"] == "failed"
        assert "test error" in (event["error_message"] or "")

    def test_loop_skips_non_executing_project(self, db_conn, new_project):
        """AgentLoop does not process events for non-executing projects."""
        pid = new_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        eid = create_system_event(pid, agent_id, "task_available")

        mock_handler = MagicMock()
        loop = AgentLoop(agent_id, pid, "developer")
        loop.handlers = {"task_available": mock_handler}
        loop._base_interval = 0.1
        loop._current_interval = 0.1

        loop.start()
        time.sleep(0.5)
        loop.stop()

        # Handler should NOT have been called
        assert not mock_handler.execute.called

        # Event should still be pending
        event = get_event_by_id(eid)
        assert event["status"] == "pending"


class TestAgentLoopManager:
    def test_start_and_stop(self, db_conn, executing_project):
        """AgentLoopManager starts and stops loops for eligible agents."""
        pid = executing_project
        seed_roster(db_conn, pid, [
            (f"developer_1_p{pid}", "developer"),
            (f"team_lead_p{pid}", "team_lead"),
            (f"project_lead_p{pid}", "project_lead"),  # Not loop-eligible (no toggle)
        ])

        with patch("backend.autonomy.agent_loop.settings") as mock_settings:
            mock_settings.AUTONOMY_ENABLED = True
            mock_settings.AUTONOMY_ENABLE_DEVELOPER = True
            mock_settings.AUTONOMY_ENABLE_RESEARCHER = True
            mock_settings.AUTONOMY_ENABLE_TEAM_LEAD = True
            mock_settings.AGENT_LOOP_POLL_INTERVAL = 30.0
            mock_settings.AGENT_LOOP_MAX_IDLE_INTERVAL = 300.0
            mock_settings.AGENT_LOOP_ERROR_THRESHOLD = 5
            mock_settings.AGENT_LOOP_MAX_ACTIONS_PER_HOUR = 20

            mgr = AgentLoopManager(pid)
            mgr.start_all()

            # Should have loops for developer and team_lead
            assert len(mgr._loops) >= 2

            mgr.stop()
            assert len(mgr._loops) == 0
