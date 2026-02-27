"""PABADA Flow definitions — event-driven orchestration using CrewAI Flows."""

from backend.flows.main_project_flow import MainProjectFlow
from backend.flows.development_flow import DevelopmentFlow
from backend.flows.code_review_flow import CodeReviewFlow
from backend.flows.research_flow import ResearchFlow
from backend.flows.brainstorming_flow import BrainstormingFlow

from backend.flows.state_models import (
    ProjectState,
    DevelopmentState,
    CodeReviewState,
    ResearchState,
    BrainstormState,
    ProjectStatus,
    ReviewStatus,
    ResearchStatus,
    BrainstormPhase,
    TaskType,
)

from backend.flows.event_listeners import (
    AgentResolver,
    EventBus,
    FlowEvent,
    ListenerManager,
    TaskStatusChangedListener,
    NewTaskCreatedListener,
    UserMessageListener,
    StagnationDetectedListener,
    AllTasksDoneListener,
    EpicCreatedListener,
    event_bus,
)

from backend.flows import helpers

__all__ = [
    # Flows
    "MainProjectFlow",
    "DevelopmentFlow",
    "CodeReviewFlow",
    "ResearchFlow",
    "BrainstormingFlow",
    # State models
    "ProjectState",
    "DevelopmentState",
    "CodeReviewState",
    "ResearchState",
    "BrainstormState",
    # Enums
    "ProjectStatus",
    "ReviewStatus",
    "ResearchStatus",
    "BrainstormPhase",
    "TaskType",
    # Event system
    "AgentResolver",
    "EventBus",
    "FlowEvent",
    "ListenerManager",
    "TaskStatusChangedListener",
    "NewTaskCreatedListener",
    "UserMessageListener",
    "StagnationDetectedListener",
    "AllTasksDoneListener",
    "EpicCreatedListener",
    "event_bus",
    # Helpers sub-package
    "helpers",
]
