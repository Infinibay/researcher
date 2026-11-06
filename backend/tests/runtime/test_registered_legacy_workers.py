"""Retired autonomy leaves only observed Stop over explicitly registered workers; no event replay or task recovery is implied."""

import threading

import pytest


async def test_shutdown_includes_a_thread_registered_without_a_flow_object(monkeypatch, caplog):
    """A thread-only registry entry is still real work: shutdown signals it, reports timeout honestly, and retains it until exit."""
    from backend.api.flow_manager import FlowManager
    from backend.api.main import _stop_active_flows

    manager = FlowManager()
    monkeypatch.setattr("backend.api.flow_manager.flow_manager", manager)
    release, requested = threading.Event(), threading.Event()
    worker = threading.Thread(target=release.wait, daemon=True)
    manager._threads[101] = worker
    manager._stop_signals[101] = requested
    worker.start()
    join = worker.join
    monkeypatch.setattr(worker, "join", lambda timeout=None: join(0))
    try:
        await _stop_active_flows()
        assert requested.is_set()
        assert manager._threads[101] is worker and manager.is_project_running(101)
        assert "still stopping" in caplog.text
    finally:
        release.set()
        join(1)
    await _stop_active_flows()
    assert 101 not in manager._threads and not manager.is_project_running(101)


def test_registered_autonomy_controller_blocks_native_work_until_observed_exit(coordination, monkeypatch):
    """The existing API registry owns a retained controller through timeout without touching historical messages, tasks or loop state."""
    from backend.api.flow_manager import FlowManager
    from backend.api.runtime_dependencies import _legacy_project_active

    manager = FlowManager()
    monkeypatch.setattr("backend.api.flow_manager.flow_manager", manager)
    release, requested = threading.Event(), threading.Event()
    worker = threading.Thread(target=release.wait, daemon=True)

    class RetainedController:
        """Model an existing controller, independent of the removed event loop's factories and scheduling code."""

        @property
        def is_running(self):
            """Report actual thread liveness, not whether Stop was requested."""
            return worker.is_alive()

        def stop_signal(self):
            """Signal the original worker without claiming that its current operation ended."""
            requested.set()

        def stop_join(self):
            """Bound observation while keeping the original worker reference available."""
            worker.join(timeout=0)
            return not worker.is_alive()

    c = coordination
    c.conn.execute("INSERT INTO agent_events(project_id,agent_id,event_type,status,payload_json)VALUES(101,'old','message_received','pending','{\"message\":\"An example, not permission\"}')")
    c.conn.commit()
    before = list(c.conn.iterdump())
    owner = RetainedController()
    manager._autonomy[101] = owner
    worker.start()
    try:
        assert _legacy_project_active(101)
        assert manager.stop_project_flow(101)["registered_workers_closed"] is False
        assert requested.is_set() and manager._autonomy[101] is owner
        assert _legacy_project_active(101)
    finally:
        release.set()
        worker.join(timeout=1)
    assert manager.stop_project_flow(101)["registered_workers_closed"] is True
    assert not _legacy_project_active(101) and 101 not in manager._autonomy
    assert list(c.conn.iterdump()) == before


def test_retired_autonomy_package_is_unavailable():
    """No poller, scorer, scavenger, old event mutator or handler remains importable as another execution path."""
    import importlib.util

    assert importlib.util.find_spec("backend.autonomy") is None


def test_retired_role_templates_and_provider_readers_are_unavailable():
    """Historical role factories and provider probes cannot reenter the native instruction or subscription path."""
    import importlib.util

    for name in ('team','shared','tool_refs','developer','researcher','code_reviewer','research_reviewer','team_lead','project_lead'):
        assert importlib.util.find_spec('backend.prompts.' + name) is None
    for name in ('llm','model_capabilities'):
        assert importlib.util.find_spec('backend.config.' + name) is None
    from backend.prompts.native import COMMON_INSTRUCTIONS

    assert 'Distinguish owner statements' in COMMON_INSTRUCTIONS
