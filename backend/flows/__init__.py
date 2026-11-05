"""Lazy compatibility exports keep native owner handoffs independent of legacy engine initialization."""

from importlib import import_module

_EXPORTS = {
    "MainProjectFlow": "main_project_flow",
    "DevelopmentFlow": "development_flow",
    "CodeReviewFlow": "code_review_flow",
    "ResearchFlow": "research_flow",
    "BrainstormingFlow": "brainstorming_flow",
    "ProjectState": "state_models",
    "DevelopmentState": "state_models",
    "CodeReviewState": "state_models",
    "ResearchState": "state_models",
    "BrainstormState": "state_models",
    "ProjectStatus": "state_models",
    "ReviewStatus": "state_models",
    "ResearchStatus": "state_models",
    "BrainstormPhase": "state_models",
    "TaskType": "state_models",
    "AgentResolver": "event_listeners",
    "EventBus": "event_listeners",
    "FlowEvent": "event_listeners",
    "ListenerManager": "event_listeners",
    "TaskStatusChangedListener": "event_listeners",
    "NewTaskCreatedListener": "event_listeners",
    "UserMessageListener": "event_listeners",
    "StagnationDetectedListener": "event_listeners",
    "AllTasksDoneListener": "event_listeners",
    "EpicCreatedListener": "event_listeners",
    "event_bus": "event_listeners",
}
__all__ = [
    "AgentResolver",
    "AllTasksDoneListener",
    "BrainstormPhase",
    "BrainstormState",
    "BrainstormingFlow",
    "CodeReviewFlow",
    "CodeReviewState",
    "DevelopmentFlow",
    "DevelopmentState",
    "EpicCreatedListener",
    "EventBus",
    "FlowEvent",
    "ListenerManager",
    "MainProjectFlow",
    "NewTaskCreatedListener",
    "ProjectState",
    "ProjectStatus",
    "ResearchFlow",
    "ResearchState",
    "ResearchStatus",
    "ReviewStatus",
    "StagnationDetectedListener",
    "TaskStatusChangedListener",
    "TaskType",
    "UserMessageListener",
    "event_bus",
    "helpers",
]


def __getattr__(name):
    """Load the requested historical export only, preserving its original class/module identity."""
    if name == "helpers":
        value = import_module("backend.flows.helpers")
    elif name in _EXPORTS:
        value = getattr(import_module(f"backend.flows.{_EXPORTS[name]}"), name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value
