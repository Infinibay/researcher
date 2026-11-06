"""Legacy context cannot silently preserve cleared scope or borrow another agent's identity."""

import threading
from contextvars import ContextVar

import pytest

from backend.tools.base import context


@pytest.fixture
def isolated_context(monkeypatch):
    """Isolate real context propagation without substituting the scope-resolution behavior."""
    monkeypatch.setattr(context, "_tls", threading.local())
    monkeypatch.setattr(context, "_agent_contexts", {})
    for name in ["project_id", "agent_id", "agent_run_id", "task_id", "workspace_path"]:
        monkeypatch.setattr(
            context, "_" + name + "_var", ContextVar("test_" + name, default=None)
        )
        monkeypatch.delenv("INFINIBAY_" + name.upper(), raising=False)


def test_explicit_clear_masks_older_local_and_environment_scope(
    isolated_context, monkeypatch
):
    """None is a deliberate withdrawal, even when a sandbox environment still has a project."""
    context.set_context(project_id=101, task_id=1001, agent_id="author")
    monkeypatch.setenv("INFINIBAY_PROJECT_ID", "202")
    context.set_context(project_id=None, task_id=None)
    assert context.get_current_project_id() is None
    assert context.get_current_task_id() is None
    assert context.get_context_for_agent("author").project_id is None
    assert context.get_context_for_agent("author").task_id is None


def test_omitted_fields_preserve_only_the_same_agents_context(isolated_context):
    """A task-only update preserves its owner; switching to an unknown agent does not borrow it."""
    context.set_context(project_id=101, task_id=1001, agent_id="author")
    context.set_context(task_id=1002)
    assert context.get_context().project_id == 101
    assert context.get_context().task_id == 1002
    context.set_context(agent_id="new-agent")
    assert context.get_context().project_id is None
    assert context.get_context().task_id is None
    assert context.get_context_for_agent("new-agent").project_id is None




def test_switching_to_registered_agent_restores_its_own_snapshot(isolated_context):
    """An existing actor's task and project follow that actor, not a reused execution thread."""
    context.set_context(project_id=101, task_id=1001, agent_id="author")
    context.set_context(project_id=202, task_id=2002, agent_id="other")
    context.set_context(agent_id="author", agent_run_id="new-author-run")
    assert context.get_context().project_id == 101
    assert context.get_context().task_id == 1001
    assert context.get_current_agent_run_id() == "new-author-run"


def test_async_context_snapshots_do_not_read_a_later_threads_project(isolated_context):
    """Copied execution contexts retain their actor scope when another coroutine reuses the thread."""
    from contextvars import copy_context

    context.set_context(project_id=101, task_id=1001, agent_id="author")
    first = copy_context()
    context.set_context(project_id=202, task_id=2002, agent_id="other")
    assert first.run(context.get_current_project_id) == 101
    assert first.run(context.get_current_task_id) == 1001
    assert context.get_current_project_id() == 202
