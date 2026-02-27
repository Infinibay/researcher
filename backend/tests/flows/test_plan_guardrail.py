"""Tests for plan guardrail, flexible plan parsing, and completion_router no-tasks guard."""

from __future__ import annotations

from backend.flows.guardrails import validate_plan_output
from backend.flows.helpers.db_helpers import get_task_count
from backend.flows.helpers.parsing import parse_plan_tasks


class TestValidatePlanOutput:
    """Test validate_plan_output guardrail."""

    def test_accepts_plan_with_canonical_format(self):
        """Plan with **Title**: lines should be accepted."""
        plan = (
            "## Epic 1: Setup\n"
            "### Task 1\n"
            "**Title**: Initialize project repository\n"
            "**Description**: Set up the repo with initial scaffolding\n"
            "**Type**: code\n\n"
            "### Task 2\n"
            "**Title**: Configure CI/CD pipeline\n"
            "**Description**: Set up GitHub Actions for testing\n"
            "**Type**: code\n"
        )
        result = validate_plan_output(plan)
        assert result[0] is True

    def test_accepts_plan_with_free_form_structure(self):
        """Plan without rigid formatting but with actionable content should pass."""
        plan = (
            "## Project Plan\n"
            "1. Set up the project repository and initial scaffolding\n"
            "2. Build the frontend components for the dashboard\n"
            "3. Write the backend API endpoints and database models\n"
            "4. Deploy to production environment and configure monitoring\n"
            "This plan covers the full development pipeline from setup to deploy."
        )
        result = validate_plan_output(plan)
        assert result[0] is True

    def test_rejects_short_plan(self):
        """Very short plan should be rejected."""
        result = validate_plan_output("Short plan.")
        assert result[0] is False
        assert "too short" in result[1]

    def test_rejects_vague_plan(self):
        """Plan that is long but doesn't describe concrete work should be rejected."""
        plan = (
            "We should think carefully about what the users really want "
            "and make sure we understand their needs before proceeding. "
            "It is important to consider all stakeholders and gather "
            "feedback from everyone involved in the process."
        )
        result = validate_plan_output(plan)
        assert result[0] is False
        assert "concrete work" in result[1]


class TestParsePlanTasksFlexible:
    """Test that parse_plan_tasks handles various LLM output formats."""

    def test_canonical_bold_title(self):
        """Pattern 1: **Title**: text — the expected format."""
        plan = (
            "### Task 1\n"
            "**Title**: Initialize project repository\n"
            "**Description**: Setup\n\n"
            "### Task 2\n"
            "**Title**: Design database schema\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 2
        assert titles[0] == "Initialize project repository"
        assert titles[1] == "Design database schema"

    def test_plain_title_no_bold(self):
        """Pattern 2: Title: text — without bold markers."""
        plan = (
            "## Tasks\n"
            "### Task 1\n"
            "Title: Initialize project repository\n"
            "Description: Setup the repo\n\n"
            "### Task 2\n"
            "Title: Design database schema\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 2
        assert titles[0] == "Initialize project repository"

    def test_task_headers_with_colon(self):
        """Pattern 3: ### Task N: Title text."""
        plan = (
            "## Tasks\n"
            "### Task 1: Initialize project repository\n"
            "Set up the repo\n\n"
            "### Task 2: Design database schema\n"
            "Create the tables\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 2
        assert titles[0] == "Initialize project repository"
        assert titles[1] == "Design database schema"

    def test_bold_list_items_under_tasks_section(self):
        """Pattern 4: - **Bold title** under a Tasks header."""
        plan = (
            "## Epic 1: Setup\n"
            "### Tasks\n"
            "- **Initialize project repository**\n"
            "- **Design database schema**\n"
            "- **Configure CI/CD pipeline**\n\n"
            "## Epic 2: Development\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 3
        assert titles[0] == "Initialize project repository"

    def test_numbered_bold_items(self):
        """Pattern 5: 1. **Title** — numbered bold items."""
        plan = (
            "## Plan\n"
            "1. **Initialize project repository** - set up scaffolding\n"
            "2. **Design database schema** - create tables\n"
            "3. **Configure CI/CD pipeline** - github actions\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 3
        assert titles[0] == "Initialize project repository"

    def test_canonical_format_takes_priority(self):
        """When **Title**: lines exist, don't fall through to other patterns."""
        plan = (
            "### Task 1: Header title\n"
            "**Title**: Actual canonical title\n"
            "**Description**: Setup\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 1
        assert titles[0] == "Actual canonical title"

    def test_deduplication(self):
        """Near-duplicate titles should be deduplicated."""
        plan = (
            "**Title**: Create project repository\n"
            "**Title**: Build project repository\n"  # near-duplicate after normalization (both verbs stripped)
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 1

    def test_rejects_very_short_titles(self):
        """Titles shorter than 5 chars should be skipped."""
        plan = (
            "**Title**: Test\n"  # too short (4 chars)
            "**Title**: Initialize project repository\n"
        )
        titles = parse_plan_tasks(plan)
        assert len(titles) == 1
        assert titles[0] == "Initialize project repository"


class TestGetTaskCount:
    """Test the get_task_count helper."""

    def test_returns_zero_for_empty_project(self, sample_project):
        assert get_task_count(sample_project) == 0

    def test_returns_correct_count(self, executing_project):
        assert get_task_count(executing_project) == 4

    def test_returns_zero_for_nonexistent_project(self):
        assert get_task_count(99999) == 0


class TestCompletionRouterNoStructure:
    """Test that completion_router routes to no_structure when 0 tasks exist."""

    def test_routes_to_no_structure_when_no_tasks(self, sample_project):
        """completion_router should return 'no_structure' when project has 0 tasks."""
        from backend.flows.main_project_flow import MainProjectFlow
        from backend.flows.state_models import ProjectStatus

        flow = MainProjectFlow()
        flow.state.project_id = sample_project
        flow.state.status = ProjectStatus.EXECUTING

        result = flow.completion_router()
        assert result == "no_structure"

    def test_routes_to_not_complete_when_tasks_exist(self, executing_project):
        """completion_router should NOT return 'no_structure' when tasks exist."""
        from backend.flows.main_project_flow import MainProjectFlow
        from backend.flows.state_models import ProjectStatus

        flow = MainProjectFlow()
        flow.state.project_id = executing_project
        flow.state.status = ProjectStatus.EXECUTING

        result = flow.completion_router()
        # Epics are not all completed -> should be "not_complete"
        assert result == "not_complete"
