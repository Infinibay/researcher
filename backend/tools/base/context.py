"""Actor-bound context and explicit execution-local scope for retained tools.

CrewAI agents with ``max_execution_time`` set run tool execution inside a
``concurrent.futures.ThreadPoolExecutor``, meaning tools execute in a
**different thread** from where ``set_context()`` was called.  Both
``threading.local()`` and ``ContextVar`` are inherently thread-scoped and
cannot propagate across this boundary.

**Primary storage**: a process-global dict (``_agent_contexts``) keyed by
``agent_id``.  Tools are stamped with their owning agent's ID at construction
time (via ``bind_tools_to_agent()``), so they can look up the correct context
from any thread.

**Unbound callers**: execution-local ContextVar, then environment only before a
context is established. Explicit None withdraws a value and masks environment fallback.
Thread-local values are compatibility mirrors, never authoritative across async tasks.
"""

import logging
import os
import threading
from contextvars import ContextVar
from dataclasses import dataclass, replace

_ctx_logger = logging.getLogger(__name__)

# ── Process-global storage (primary — survives thread boundaries) ────────────

_agent_contexts: dict[str, "ToolContext"] = {}
_agent_contexts_lock = threading.Lock()

# ── Thread-local storage (fallback for non-tool callers) ─────────────────────

_tls = threading.local()

# ── ContextVar storage (fallback for asyncio-aware code paths) ───────────────


class _Omitted:
    """Distinguish an omitted update from an explicit withdrawal of context."""


_UNSET = _Omitted()
_project_id_var: ContextVar = ContextVar("project_id", default=_UNSET)
_agent_id_var: ContextVar = ContextVar("agent_id", default=_UNSET)
_agent_run_id_var: ContextVar = ContextVar("agent_run_id", default=_UNSET)
_task_id_var: ContextVar = ContextVar("task_id", default=_UNSET)
_workspace_path_var: ContextVar = ContextVar("workspace_path", default=_UNSET)


@dataclass
class ToolContext:
    """Snapshot of current agent context."""

    project_id: int | None = None
    agent_id: str | None = None
    agent_run_id: str | None = None
    task_id: int | None = None
    workspace_path: str | None = None
    event_id: int | None = None
    resume_state: dict | None = None


# ── Setting context ──────────────────────────────────────────────────────────


def set_context(
    project_id: int | None | _Omitted = _UNSET,
    agent_id: str | None | _Omitted = _UNSET,
    agent_run_id: str | None | _Omitted = _UNSET,
    task_id: int | None | _Omitted = _UNSET,
    workspace_path: str | None | _Omitted = _UNSET,
    event_id: int | None | _Omitted = _UNSET,
    resume_state: dict | None | _Omitted = _UNSET,
) -> ToolContext:
    """Apply explicit updates to one actor; None clears, omitted fields preserve its own snapshot.

    Switching actors restores only that actor's registered scope, or an empty scope
    for an unknown actor. ContextVars are authoritative within async executions;
    stamped worker-thread tools use the actor registry. An explicit clear never
    falls back to an environment value or another actor's thread-local state.
    """
    previous = get_context()
    key = previous.agent_id if agent_id is _UNSET else agent_id
    supplied = {
        "project_id": project_id,
        "agent_id": agent_id,
        "agent_run_id": agent_run_id,
        "task_id": task_id,
        "workspace_path": workspace_path,
        "event_id": event_id,
        "resume_state": resume_state,
    }
    for field in ("project_id", "task_id"):
        value = supplied[field]
        if value is not _UNSET and value is not None:
            try:
                supplied[field] = int(value)
            except (ValueError, TypeError):
                pass
    with _agent_contexts_lock:
        if key is None:
            if previous.agent_id:
                _agent_contexts.pop(previous.agent_id, None)
            base = previous if agent_id is _UNSET else ToolContext()
        elif key != previous.agent_id:
            base = _agent_contexts.get(key, ToolContext(agent_id=key))
        else:
            base = _agent_contexts.get(key, previous)
        updates = {
            name: value for name, value in supplied.items() if value is not _UNSET
        }
        updates["agent_id"] = key
        current = replace(base, **updates)
        if key:
            _agent_contexts[key] = current
    for name, variable in (
        ("project_id", _project_id_var),
        ("agent_id", _agent_id_var),
        ("agent_run_id", _agent_run_id_var),
        ("task_id", _task_id_var),
        ("workspace_path", _workspace_path_var),
    ):
        value = getattr(current, name)
        variable.set(value)
        setattr(_tls, name, value)
    _ctx_logger.debug(
        "set_context: actor=%s project=%s task=%s",
        current.agent_id,
        current.project_id,
        current.task_id,
    )
    return current


