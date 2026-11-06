"""Native project admission excludes competing legacy activation/recovery; thread tests distinguish a stop request from observed termination."""

from types import SimpleNamespace

import pytest


def admitted_project(coordination):
    """Persist actual native intent, leaving the separate legacy-looking code task without a native run."""
    c = coordination
    run = c.store.admit(c.spec)
    c.conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status,assigned_to)VALUES(1003,101,'code','Old partial work','in_progress','legacy-worker'),(2003,202,'code','Other project','in_progress','legacy-other')"
    )
    c.conn.commit()
    return c, run


def test_native_project_fences_other_task_legacy_claim_without_minting_work(
    coordination,
):
    """Project owner evidence also excludes a fresh task; task ID absence must not reopen an old engine in the same project."""
    from backend.runtime.legacy_handoff import legacy_event_handoff

    c, run = admitted_project(coordination)
    hint = legacy_event_handoff(101, 1003)
    assert hint["delivery"] == "native_owner_handoff"
    assert hint["native_runs"] == []
    assert hint["event_authorizes_work"] is False
    assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 1
    assert c.store.get(101, run.run_id).status == "queued"


def test_actual_old_engine_refuses_native_project_before_model_configuration(
    coordination, monkeypatch
):
    """The old model entry cannot spend another turn merely because it was called outside the migrated flow handlers."""
    from backend.engine.loop_engine import LoopEngine

    admitted_project(coordination)

    def forbidden():
        """Fail if provider setup is reached before owner exclusion."""
        pytest.fail("Legacy model configuration reached")

    monkeypatch.setattr("backend.config.llm.get_litellm_params", forbidden)
    with pytest.raises(ValueError, match="[Nn]ative|owner"):
        LoopEngine().execute(
            SimpleNamespace(project_id=101, agent_id="legacy-worker"),
            ("Resume old work", "A report"),
        )


@pytest.mark.parametrize(
    "handler,event_type",
    [
        ("MessageHandler", "message_received"),
        ("HealthCheckHandler", "health_check"),
        ("ProgressEvalHandler", "all_tasks_done"),
    ],
)
def test_native_project_generic_events_are_owner_hints_not_inference(
    coordination, monkeypatch, handler, event_type
):
    """An unscoped message or inferred stagnation/completion must not choose a task or run a legacy team lead."""
    from backend.autonomy import handlers

    c, _run = admitted_project(coordination)

    def forbidden(*args, **kwargs):
        """Detect a competing inference or message side effect."""
        pytest.fail("Legacy generic dispatch reached")

    monkeypatch.setattr(
        "backend.flows.helpers.message_dispatcher.dispatch_message", forbidden
    )
    monkeypatch.setattr("backend.flows.helpers.stagnation.get_stuck_tasks", forbidden)
    monkeypatch.setattr("backend.flows.helpers.send_agent_message", forbidden)
    result = getattr(handlers, handler)().execute(
        {
            "id": 801,
            "project_id": 101,
            "agent_id": "legacy-worker",
            "event_type": event_type,
            "payload_json": "{}",
        }
    )
    assert result["delivery"] == "native_owner_handoff"
    assert result.get("task_id") is None
    assert result["event_authorizes_work"] is False
    assert c.conn.execute(
        "SELECT status,assigned_to FROM tasks WHERE id=1003"
    ).fetchone()[:] == ("in_progress", "legacy-worker")


def test_dead_legacy_worker_and_shutdown_cannot_reset_native_project_tasks(
    coordination,
):
    """Legacy heartbeat/thread assumptions cannot clear a native project's task assignment or put work back in a claim queue."""
    from backend.api.flow_manager import FlowManager
    from backend.autonomy.liveness import recover_dead_agent_task

    c, _run = admitted_project(coordination)
    assert recover_dead_agent_task(1003, "legacy-worker") is False
    FlowManager().stop_project_flow(101)
    assert c.conn.execute(
        "SELECT status,assigned_to FROM tasks WHERE id=1003"
    ).fetchone()[:] == ("in_progress", "legacy-worker")
    assert recover_dead_agent_task(2003, "legacy-other") is False
    assert c.conn.execute(
        "SELECT status,assigned_to FROM tasks WHERE id=2003"
    ).fetchone()[:] == ("in_progress", "legacy-other")


