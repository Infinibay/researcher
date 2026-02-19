"""Tests for BrainstormingFlow."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.flows.helpers import calculate_time_elapsed, parse_ideas
from backend.flows.state_models import BrainstormPhase, BrainstormState
from backend.tests.flows.conftest import make_mock_agent, make_mock_crew


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

    @patch("backend.flows.brainstorming_flow.log_flow_event")
    def test_start_session(self, mock_log):
        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1

        result = flow.start_session()
        # start_session no longer returns a routing string (routing is done by brainstorm_phase router)
        assert result is None
        assert len(flow.state.participants) == 3
        assert flow.state.start_time != ""
        assert flow.state.phase == BrainstormPhase.BRAINSTORM


class TestBrainstormingFlowConsolidation:
    """Test idea consolidation."""

    @patch("backend.flows.brainstorming_flow.Crew")
    @patch("backend.flows.brainstorming_flow.Task")
    @patch("backend.flows.brainstorming_flow.get_agent_by_role")
    @patch("backend.flows.brainstorming_flow.log_flow_event")
    def test_consolidate_ideas(self, mock_log, mock_agent, MockTask, MockCrew):
        mock_agent.return_value = make_mock_agent("team_lead")
        MockCrew.return_value = make_mock_crew(
            "1. Combined Feature: Merged auth and security features\n"
            "2. Analytics: Dashboard and reporting combined"
        )
        MockTask.return_value = MagicMock()

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
    @patch("backend.flows.brainstorming_flow.Crew")
    @patch("backend.flows.brainstorming_flow.Task")
    @patch("backend.flows.brainstorming_flow.get_agent_by_role")
    def test_present_to_user_approved(self, mock_agent, MockTask, MockCrew, mock_log):
        mock_agent.return_value = make_mock_agent("project_lead")
        MockCrew.return_value = make_mock_crew("APPROVED")
        MockTask.return_value = MagicMock()

        from backend.flows.brainstorming_flow import BrainstormingFlow

        flow = BrainstormingFlow()
        flow.state.project_id = 1
        flow.state.selected_ideas = [{"title": "Feature A", "description": "Do A"}]

        result = flow.present_to_user()
        assert result == "approved"
        assert flow.state.user_approved is True

    @patch("backend.flows.brainstorming_flow.log_flow_event")
    @patch("backend.flows.brainstorming_flow.Crew")
    @patch("backend.flows.brainstorming_flow.Task")
    @patch("backend.flows.brainstorming_flow.get_agent_by_role")
    def test_present_to_user_rejected(self, mock_agent, MockTask, MockCrew, mock_log):
        mock_agent.return_value = make_mock_agent("project_lead")
        MockCrew.return_value = make_mock_crew("REJECTED: Need more innovative ideas")
        MockTask.return_value = MagicMock()

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
