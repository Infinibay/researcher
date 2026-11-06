"""Native project admission excludes competing legacy activation/recovery; thread tests distinguish a stop request from observed termination."""

from types import SimpleNamespace

import pytest


def test_registered_listener_remains_owned_until_its_actual_worker_exits(coordination):
    """Removing listener factories must preserve bounded Stop and liveness for an already registered controller."""
    import threading

    from backend.api.flow_manager import FlowManager

    release = threading.Event()
    requested = threading.Event()
    worker = threading.Thread(target=release.wait, daemon=True)

    class RegisteredController:
        """Represent a retained controller whose current operation ignores its stop request until released."""

        @property
        def is_running(self):
            """Report actual worker liveness independently of the requested stop flag."""
            return worker.is_alive()

        def stop_all(self):
            """Request cooperative stop but refuse to claim termination while the worker remains live."""
            requested.set()
            worker.join(timeout=0)
            if worker.is_alive():
                raise TimeoutError("Existing check still running")

    manager = FlowManager()
    retained = RegisteredController()
    manager._listeners[101] = retained
    worker.start()
    try:
        stopped = manager.stop_project_flow(101)
        assert requested.is_set() and stopped["registered_workers_closed"] is False
        assert manager._listeners[101] is retained and manager.is_project_running(101)
    finally:
        release.set()
        worker.join(timeout=1)
    assert manager.stop_project_flow(101)["registered_workers_closed"] is True
    assert 101 not in manager._listeners


def admitted_project(coordination):
    """Persist actual native intent, leaving the separate legacy-looking code task without a native run."""
    c = coordination
    run = c.store.admit(c.spec)
    c.conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status,assigned_to)VALUES(1003,101,'code','Old partial work','in_progress','legacy-worker'),(2003,202,'code','Other project','in_progress','legacy-other')"
    )
    c.conn.commit()
    return c, run








def test_shutdown_cannot_reset_native_or_historical_project_tasks(
    coordination,
):
    """Stopping registered work cannot clear historical task assignments or put native work back into an old claim queue."""
    from backend.api.flow_manager import FlowManager

    c, _run = admitted_project(coordination)
    FlowManager().stop_project_flow(101)
    assert c.conn.execute(
        "SELECT status,assigned_to FROM tasks WHERE id=1003"
    ).fetchone()[:] == ("in_progress", "legacy-worker")
    assert c.conn.execute(
        "SELECT status,assigned_to FROM tasks WHERE id=2003"
    ).fetchone()[:] == ("in_progress", "legacy-other")


def test_legacy_project_start_returns_policy_without_opening_workers(coordination, monkeypatch):
    """The retained project entry returns an owner hint before thread construction, event mutation or snapshot replay."""
    import threading

    from backend.api.flow_manager import FlowManager

    admitted_project(coordination)

    def forbidden(*args, **kwargs):
        """Detect any attempt to recreate the retired scheduler."""
        pytest.fail("Legacy worker start reached")

    monkeypatch.setattr(threading, "Thread", forbidden)
    result = FlowManager().start_project_flow(101)
    assert result["delivery"] == "native_owner_handoff"











def test_flow_stop_keeps_actual_main_thread_registered_until_it_exits(
    coordination, monkeypatch
):
    """Stopping listeners does not close a held main flow; native admission must still see the registered live thread after a bounded join."""
    import threading

    from backend.api.flow_manager import FlowManager

    release, entered = threading.Event(), threading.Event()

    def held_worker():
        """Represent an already-running registered worker; new legacy start is retired."""
        entered.set()
        release.wait(3)

    manager = FlowManager()
    worker = threading.Thread(target=held_worker, name="existing-main-p202", daemon=True)
    manager._threads[202] = worker
    manager._stop_signals[202] = threading.Event()
    worker.start()
    assert entered.wait(1)
    join = worker.join
    monkeypatch.setattr(worker, "join", lambda timeout=None: join(0.01))
    try:
        report = manager.stop_project_flow(202)
        assert report["registered_workers_closed"] is False
        assert manager.is_project_running(202)
        assert manager._threads[202] is worker
    finally:
        release.set()
        join(1)
    report = manager.stop_project_flow(202)
    assert report["registered_workers_closed"] is True
    assert not manager.is_project_running(202)








async def test_direct_native_request_waits_for_observed_legacy_thread_exit(
    service_setup,
):
    """Task-level native submission cannot bypass live legacy controllers; retry starts only the original queued request after the actual thread exits."""
    import threading

    from backend.api.flow_manager import FlowManager
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    s = service_setup
    release = threading.Event()
    worker = threading.Thread(target=lambda: release.wait(5))
    worker.start()
    manager = FlowManager()
    manager._threads[101] = worker
    native = ControlledInference(s)
    native.release.set()
    try:
        service = coordinator(s, native, legacy_active=manager.is_project_running)
        async with service:
            run = await service.submit(s.c.spec)
            assert run.status == "queued" and run.attempt_id is None
            assert run.issue["code"] == "legacy_owner_active"
            assert run.issue["inference_started"] is False
            assert await service.submit(s.c.spec) == run
            assert native.prompts == []
            assert (
                s.c.conn.execute("SELECT count(*)FROM runtime_attempts").fetchone()[0]
                == 0
            )
            release.set()
            worker.join(1)
            assert not manager.is_project_running(101)
            await service.retry_start(
                project_id=101,
                run_id=run.run_id,
                expected_fence=run.fence,
                context_version=run.context_version,
                operation_key="after-observed-old-exit",
            )
            await service.wait(run.run_id)
            assert len(native.prompts) == 1
            assert (
                s.c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 1
            )
            assert (
                s.c.conn.execute(
                    "SELECT count(*)FROM runtime_inference_dispatches"
                ).fetchone()[0]
                == 1
            )
    finally:
        release.set()
        worker.join(1)


async def test_failed_legacy_liveness_observation_never_grants_native_start(
    service_setup,
):
    """An observation error is unresolved closure, not proof that no competing controller remains."""
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    s = service_setup
    native = ControlledInference(s)

    def unknown(project_id):
        """Simulate an unavailable registered-controller observation."""
        raise RuntimeError("Unavailable controller observation")

    async with coordinator(s, native, legacy_active=unknown) as service:
        run = await service.submit(s.c.spec)
        assert run.status == "queued" and run.attempt_id is None
        assert run.issue["code"] == "legacy_owner_active"
        assert run.issue["inference_started"] is False
        assert native.prompts == []


async def test_project_stop_api_discloses_unclosed_legacy_controller(
    coordination, monkeypatch
):
    """The public stop response reports pending legacy closure instead of turning a paused label into evidence that a worker ended."""
    import threading

    from backend.api.flow_manager import FlowManager
    from backend.api.routes import projects

    release = threading.Event()
    worker = threading.Thread(target=lambda: release.wait(3))
    worker.start()
    join = worker.join
    monkeypatch.setattr(worker, "join", lambda timeout=None: join(0.01))
    manager = FlowManager()
    manager._threads[202] = worker
    monkeypatch.setattr(projects, "flow_manager", manager)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runtime_service=None))
    )
    try:
        response = await projects.stop_project(202, request)
        assert response["legacy_control"]["registered_workers_closed"] is False
        assert "cierre" in response["message"]
        assert response["status"] == "paused" and manager.is_project_running(202)
    finally:
        release.set()
        join(1)
        manager.stop_project_flow(202)