@pytest.mark.parametrize("entry", ["flow", "loop", "loop_manager"])
def test_actual_legacy_starts_do_not_open_workers_in_native_project(
    coordination, monkeypatch, entry
):
    """Native project exclusion happens before listener/roster/thread startup or stale-event clearing."""
    from backend.api.flow_manager import FlowManager
    from backend.autonomy.agent_loop import AgentLoop, AgentLoopManager

    admitted_project(coordination)

    def forbidden(*args, **kwargs):
        """Catch new legacy worker/listener construction."""
        pytest.fail("Legacy worker start reached")

    monkeypatch.setattr("backend.api.flow_manager.ListenerManager", forbidden)
    monkeypatch.setattr("backend.autonomy.agent_loop.threading.Thread", forbidden)
    target = (
        FlowManager()
        if entry == "flow"
        else AgentLoop("legacy-worker", 101, "developer")
        if entry == "loop"
        else AgentLoopManager(101)
    )
    result = (
        target.start_project_flow(101)
        if entry == "flow"
        else target.start()
        if entry == "loop"
        else target.start_all()
    )
    assert result["delivery"] == "native_owner_handoff"


def test_old_engine_rechecks_after_a_model_reply_before_using_its_output(
    coordination, monkeypatch
):
    """Native ownership appearing during a legacy model call stops interpretation/tools and the next loop instead of treating old context as fresh authority."""
    from dataclasses import replace

    from backend.engine.loop_engine import LoopEngine

    c = coordination
    monkeypatch.setattr(
        "backend.config.llm.get_litellm_params", lambda: {"model": "controlled-legacy"}
    )
    monkeypatch.setattr(
        "backend.config.model_capabilities.get_model_capabilities",
        lambda: SimpleNamespace(supports_function_calling=True),
    )

    def reply(*args, **kwargs):
        """Commit real native intent while the one controlled legacy call is in flight."""
        c.store.admit(
            replace(
                c.spec,
                project_id=202,
                task_id=2002,
                operation_key="native-during-old-reply",
            )
        )
        return object()  # Cannot be consumed; owner exclusion must happen first.

    monkeypatch.setattr("backend.engine.loop_engine.call_llm", reply)
    agent = SimpleNamespace(
        project_id=202,
        agent_id="legacy-other",
        backstory="Legacy fixture",
        tools=[],
        name="Fixture",
        role="developer",
    )
    with pytest.raises(ValueError, match="[Nn]ative|owner"):
        LoopEngine().execute(agent, ("Old request", "Old output"), verbose=False)


def test_agent_stop_timeout_retains_the_live_thread_until_actual_exit(
    coordination, monkeypatch
):
    """A join timeout cannot erase the only live worker reference or be reported as physical closure."""
    import threading

    from backend.autonomy.agent_loop import AgentLoop

    release, entered = threading.Event(), threading.Event()

    def held_worker():
        """Remain physically alive after a stop request until this test releases it."""
        entered.set()
        release.wait(3)

    worker = threading.Thread(target=held_worker)
    worker.start()
    assert entered.wait(1)
    join = worker.join
    monkeypatch.setattr(worker, "join", lambda timeout=None: join(0.01))
    loop = AgentLoop("held-legacy", 101, "developer")
    loop._thread = worker
    try:
        assert loop.stop() is False
        assert loop.is_running and loop._thread is worker
    finally:
        release.set()
        join(1)
    assert loop.stop() is True
    assert not loop.is_running


