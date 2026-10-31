"""Neutral product execution contracts; no database, framework or vendor I/O."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


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


def validate_correction(
    *,
    project_id,
    task_id,
    expected_version,
    operation_key,
    statement,
    source_kind,
    source_reference,
):
    for value in (project_id, task_id, expected_version):
        identity(value)
    command_key(operation_key)
    text(statement, "statement", 50000)
    text(source_reference, "source_reference", 1200)
    if source_kind not in (
        "user_message",
        "user_example",
        "tool_evidence",
        "assumption",
    ):
        raise ValueError("Unknown context source kind")


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


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_seconds: float = 30
    output_bytes: int = 1048576

    def __post_init__(self):
        if not isinstance(self.argv, tuple) or not 1 <= len(self.argv) <= 128:
            raise ValueError("Expected a nonempty bounded command argv tuple")
        text(self.argv[0], "executable", 16384)
        if any(not isinstance(arg, str) or "\0" in arg for arg in self.argv):
            raise ValueError("Command arguments must be strings without NUL")
        if sum(len(arg.encode()) for arg in self.argv) > 65536:
            raise ValueError("Command arguments exceed the byte budget")
        text(self.cwd, "cwd", 4096)
        path = PurePosixPath(self.cwd)
        if path.is_absolute() or ".." in path.parts or "\0" in self.cwd:
            raise ValueError("Command cwd must stay relative to its workspace")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not 0 < self.timeout_seconds <= 300
        ):
            raise ValueError(
                "Command deadline must be positive and at most 300 seconds"
            )
        if type(self.output_bytes) is not int or not 1 <= self.output_bytes <= 4194304:
            raise ValueError(
                "Command output budget must be between 1 byte and 4 MiB per stream"
            )


@dataclass(frozen=True)
class CommandJob:
    job_id: str
    run_id: str
    attempt_id: str
    executor_id: str
    operation_key: str
    status: str
    spec: CommandSpec
    workspace: str
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    output_limited: bool
    cancel_requested: bool
    error: str | None


@dataclass(frozen=True)
class JobReservation:
    job: CommandJob
    should_dispatch: bool


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
