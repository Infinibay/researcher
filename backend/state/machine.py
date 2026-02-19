"""Canonical task state machine — single source of truth for valid transitions."""

VALID_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"pending", "cancelled"},
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"review_ready", "cancelled"},
    "review_ready": {"done", "rejected", "cancelled"},
    "rejected": {"in_progress", "cancelled"},
    "done": set(),
    "cancelled": set(),
}

TASK_STATUSES = list(VALID_TRANSITIONS.keys())

TERMINAL_STATUSES = frozenset({"done", "cancelled"})


class TaskStateMachine:
    """Static helpers for task status validation."""

    VALID_TRANSITIONS = VALID_TRANSITIONS

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in VALID_TRANSITIONS.get(current, set())

    @staticmethod
    def get_allowed_transitions(current: str) -> set[str]:
        return VALID_TRANSITIONS.get(current, set())

    @staticmethod
    def validate_transition(current: str, target: str) -> None:
        """Raise ``ValueError`` if the transition is not allowed."""
        if target not in VALID_TRANSITIONS:
            raise ValueError(
                f"Invalid status '{target}'. Must be one of: {', '.join(TASK_STATUSES)}"
            )
        allowed = VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: '{current}' -> '{target}'. "
                f"Allowed transitions from '{current}': {allowed or 'none (terminal state)'}"
            )

    @staticmethod
    def is_terminal(status: str) -> bool:
        return status in TERMINAL_STATUSES