def test_legacy_event_ack_preserves_message_and_cannot_call_a_handler_in_native_project(
    coordination,
):
    """Completing a documentary hint in the old queue is distinct from doing task work or promoting the old message to an owner instruction."""
    import json

    from backend.autonomy.agent_loop import AgentLoop

    c, _run = admitted_project(coordination)
    payload = json.dumps(
        {"from_agent": "legacy-unverified-label", "message": "Do it now"}
    )
    eid = c.conn.execute(
        "INSERT INTO agent_events(project_id,agent_id,event_type,payload_json,status)VALUES(101,'legacy-worker','message_received',?,'pending')RETURNING id",
        (payload,),
    ).fetchone()[0]
    c.conn.commit()
    loop = AgentLoop("legacy-worker", 101, "developer")
    loop.handlers["message_received"] = SimpleNamespace(
        execute=lambda event: pytest.fail("Competing legacy handler reached")
    )
    hint = loop._execute_event(
        {
            "id": eid,
            "project_id": 101,
            "agent_id": "legacy-worker",
            "event_type": "message_received",
            "payload_json": payload,
        }
    )
    assert hint["delivery"] == "native_owner_handoff"
    row = c.conn.execute(
        "SELECT status,payload_json,progress_json FROM agent_events WHERE id=?", (eid,)
    ).fetchone()
    assert row["status"] == "completed" and row["payload_json"] == payload
    assert json.loads(row["progress_json"])["task_completed"] is False
    assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 1
    assert c.conn.execute("SELECT count(*)FROM runtime_owner_notes").fetchone()[0] == 0


def test_foreign_stored_event_cannot_be_acknowledged_using_a_native_project_label(
    coordination,
):
    """The stored project/recipient outrank an incoming event dictionary's claimed context."""
    from backend.autonomy.agent_loop import AgentLoop

    c, _run = admitted_project(coordination)
    eid = c.conn.execute(
        "INSERT INTO agent_events(project_id,agent_id,event_type,payload_json,status)VALUES(202,'legacy-other','message_received','{}','pending')RETURNING id"
    ).fetchone()[0]
    c.conn.commit()
    loop = AgentLoop("legacy-worker", 101, "developer")
    with pytest.raises(ValueError, match="scope|project|recipient"):
        loop._execute_event(
            {
                "id": eid,
                "project_id": 101,
                "agent_id": "legacy-worker",
                "event_type": "message_received",
                "payload_json": "{}",
            }
        )
    assert (
        c.conn.execute("SELECT status FROM agent_events WHERE id=?", (eid,)).fetchone()[
            0
        ]
        == "pending"
    )


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


def test_loop_manager_does_not_erase_a_worker_that_ignored_stop_timeout(
    coordination, monkeypatch
):
    """The project registry and manager retain the live child until a later observation proves thread exit."""
    import threading

    from backend.api.runtime_dependencies import _legacy_project_active
    from backend.autonomy import agent_loop

    release = threading.Event()
    worker = threading.Thread(target=lambda: release.wait(3))
    worker.start()
    join = worker.join
    monkeypatch.setattr(worker, "join", lambda timeout=None: join(0.01))
    loop = agent_loop.AgentLoop("held-legacy", 101, "developer")
    loop._thread = worker
    manager = agent_loop.AgentLoopManager(101)
    manager._loops = {"held-legacy": loop}
    agent_loop._loop_managers[101] = manager
    try:
        assert _legacy_project_active(101) is True
        manager.stop_signal()
        assert manager.stop_join() is False
        assert manager.is_running
        assert agent_loop.get_loop_manager(101) is manager
        assert manager._loops["held-legacy"] is loop
    finally:
        release.set()
        join(1)
        manager.stop_join()
    assert not manager.is_running
    assert agent_loop.get_loop_manager(101) is None