def get_context_for_agent(agent_id: str) -> ToolContext:
    """Get context for a specific agent from process-global storage."""
    with _agent_contexts_lock:
        return _agent_contexts.get(agent_id, ToolContext())


def clear_agent_context(agent_id: str) -> None:
    """Remove an agent's context entry (call when agent finishes)."""
    with _agent_contexts_lock:
        _agent_contexts.pop(agent_id, None)


def bind_tools_to_agent(tools: list, agent_id: str) -> None:
    """Stamp tool instances with their owning agent's ID.

    Call this after creating tools but before passing them to CrewAI Agent.
    Each tool's ``_bound_agent_id`` attribute is used by InfinibayBaseTool
    to look up context from the process-global dict.
    """
    for tool in tools:
        try:
            object.__setattr__(tool, "_bound_agent_id", agent_id)
        except (AttributeError, TypeError):
            _ctx_logger.debug(
                "bind_tools_to_agent: could not stamp tool %s",
                getattr(tool, "name", type(tool).__name__),
            )


# ── Getting context ──────────────────────────────────────────────────────────


def get_context() -> ToolContext:
    """Get current context using all available sources."""
    return ToolContext(
        project_id=_get_project_id(),
        agent_id=_get_agent_id(),
        agent_run_id=_get_agent_run_id(),
        task_id=_get_task_id(),
        workspace_path=_get_workspace_path(),
    )


def _context_value(variable, environment):
    """Use environment only before a context was established, never after explicit clearing."""
    value = variable.get()
    return environment() if value is _UNSET else value


def _get_project_id() -> int | None:
    """Resolve project in this execution without borrowing mutable thread state."""
    return _context_value(_project_id_var, lambda: _env_int("INFINIBAY_PROJECT_ID"))


def _get_agent_id() -> str | None:
    """Resolve the current execution's actor, preserving an explicit clear."""
    return _context_value(_agent_id_var, lambda: os.environ.get("INFINIBAY_AGENT_ID"))


def _get_agent_run_id() -> str | None:
    """Resolve the current actor run without retaining another actor's invocation."""
    return _context_value(
        _agent_run_id_var, lambda: os.environ.get("INFINIBAY_AGENT_RUN_ID")
    )


def _get_task_id() -> int | None:
    """Resolve the selected task or explicit absence in this execution."""
    return _context_value(_task_id_var, lambda: _env_int("INFINIBAY_TASK_ID"))


def _get_workspace_path() -> str | None:
    """Resolve workspace only from this execution or its initial container environment."""
    return _context_value(
        _workspace_path_var, lambda: os.environ.get("INFINIBAY_WORKSPACE_PATH")
    )


# ── Public convenience getters (used by InfinibayBaseTool fallback) ─────────────


def get_current_project_id() -> int | None:
    """Get the current project ID from context or environment."""
    return _get_project_id()


def get_current_agent_id() -> str | None:
    """Get the current agent ID from context or environment."""
    return _get_agent_id()


def get_current_agent_run_id() -> str | None:
    """Get the current agent run ID from context or environment."""
    return _get_agent_run_id()


def get_current_task_id() -> int | None:
    """Get the current task ID from context or environment."""
    return _get_task_id()


def get_current_workspace_path() -> str | None:
    """Get the current workspace path from context or environment."""
    return _get_workspace_path()


def _env_int(name: str) -> int | None:
    """Read an integer from environment, returning None if missing or invalid."""
    val = os.environ.get(name)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None
