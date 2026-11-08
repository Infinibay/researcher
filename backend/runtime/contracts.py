"""Neutral product execution contracts; no database, framework or vendor I/O."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


class RunConflict(RuntimeError):
    """The command conflicts with an existing identity or current state."""


class ProjectBudgetExhausted(RunConflict):
    """A durable project allowance cannot reserve this attempt; no native turn was sent."""

    def __init__(self, budget):
        """Retain the transaction's admission snapshot, including unknown usage, independently of later history or policy reads."""
        super().__init__("Project work budget exhausted; no native turn was sent")
        self.budget = dict(budget)


class RunNotFound(LookupError):
    """The object is absent from the caller's project scope."""


class DeliveryReady(RuntimeError):
    """Host-only signal: a durable delivery revoked authority; interrupt without another model step."""

    def __init__(self, answer_bytes=0):
        """Carry the host-measured explanation size so typed delivery cannot bypass the native output fuse."""
        super().__init__("Durable host delivery ready")
        self.answer_bytes = answer_bytes


class StaleAttempt(RunConflict):
    """The attempt no longer has authority to mutate current work."""


class WorkspaceChanged(RunConflict):
    """The admitted repository or physical directory cannot be revalidated."""


class InputTooLarge(RunConflict):
    """The complete input exceeds a declared bound; nothing is silently omitted."""


@dataclass(frozen=True)
class FrozenRunInput:
    """Pair exact serialized attempt input with its content hash; the value alone does not certify
    provenance or permission.
    """
    input_text: str
    input_sha256: str


def text(value: str, name: str, maximum: int) -> None:
    """Reject blank, non-string or oversized UTF-8 text without truncating the caller's value."""
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(f"{name} must be nonempty and at most {maximum} UTF-8 bytes")


def identity(value: int) -> None:
    """Require a positive integer database identity, excluding booleans."""
    if type(value) is not int or value <= 0:
        raise ValueError("Expected a positive integer identity")


def command_key(value: str) -> None:
    """Validate a bounded stable operation identifier before it can name a replayable intent."""
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
    """Validate the correction scope, expected version, original key, statement and attributed source
    kind before any persistence.
    """
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
    """Describe one requested task execution and its context version; validated request data is not an
    attempt lease or execution permission.
    """
    project_id: int
    task_id: int
    actor_id: str
    context_version: int
    operation_key: str
    prompt: str
    runtime: str

    def __post_init__(self):
        """Validate request identities and byte bounds without reading storage or admitting an
        execution.
        """
        for value in (self.project_id, self.task_id, self.context_version):
            identity(value)
        text(self.actor_id, "actor_id", 128)
        text(self.prompt, "prompt", 200000)
        command_key(self.operation_key)
        command_key(self.runtime)


@dataclass(frozen=True)
class WorkspaceBinding:
    """Carry the selected repository and expected physical directory identity so admission and
    execution can revalidate the same workspace.
    """
    repository_id: int
    repository_name: str
    registration_path: str
    workspace: str
    device: int
    inode: int
    requested_repository_id: int | None = None

    def __post_init__(self):
        """Validate supplied repository identity and absolute workspace syntax; physical directory
        verification belongs to the workspace boundary.
        """
        identity(self.repository_id)
        identity(self.inode)
        if type(self.device) is not int or self.device < 0:
            raise ValueError("Invalid workspace device identity")
        if self.requested_repository_id is not None:
            identity(self.requested_repository_id)
            if self.requested_repository_id != self.repository_id:
                raise ValueError("Resolved repository differs from requested selection")
        for name in ("repository_name", "registration_path", "workspace"):
            text(getattr(self, name), name, 4096)
        if not PurePosixPath(self.workspace).is_absolute() or "\0" in self.workspace:
            raise ValueError("Workspace binding requires an absolute host path")


@dataclass(frozen=True)
class RunView:
    """Immutable owner projection of one durable run, with optional attributed review metadata."""

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
    operation_key: str = ""
    conversation_thread_id: str | None = None
    model: str | None = None
    repository_id: int | None = None
    repository_name: str | None = None
    issue: dict | None = None
    review: dict | None = None
    execution_kind: str = "research"
    model_selection: dict | None = None


@dataclass(frozen=True)
class AttemptLease:
    """Identify one owner's fenced attempt and expiry; mutation still requires store-side validation
    against current durable authority.
    """
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
    """Expose one attributed durable runtime observation and its cursor; an event does not authorize
    work or prove the truth of model content.
    """
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
    """Return an ordered observation batch with its next cursor and continuation flag, without
    replaying the effects those events describe.
    """
    events: tuple[RunEvent, ...]
    next_after_id: int
    has_more: bool


@dataclass(frozen=True)
class CommandSpec:
    """Specify an argument vector, relative directory, deadline and per-stream capture bound;
    construction does not launch a process.
    """
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_seconds: float = 30
    output_bytes: int = 1048576

    def __post_init__(self):
        """Validate argument bytes, workspace-relative paths and explicit time/output ceilings before a
        command may be reserved.
        """
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
    """Project one reserved command, captured binary output and separate local-closure evidence; exit
    code and closure may independently be unknown.
    """
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
    peer_id: str | None = None
    local_execution_closed: bool = False


@dataclass(frozen=True)
class JobReservation:
    """Return the original command receipt and whether this reservation newly permits dispatch;
    recovering a receipt never grants another launch.
    """
    job: CommandJob
    should_dispatch: bool


def native_outcome(native_status: str) -> str:
    """Map a supported native terminal observation to review or reconciliation; native completion never
    means owner acceptance.
    """
    outcomes = {
        "completed": "needs_review",
        "failed": "reconciling",
        "interrupted": "reconciling",
    }
    if native_status not in outcomes:
        raise ValueError("Unsupported native terminal status")
    return outcomes[native_status]


def cancel_outcome(status: str) -> str:
    """Choose the product state after cancellation intent, rejecting accepted work and preserving
    states that already require separate recovery.
    """
    if status == "accepted":
        raise RunConflict("Accepted work cannot be retroactively cancelled")
    return {
        "queued": "cancelled",
        "needs_review": "cancelled",
        "waiting_input": "cancelled",
        "running": "cancelling",
    }.get(status, status)


def invalidated_outcome(status: str) -> str:
    """Invalidate queued or delivered work after context changes while sending active work to
    reconciliation rather than claiming it has stopped.
    """
    return {
        "queued": "superseded",
        "needs_review": "superseded",
        "waiting_input": "superseded",
        "running": "reconciling",
        "cancelling": "reconciling",
    }.get(status, status)
