"""Pydantic state models for all PABADA flows."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class ProjectStatus(str, Enum):
    NEW = "new"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResearchStatus(str, Enum):
    ASSIGNED = "assigned"
    LITERATURE_REVIEW = "literature_review"
    HYPOTHESIS = "hypothesis"
    INVESTIGATING = "investigating"
    REPORT_WRITING = "report_writing"
    PEER_REVIEW = "peer_review"
    VALIDATED = "validated"
    REJECTED = "rejected"


class BrainstormPhase(str, Enum):
    BRAINSTORM = "brainstorm"
    CONSOLIDATION = "consolidation"
    DECISION = "decision"
    PRESENTATION = "presentation"
    COMPLETE = "complete"


class TaskType(str, Enum):
    DEVELOPMENT = "development"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    DESIGN = "design"
    BUG_FIX = "bug_fix"
    TEST = "test"
    INTEGRATION = "integration"


# ── State Models ──────────────────────────────────────────────────────────────


class ProjectState(BaseModel):
    """State for MainProjectFlow — orchestrates the entire project lifecycle."""

    project_id: int = 0
    project_name: str = ""
    status: ProjectStatus = ProjectStatus.NEW
    requirements: str = ""
    plan: str = ""
    user_approved: bool = False
    current_task_id: int | None = None
    current_task_type: str = ""
    feedback: str = ""
    epics_created: list[int] = Field(default_factory=list)
    milestones_created: list[int] = Field(default_factory=list)
    tasks_created: list[int] = Field(default_factory=list)
    completed_tasks: int = 0
    total_tasks: int = 0
    brainstorm_attempts: int = 0
    max_brainstorm_attempts: int = 3
    max_concurrent_tasks: int = 3
    evaluate_progress_attempts: int = 0
    max_evaluate_progress_attempts: int = 3
    running_task_ids: list[int] = Field(default_factory=list)
    repo_name: str = ""
    requirements_attempts: int = 0
    max_requirements_attempts: int = 3
    planning_iteration: int = 0
    current_step: str = ""


class DevelopmentState(BaseModel):
    """State for DevelopmentFlow — handles task assignment, coding, and review."""

    project_id: int = 0
    project_name: str = ""
    task_id: int = 0
    task_title: str = ""
    task_description: str = ""
    branch_name: str = ""
    developer_id: str = ""
    review_status: ReviewStatus = ReviewStatus.PENDING
    dependencies_met: bool = False
    agent_run_id: str = ""
    tech_hints: list[str] = Field(default_factory=list)


class CodeReviewState(BaseModel):
    """State for CodeReviewFlow — manages the dev/reviewer review cycle."""

    project_id: int = 0
    project_name: str = ""
    task_id: int = 0
    task_title: str = ""
    branch_name: str = ""
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewer_comments: list[str] = Field(default_factory=list)
    rejection_count: int = 0
    reviewer_id: str = ""
    developer_id: str = ""
    agent_run_id: str = ""
    ci_passed: bool = False
    ci_output: str = ""


class ResearchState(BaseModel):
    """State for ResearchFlow — manages research lifecycle with peer review."""

    project_id: int = 0
    project_name: str = ""
    task_id: int = 0
    task_title: str = ""
    researcher_id: str = ""
    hypothesis: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence_scores: list[float] = Field(default_factory=list)
    peer_review_status: str = "pending"
    last_reviewer_feedback: str = ""
    validated: bool = False
    report_path: str = ""
    references: list[str] = Field(default_factory=list)
    agent_run_id: str = ""
    revision_count: int = 0
    max_revisions: int = 7
    rescue_count: int = 0
    knowledge_service_enabled: bool = True


class TicketCreationState(BaseModel):
    """State for TicketCreationFlow — iterative ticket creation with research."""

    project_id: int = 0
    project_name: str = ""
    plan: str = ""
    ticket_index: int = 0
    task_titles: list[str] = Field(default_factory=list)
    total_tickets: int = 0
    epics_created: dict[str, int] = Field(default_factory=dict)
    milestones_created: dict[str, int] = Field(default_factory=dict)
    tasks_created: dict[str, int] = Field(default_factory=dict)
    failed_items: list[str] = Field(default_factory=list)


class BrainstormState(BaseModel):
    """State for BrainstormingFlow — time-limited ideation sessions."""

    project_id: int = 0
    project_name: str = ""
    project_description: str = ""
    project_type: str = "development"
    participants: list[str] = Field(default_factory=list)
    ideas: list[dict[str, Any]] = Field(default_factory=list)
    consolidated_ideas: list[dict[str, Any]] = Field(default_factory=list)
    start_time: str = ""
    phase: BrainstormPhase = BrainstormPhase.BRAINSTORM
    time_limit_brainstorm: int = 900  # 15 minutes in seconds
    time_limit_decision: int = 300  # 5 minutes in seconds
    decision_start_time: str = ""
    selected_ideas: list[dict[str, Any]] = Field(default_factory=list)
    user_approved: bool = False
    user_feedback: str = ""
    round_count: int = 0
    max_rounds: int = 5
    rejection_attempts: int = 0
    max_rejection_attempts: int = 3
    thread_id: str = ""
