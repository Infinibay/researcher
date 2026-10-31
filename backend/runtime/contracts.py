"""Neutral product execution contracts; no database, framework or vendor I/O."""

import re
from dataclasses import dataclass


class RunConflict(RuntimeError):
    """The command conflicts with an existing identity or current state."""


class RunNotFound(LookupError):
    """The object is absent from the caller's project scope."""


class StaleAttempt(RunConflict):
    """The attempt no longer has authority to mutate current work."""


def text(value: str, name: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(f"{name} must be nonempty and at most {maximum} UTF-8 bytes")


def identity(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("Expected a positive integer identity")


def command_key(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        raise ValueError("Invalid operation key")


@dataclass(frozen=True)
class RunSpec:
    project_id: int
    task_id: int
    actor_id: str
    context_version: int
    operation_key: str
    prompt: str
    runtime: str

    def __post_init__(self):
        for value in (self.project_id, self.task_id, self.context_version):
            identity(value)
        text(self.actor_id, "actor_id", 128)
        text(self.prompt, "prompt", 200000)
        command_key(self.operation_key)
        command_key(self.runtime)


@dataclass(frozen=True)
class RunView:
    run_id: str
    project_id: int
    task_id: int
    actor_id: str
    context_version: int
    status: str
    fence: int
    attempt_id: str | None
    thread_id: str | None
    turn_id: str | None
    prompt: str
    runtime: str
    result: dict | None
    cancel_requested: bool


@dataclass(frozen=True)
class AttemptLease:
    run_id: str
    attempt_id: str
    project_id: int
    task_id: int
    actor_id: str
    context_version: int
    owner_id: str
    fence: int
    expires_at: float


@dataclass(frozen=True)
class RunEvent:
    event_id: int
    project_id: int
    entity_type: str | None
    entity_id: int | None
    event_type: str
    event_source: str
    data: dict
    created_at: str


@dataclass(frozen=True)
class EventPage:
    events: tuple[RunEvent, ...]
    next_after_id: int
    has_more: bool


def native_outcome(native_status: str) -> str:
    outcomes = {
        "completed": "needs_review",
        "failed": "reconciling",
        "interrupted": "reconciling",
    }
    if native_status not in outcomes:
        raise ValueError("Unsupported native terminal status")
    return outcomes[native_status]


def cancel_outcome(status: str) -> str:
    if status == "accepted":
        raise RunConflict("Accepted work cannot be retroactively cancelled")
    return {
        "queued": "cancelled",
        "needs_review": "cancelled",
        "running": "cancelling",
    }.get(status, status)


def invalidated_outcome(status: str) -> str:
    return {
        "queued": "superseded",
        "needs_review": "superseded",
        "running": "reconciling",
        "cancelling": "reconciling",
    }.get(status, status)
