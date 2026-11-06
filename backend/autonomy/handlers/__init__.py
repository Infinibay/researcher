"""Compatibility event handlers return scoped owner hints; native admission, review, correction and acceptance use their explicit runtime controls."""

from .base import EventHandler, _parse_payload
from .misc_handlers import (
    HealthCheckHandler,
    MessageHandler,
    ProgressEvalHandler,
    ReworkHandler,
)
from .review_handlers import ReviewHandler
from .task_handlers import TaskFlowHandler

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
