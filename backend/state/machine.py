"""Manual task transition vocabulary; native executions require their separately fenced lifecycle controls."""

VALID_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"pending", "cancelled"},
    "pending": {"in_progress", "failed", "cancelled"},
    "in_progress": {"review_ready", "failed", "cancelled"},
    "review_ready": {"done", "rejected", "failed", "cancelled"},
    "rejected": {"in_progress", "failed", "cancelled"},
    "blocked": {"pending", "failed", "cancelled"},
    "done": set(),
    "cancelled": set(),
    "failed": {"pending", "cancelled"},
}

TASK_STATUSES = list(VALID_TRANSITIONS.keys())

TERMINAL_STATUSES = frozenset({"done", "cancelled", "failed"})


class TaskStateMachine:
    """Static helpers for task status validation."""

    VALID_TRANSITIONS = VALID_TRANSITIONS

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        """Check a declared edge without granting native execution or reopening authority."""
        return target in VALID_TRANSITIONS.get(current, set())

    @staticmethod
    def get_allowed_transitions(current: str) -> set[str]:
        """Return a copy so callers cannot mutate the shared lifecycle vocabulary."""
        return set(VALID_TRANSITIONS.get(current, set()))

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
        """Identify terminal labels without implying that retained work can be silently reopened."""
        return status in TERMINAL_STATUSES
