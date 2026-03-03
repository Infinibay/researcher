"""Tests for BrainstormingFlow."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from backend.flows.helpers import calculate_time_elapsed, format_ideas, parse_ideas
from backend.flows.state_models import BrainstormPhase, BrainstormState
from backend.tests.flows.conftest import make_mock_agent


class TestBrainstormState:
    """Test BrainstormState model."""

    def test_default_state(self):
        state = BrainstormState()
        assert state.phase == BrainstormPhase.BRAINSTORM
        assert state.time_limit_brainstorm == 900
        assert state.time_limit_decision == 300
        assert state.ideas == []
        assert state.user_approved is False

    def test_state_with_values(self):
        state = BrainstormState(
            project_id=1,
            participants=["team_lead", "developer"],
            time_limit_brainstorm=600,
        )
        assert len(state.participants) == 2
        assert state.time_limit_brainstorm == 600


class TestParseIdeas:
    """Test idea parsing from agent output."""

    def test_parse_numbered_ideas(self):
        text = """1. Feature A: Implement user authentication
2. Feature B: Add dashboard analytics
3. Feature C: Create API documentation"""

        ideas = parse_ideas(text)
        assert len(ideas) == 3
        assert ideas[0]["title"] == "Feature A"
        assert "authentication" in ideas[0]["description"]

    def test_parse_dash_ideas(self):
        text = """- Caching layer: Add Redis caching for API responses
