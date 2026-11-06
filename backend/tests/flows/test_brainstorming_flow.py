"""Tests for BrainstormingFlow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.flows.helpers import calculate_time_elapsed, format_ideas, parse_ideas
from backend.flows.state_models import BrainstormPhase, BrainstormState


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


class TestRetiredAgentTask:
    """The old helper rejects before activating context, tracking a run or constructing a provider."""

    def test_old_helper_has_no_model_or_agent_effect(self, db_conn, executing_project):
        """An actual project requires native owner entry even before its first native run."""
        from types import SimpleNamespace

        from backend.flows.helpers import run_agent_task
        from backend.runtime.lifecycle import NativeOwnerRequired

        agent = SimpleNamespace(project_id=executing_project)
        with pytest.raises(NativeOwnerRequired):
            run_agent_task(agent, ("old brainstorm", "old output"), task_id=1, track_run=True)
