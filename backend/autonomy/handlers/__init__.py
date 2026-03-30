"""Event handlers that bridge agent_events to existing sub-flows.

Each handler maps an event type to execution logic, reusing all existing
sub-flows (DevelopmentFlow, ResearchFlow, CodeReviewFlow) and the
``build_crew`` / ``dispatch_message`` infrastructure.

Import safety: all imports from backend.flows.* and backend.agents.* are
LAZY (inside method bodies) to avoid the circular import chain.
"""

from .base import EventHandler, _parse_payload
from .task_handlers import TaskFlowHandler
from .review_handlers import ReviewHandler
from .misc_handlers import (
    HealthCheckHandler,
    MessageHandler,
    ProgressEvalHandler,
    ReworkHandler,
)

__all__ = [
    "EventHandler",
    "_parse_payload",
    "TaskFlowHandler",
    "ReviewHandler",
    "HealthCheckHandler",
    "MessageHandler",
    "ProgressEvalHandler",
    "ReworkHandler",
    "build_handler_map",
]

_HANDLER_MAP: dict[str, type[EventHandler]] = {
    "task_available": TaskFlowHandler,
    "task_resume": TaskFlowHandler,
    "review_ready": ReviewHandler,
    "task_rejected": ReworkHandler,
    "message_received": MessageHandler,
    "user_message_received": MessageHandler,
    "health_check": HealthCheckHandler,
    "stagnation_detected": ProgressEvalHandler,
    "all_tasks_done": ProgressEvalHandler,
    "waiting_for_research": ProgressEvalHandler,
    "evaluate_progress": ProgressEvalHandler,
}


def build_handler_map() -> dict[str, EventHandler]:
    """Return a dict of event_type -> handler instance."""
    return {etype: cls() for etype, cls in _HANDLER_MAP.items()}
