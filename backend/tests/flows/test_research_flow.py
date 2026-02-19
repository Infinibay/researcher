"""Tests for ResearchFlow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.flows.state_models import ResearchState
from backend.tests.flows.conftest import make_mock_agent, make_mock_crew


class TestResearchState:
    """Test ResearchState model."""

    def test_default_state(self):
        state = ResearchState()
        assert state.task_id == 0
        assert state.hypothesis == ""
        assert state.findings == []
        assert state.validated is False
        assert state.peer_review_status == "pending"

    def test_state_with_values(self):
        state = ResearchState(
            project_id=1,
            task_id=10,
            hypothesis="Algorithm X is faster than Y",
            confidence_scores=[0.85, 0.72],
        )
        assert state.hypothesis == "Algorithm X is faster than Y"
        assert len(state.confidence_scores) == 2


class TestResearchFlowAssignment:
    """Test research task assignment."""

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_assign_research_success(self, mock_log, mock_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_agent.return_value = make_mock_agent("researcher", executing_project)
        MockCrew.return_value = make_mock_crew("Research plan outlined")
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2  # Research task from fixture
        flow.state.knowledge_service_enabled = False

        result = flow.assign_research()
        # @start() methods no longer return routing strings
        assert result is None

        # Routing is now handled by the router method
        route = flow.route_assignment()
        assert route == "task_assigned"

    @patch("backend.flows.research_flow.get_available_agent_by_role")
    def test_assign_research_task_not_found(self, mock_agent, db_conn):
        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = 1
        flow.state.task_id = 99999
        flow.state.knowledge_service_enabled = False

        result = flow.assign_research()
        # @start() methods no longer return routing strings
        assert result is None

        # Routing is now handled by the router method
        route = flow.route_assignment()
        assert route == "error"


class TestResearchFlowPeerReview:
    """Test peer review routing."""

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_peer_review_validated(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_reviewer = make_mock_agent("research_reviewer", executing_project)
        mock_avail_agent.return_value = mock_reviewer
        MockCrew.return_value = make_mock_crew("VALIDATED: Methodology is sound")
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.hypothesis = "Test hypothesis"
        flow.state.knowledge_service_enabled = False

        result = flow.request_peer_review()
        # @listen() methods no longer return routing strings
        assert result is None
        assert flow.state.validated is True
        assert flow.state.peer_review_status == "validated"

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_peer_review_rejected(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_reviewer = make_mock_agent("research_reviewer", executing_project)
        mock_avail_agent.return_value = mock_reviewer
        MockCrew.return_value = make_mock_crew("REJECTED: Insufficient evidence for conclusion")
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.hypothesis = "Test hypothesis"
        flow.state.knowledge_service_enabled = False

        result = flow.request_peer_review()
        # @listen() methods no longer return routing strings
        assert result is None
        assert flow.state.validated is False
        assert flow.state.peer_review_status == "rejected"


class TestReviewerFeedbackExtraction:
    """Test that reviewer feedback is extracted and stored in state."""

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_rejected_extracts_feedback_after_prefix(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_reviewer = make_mock_agent("research_reviewer", executing_project)
        mock_avail_agent.return_value = mock_reviewer
        MockCrew.return_value = make_mock_crew("REJECTED: Insufficient evidence for conclusion")
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.knowledge_service_enabled = False

        flow.request_peer_review()
        assert flow.state.validated is False
        assert flow.state.last_reviewer_feedback == "Insufficient evidence for conclusion"

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_rejected_fallback_when_no_prefix(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, db_conn, executing_project):
        raw_result = "The research lacks credible sources and has logical gaps"
        mock_reviewer = make_mock_agent("research_reviewer", executing_project)
        mock_avail_agent.return_value = mock_reviewer
        MockCrew.return_value = make_mock_crew(raw_result)
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.knowledge_service_enabled = False

        flow.request_peer_review()
        assert flow.state.validated is False
        assert flow.state.last_reviewer_feedback == raw_result

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_validated_clears_feedback(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_reviewer = make_mock_agent("research_reviewer", executing_project)
        mock_avail_agent.return_value = mock_reviewer
        MockCrew.return_value = make_mock_crew("VALIDATED: Methodology is sound")
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.last_reviewer_feedback = "old feedback from previous round"
        flow.state.knowledge_service_enabled = False

        flow.request_peer_review()
        assert flow.state.validated is True
        assert flow.state.last_reviewer_feedback == ""

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_available_agent_by_role")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    def test_rejected_case_insensitive_prefix(self, mock_log, mock_get_agent, mock_avail_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_reviewer = make_mock_agent("research_reviewer", executing_project)
        mock_avail_agent.return_value = mock_reviewer
        MockCrew.return_value = make_mock_crew("Rejected: Confidence scores are inflated")
        MockTask.return_value = MagicMock()

        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.knowledge_service_enabled = False

        flow.request_peer_review()
        assert flow.state.validated is False
        assert flow.state.last_reviewer_feedback == "Confidence scores are inflated"


class TestReviseResearchFeedbackPropagation:
    """Test that reviewer feedback is passed to the revision prompt."""

    @patch("backend.flows.research_flow.Crew")
    @patch("backend.flows.research_flow.Task")
    @patch("backend.flows.research_flow.get_agent_by_role")
    @patch("backend.flows.research_flow.log_flow_event")
    @patch("backend.flows.research_flow.res_tasks")
    def test_revise_research_passes_feedback_to_prompt(self, mock_res_tasks, mock_log, mock_get_agent, MockTask, MockCrew, db_conn, executing_project):
        mock_researcher = make_mock_agent("researcher", executing_project)
        mock_get_agent.return_value = mock_researcher
        MockCrew.return_value = make_mock_crew("Revision complete")
        MockTask.return_value = MagicMock()
        mock_res_tasks.revise_research.return_value = ("mock desc", "mock expected")

        from backend.flows.research_flow import ResearchFlow

        feedback = "Insufficient evidence for conclusion 3"
        flow = ResearchFlow()
        flow.state.project_id = executing_project
        flow.state.task_id = 2
        flow.state.researcher_id = f"researcher_p{executing_project}"
        flow.state.last_reviewer_feedback = feedback
        flow.state.revision_count = 1
        flow.state.knowledge_service_enabled = False

        flow.revise_research()

        mock_res_tasks.revise_research.assert_called_once_with(
            2,
            reviewer_feedback=feedback,
        )


class TestResearchFlowPeerReviewRouter:
    """Test the peer review router."""

    def test_router_validated(self):
        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.validated = True
        result = flow.peer_review_router()
        assert result == "validated"

    def test_router_rejected(self):
        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.validated = False
        flow.state.revision_count = 0
        flow.state.max_revisions = 7
        result = flow.peer_review_router()
        assert result == "rejected"
        # Router now increments revision_count on rejection
        assert flow.state.revision_count == 1

    def test_router_max_revisions_reached(self):
        from backend.flows.research_flow import ResearchFlow

        flow = ResearchFlow()
        flow.state.validated = False
        flow.state.revision_count = 6
        flow.state.max_revisions = 7
        result = flow.peer_review_router()
        assert result == "max_revisions_reached"