- Rate limiting: Implement rate limiting middleware"""

        ideas = parse_ideas(text)
        assert len(ideas) == 2
        assert ideas[0]["title"] == "Caching layer"

    def test_parse_empty_input(self):
        ideas = parse_ideas("")
        assert ideas == []

    def test_parse_single_idea(self):
        text = "1. Database optimization: Add indexes to frequently queried columns"
        ideas = parse_ideas(text)
        assert len(ideas) == 1
        assert ideas[0]["title"] == "Database optimization"


class TestCalculateTimeElapsed:
    """Test time elapsed calculation."""

    def test_recent_time(self):
        start = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        elapsed = calculate_time_elapsed(start)
        assert 29 <= elapsed <= 32

    def test_empty_start(self):
        elapsed = calculate_time_elapsed("")
        assert elapsed == 0.0

    def test_long_elapsed(self):
        start = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        elapsed = calculate_time_elapsed(start)
        assert 1199 <= elapsed <= 1201


class TestBrainstormingFlowStart:
    """Test session start."""

    @patch("backend.communication.thread_manager.ThreadManager")
    @patch("backend.flows.brainstorming_flow.log_flow_event")
    def test_start_session(self, mock_log, mock_tm_cls):
        mock_tm_cls.return_value.create_thread.return_value = "test-thread-id"

        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1

        result = flow.start_session()
        # start_session no longer returns a routing string (routing is done by brainstorm_phase router)
        assert result is None
        assert len(flow.state.participants) == 3
        assert flow.state.start_time != ""
        assert flow.state.phase == BrainstormPhase.BRAINSTORM
        assert flow.state.thread_id == "test-thread-id"
        mock_tm_cls.return_value.create_thread.assert_called_once_with(
            project_id=1,
            thread_type="brainstorming",
            participants=["team_lead", "developer", "researcher"],
        )


class TestBrainstormingFlowConsolidation:
    """Test idea consolidation."""

    @patch("backend.flows.brainstorming_flow.run_agent_task")
    @patch("backend.flows.brainstorming_flow.get_agent_by_role")
    @patch("backend.flows.brainstorming_flow.log_flow_event")
    def test_consolidate_ideas(self, mock_log, mock_agent, mock_run):
        mock_agent.return_value = make_mock_agent("team_lead")
        mock_run.return_value = (
            "1. Combined Feature: Merged auth and security features\n"
            "2. Analytics: Dashboard and reporting combined"
        )

        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1
        flow.state.ideas = [
            {"title": "Auth", "description": "Add authentication"},
            {"title": "Security", "description": "Add security features"},
            {"title": "Dashboard", "description": "Add analytics dashboard"},
        ]

        result = flow.consolidate_ideas()
        # consolidate_ideas is a non-router listener — no routing return value
        assert result is None
        assert flow.state.phase == BrainstormPhase.CONSOLIDATION
        assert len(flow.state.consolidated_ideas) > 0


class TestBrainstormingFlowUserDecision:
    """Test user presentation and decision routing."""

    @patch("backend.flows.brainstorming_flow.log_flow_event")
    @patch("backend.flows.brainstorming_flow.run_agent_task")
    @patch("backend.flows.brainstorming_flow.get_agent_by_role")
    def test_present_to_user_approved(self, mock_agent, mock_run, mock_log):
        mock_agent.return_value = make_mock_agent("project_lead")
        mock_run.return_value = "APPROVED"

        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1
        flow.state.selected_ideas = [{"title": "Feature A", "description": "Do A"}]

        result = flow.present_to_user()
        assert result == "approved"
        assert flow.state.user_approved is True

    @patch("backend.flows.brainstorming_flow.log_flow_event")
    @patch("backend.flows.brainstorming_flow.run_agent_task")
    @patch("backend.flows.brainstorming_flow.get_agent_by_role")
    def test_present_to_user_rejected(self, mock_agent, mock_run, mock_log):
        mock_agent.return_value = make_mock_agent("project_lead")
        mock_run.return_value = "REJECTED: Need more innovative ideas"

        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1
        flow.state.selected_ideas = [{"title": "Feature A", "description": "Do A"}]

        result = flow.present_to_user()
        assert result == "rejected"
        assert flow.state.user_approved is False
        assert "innovative" in flow.state.user_feedback


class TestBrainstormingFlowRejection:
    """Test rejection and restart."""

    @patch("backend.flows.brainstorming_flow.log_flow_event")
    def test_reset_for_new_round(self, mock_log):
        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1
        flow.state.ideas = [{"title": "A", "description": "Desc"}]
        flow.state.consolidated_ideas = [{"title": "B", "description": "Desc"}]
        flow.state.selected_ideas = [{"title": "C", "description": "Desc"}]
        flow.state.round_count = 3
        flow.state.user_feedback = "Not innovative enough"

        result = flow.reset_for_new_round()
        # reset_for_new_round is a non-router listener — no routing return value
        assert result is None
        assert flow.state.ideas == []
        assert flow.state.consolidated_ideas == []
        assert flow.state.selected_ideas == []
        assert flow.state.round_count == 0
        assert flow.state.phase == BrainstormPhase.BRAINSTORM


class TestFormatIdeas:
    """Test format_ideas helper."""

    def test_numbered(self):
        ideas = [
            {"title": "Auth", "description": "Add auth"},
            {"title": "API", "description": "Build API"},
        ]
        result = format_ideas(ideas)
        assert result == "1. Auth: Add auth\n2. API: Build API"

    def test_unnumbered(self):
        ideas = [{"title": "Cache", "description": "Add caching"}]
        result = format_ideas(ideas, numbered=False)
        assert result == "- Cache: Add caching"

    def test_with_attribution(self):
        ideas = [
            {"title": "Idea", "description": "Desc", "proposed_by": "developer"},
        ]
        result = format_ideas(ideas, numbered=False, include_attribution=True)
        assert result == "- [developer] Idea: Desc"

    def test_missing_fields(self):
        ideas = [{}]
        result = format_ideas(ideas)
        assert result == "1. Untitled: "

    def test_empty_list(self):
        assert format_ideas([]) == ""


class TestRunAgentTask:
    """Test run_agent_task helper."""

    @patch("backend.engine.get_engine")
    def test_basic_invocation(self, mock_get_engine):
        from backend.flows.helpers import run_agent_task
        from backend.tests.flows.conftest import make_mock_agent, make_mock_engine

        agent = make_mock_agent("team_lead")
        mock_get_engine.return_value = make_mock_engine("result text")

        result = run_agent_task(agent, ("do the thing", "expected output"))

        assert result == "result text"
        agent.activate_context.assert_called_once_with(task_id=None)
        mock_get_engine.return_value.execute.assert_called_once()
        agent.create_agent_run.assert_not_called()

    @patch("backend.engine.get_engine")
    def test_with_run_tracking(self, mock_get_engine):
        from backend.flows.helpers import run_agent_task
        from backend.tests.flows.conftest import make_mock_agent, make_mock_engine

        agent = make_mock_agent("developer")
        mock_get_engine.return_value = make_mock_engine("done")

        result = run_agent_task(
            agent, ("implement", "code"), task_id=42, track_run=True,
        )

        assert result == "done"
        agent.activate_context.assert_called_once_with(task_id=42)
        agent.create_agent_run.assert_called_once_with(42)
        agent.complete_agent_run.assert_called_once()
        call_args = agent.complete_agent_run.call_args
        assert call_args[0][0] == "test-run-id"
        assert call_args[1]["status"] == "completed"

    @patch("backend.engine.get_engine")
    def test_failure_completes_run_as_failed(self, mock_get_engine):
        from backend.flows.helpers import run_agent_task
        from backend.tests.flows.conftest import make_mock_agent

        agent = make_mock_agent("developer")
        mock_get_engine.return_value.execute.side_effect = RuntimeError("LLM down")

        with pytest.raises(RuntimeError, match="LLM down"):
            run_agent_task(
                agent, ("implement", "code"), task_id=42, track_run=True,
            )

        agent.complete_agent_run.assert_called_once()
        call_args = agent.complete_agent_run.call_args
        assert call_args[1]["status"] == "failed"
        assert call_args[1]["error_class"] == "RuntimeError"