def test_legacy_stop_signal_during_model_reply_blocks_following_effects(
    coordination, monkeypatch
):
    """A cooperative stop is checked after the current request returns, without treating its completion as permission to continue."""
    import threading

    from backend.engine.base import AgentKilledError
    from backend.engine.loop_engine import LoopEngine
    from backend.runtime.legacy_scope import legacy_stop_scope

    signal = threading.Event()
    monkeypatch.setattr(
        "backend.config.llm.get_litellm_params", lambda: {"model": "controlled-legacy"}
    )
    monkeypatch.setattr(
        "backend.config.model_capabilities.get_model_capabilities",
        lambda: SimpleNamespace(supports_function_calling=True),
    )

    def forbidden(*args, **kwargs):
        """A requested Stop must prevent even the first legacy provider call."""
        pytest.fail("Stopped legacy producer cannot call a model")

    monkeypatch.setattr("backend.engine.loop_engine.call_llm", forbidden)
    agent = SimpleNamespace(project_id=202, agent_id="legacy-other")
    signal.set()
    with legacy_stop_scope(202, signal), pytest.raises((AgentKilledError, ValueError)):
        LoopEngine().execute(agent, ("Old request", "Old output"), verbose=False)


def test_legacy_dispatch_uses_stored_message_and_clears_an_inherited_task_scope(
    coordination,
):
    """An incoming dictionary and prior thread context cannot replace stored user evidence or invent the task of a project-only message."""
    import json

    from backend.autonomy.agent_loop import AgentLoop
    from backend.tools.base.context import (
        get_context,
        get_context_for_agent,
        set_context,
    )

    c = coordination
    original = json.dumps(
        {
            "from_agent": "attributed-user-label",
            "message": "I supplied an example, not approval.",
        }
    )
    eid = c.conn.execute(
        "INSERT INTO agent_events(project_id,agent_id,event_type,payload_json,status)VALUES(202,'legacy-other','message_received',?,'pending')RETURNING id",
        (original,),
    ).fetchone()[0]
    c.conn.commit()
    loop = AgentLoop("legacy-other", 202, "developer")
    observed = []

    def read_only_handler(event):
        """Inspect actual evidence and scope without model work or mutations."""
        observed.append(
            (
                event["payload_json"],
                get_context().project_id,
                get_context().task_id,
                get_context().agent_run_id,
                get_context().workspace_path,
                get_context_for_agent("legacy-other").resume_state,
            )
        )

    loop.handlers["message_received"] = SimpleNamespace(execute=read_only_handler)
    set_context(
        project_id=101,
        agent_id="legacy-other",
        task_id=1001,
        agent_run_id="unrelated-old-run",
        workspace_path="/unrelated/project",
        resume_state={"old": "checkpoint"},
    )
    try:
        loop._execute_event(
            {
                "id": eid,
                "project_id": 202,
                "agent_id": "legacy-other",
                "event_type": "message_received",
                "payload_json": json.dumps(
                    {"message": "Fabricated shared context/approval"}
                ),
            }
        )
        assert observed == []
        assert c.conn.execute("SELECT payload_json FROM agent_events WHERE id=?", (eid,)).fetchone()[0] == original
    finally:
        set_context(project_id=None, agent_id=None, task_id=None)


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


def test_wired_legacy_callbacks_remain_registered_until_explicit_unsubscribe(
    coordination,
):
    """An empty listener-thread list is insufficient while its project scheduling callbacks are still wired."""
    from backend.api.flow_manager import FlowManager
    from backend.flows.event_bus import EventBus
    from backend.flows.event_listeners import ListenerManager

    c = coordination
    listeners = ListenerManager(101, bus=EventBus())
    # Simulate subscriptions installed by a prior version, not a new activation.
    listeners._wired = True
    listeners.bus.subscribe("task_created", listeners._create_task_available_events)
    c.store.admit(c.spec)
    manager = FlowManager()
    manager._listeners[101] = listeners
    assert manager.is_project_running(101)
    assert manager.stop_project_flow(101)["registered_workers_closed"] is True
    assert not manager.is_project_running(101)
