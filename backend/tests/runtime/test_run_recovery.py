"""Reconcile original effects and closures, never replay an inference request."""

from dataclasses import replace

import pytest


def lost_attempt(c):
    from backend.runtime.codex_session import ExecutionLimits
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.recovery import RunRecovery

    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "lost-owner")
    peers = AttemptPeers.prepare(c.store, lease)
    c.store.bind_native(lease, thread_id="original-thread", turn_id="original-turn")
    c.store.reserve_inference(
        lease,
        workspace="/controlled-fixture",
        catalog_hash="a" * 64,
        limits=ExecutionLimits(5, 3, 1, 10, 100),
        project_turn_limit=20,
        project_token_limit=100,
        model="fixture-model",
    )
    c.store.recover_owners("new-owner")
    current = c.store.get(101, run.run_id)
    command = {
        "project_id": 101,
        "run_id": run.run_id,
        "attempt_id": lease.attempt_id,
        "expected_fence": current.fence,
        "operation_key": "recover-original",
    }
    return RunRecovery(c.store), peers, lease, command


def test_registered_scope_cannot_be_retired_from_a_caller_boolean(coordination):
    from backend.runtime.contracts import RunConflict
    from backend.runtime.peer_registry import AttemptPeers

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "owner")
    AttemptPeers.prepare(c.store, lease)
    with pytest.raises(RunConflict, match="peer"):
        c.store.retire_inference(lease, outcome="failed")


def test_recovery_proves_closure_keeps_unknown_budget_and_does_not_accept(coordination):
    from backend.runtime.codex_session import ExecutionLimits
    from backend.runtime.contracts import RunConflict

    c = coordination
    recovery, peers, _lease, command = lost_attempt(c)
    result = recovery.reconcile(**command)
    assert result["status"] == "failed" and result["inference_started"] is False
    assert peers.closed()
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 1
    )
    dispatch = c.conn.execute("SELECT * FROM runtime_inference_dispatches").fetchone()
    assert dispatch["status"] == "unknown" and dispatch["token_ceiling"] == 100
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    assert recovery.reconcile(**command) == result
    next_run = c.store.admit(replace(c.spec, operation_key="explicit-next"))
    next_lease = c.store.claim(101, next_run.run_id, "new-owner")
    c.store.bind_thread(next_lease, thread_id="explicit-next-thread")
    with pytest.raises(RunConflict, match="budget"):
        c.store.reserve_inference(
            next_lease,
            workspace="/controlled-fixture",
            catalog_hash="a" * 64,
            limits=ExecutionLimits(5, 3, 1, 10, 100),
            project_turn_limit=20,
            project_token_limit=100,
            model="fixture-model",
        )


@pytest.mark.parametrize(
    "control,outcome", [("stop", "cancelled"), ("correction", "superseded")]
)
def test_recovery_result_uses_current_durable_control_not_callback_order(
    coordination, control, outcome
):
    c = coordination
    recovery, peers, _lease, command = lost_attempt(c)
    recovery.begin(**command)
    if control == "stop":
        c.store.cancel(101, command["run_id"])
    else:
        c.store.correct_context(
            project_id=101,
            task_id=1001,
            expected_version=1,
            operation_key="new-context",
            statement="Usa otra fuente",
            source_kind="user_message",
            source_reference="owner:example",
        )
    for peer in peers.ids.values():
        peers.registry.close(peer)
    assert recovery.complete(**command)["status"] == outcome


def test_recovery_rejects_stale_identity_legacy_scope_and_incomplete_proof(
    coordination,
):
    from backend.runtime.contracts import RunConflict, RunNotFound

    recovery, _peers, _lease, command = lost_attempt(coordination)
    with pytest.raises(RunNotFound):
        recovery.begin(**{**command, "project_id": 202})
    with pytest.raises(RunConflict):
        recovery.begin(**{**command, "attempt_id": "another-attempt"})
    recovery.begin(**command)
    with pytest.raises(RunConflict, match="peer"):
        recovery.complete(**command)
    coordination.conn.execute("DELETE FROM runtime_peer_scopes")
    coordination.conn.commit()
    with pytest.raises(RunConflict, match="protocol"):
        recovery.reconcile(**command)


def test_failed_recovery_receipt_commit_rolls_back_state_but_keeps_closure_evidence(
    coordination,
):
    c = coordination
    recovery, peers, _lease, command = lost_attempt(c)
    recovery.begin(**command)
    for peer in peers.ids.values():
        peers.registry.close(peer)
    c.conn.execute(
        "CREATE TRIGGER reject_recovery_receipt BEFORE INSERT ON runtime_commands WHEN new.operation_key='recover-original' BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    c.conn.commit()
    with pytest.raises(Exception, match="injected"):
        recovery.complete(**command)
    assert c.store.get(101, command["run_id"]).status == "reconciling"
    assert peers.closed()
    c.conn.execute("DROP TRIGGER reject_recovery_receipt")
    c.conn.commit()
    assert recovery.reconcile(**command)["status"] == "failed"


async def test_owner_inspection_and_recovery_never_submit_a_turn(service_setup):
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )
    from backend.tests.runtime.test_workspace_delivery import owner_client

    setup = service_setup
    _recovery, _peers, _lease, command = lost_attempt(setup.c)
    native = ControlledInference(setup)
    service = coordinator(setup, native)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=service,
    )
    path = f"/api/projects/101/runs/{command['run_id']}/recovery"
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as anonymous:
            assert (await anonymous.get(path)).status_code == 401
        async with owner_client(app) as owner:
            before = await owner.get(path)
            assert before.status_code == 200, before.text
            assert before.json()["supported"] and before.json()["can_reconcile"]
            assert (
                "owner_pid" not in before.text
                and str(setup.c.database) not in before.text
            )
            body = {
                key: command[key]
                for key in ("operation_key", "attempt_id", "expected_fence")
            }
            result = await owner.post(path, json=body)
            assert result.status_code == 200, result.text
            assert (
                result.json()["local_execution_closed"]
                and not result.json()["inference_started"]
            )
            assert (await owner.post(path, json=body)).json() == result.json()
            assert (
                await owner.get(path.replace("projects/101", "projects/202"))
            ).status_code == 404
            assert native.prompts == []


@pytest.mark.parametrize("disconnect", [False, True])
async def test_owner_recovery_retires_process_before_busy_intent_commit(
    service_setup, tmp_path, disconnect
):
    import asyncio
    import os
    import select
    import time

    from backend.runtime.peer_process import _pidfd
    from backend.runtime.peer_registry import AttemptPeers
    from backend.tests.runtime.test_peer_ownership import cleanup, launch, wait_until
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    setup = service_setup
    c = setup.c
    c.now[0] = time.time()
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "old-owner", lease_seconds=120)
    peers = AttemptPeers.prepare(c.store, lease)
    marker = tmp_path / "ready"
    peer = peers.ids["native"]
    process = launch(
        peers.registry,
        peer,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(20)",
        marker,
    )
    fd = None
    try:
        await asyncio.to_thread(wait_until, marker.exists, process)
        fd = _pidfd(peers.registry.inspect(peer)["init_pid"])
        poller = select.poll()
        poller.register(fd, select.POLLIN | select.POLLHUP)
        async with coordinator(setup, ControlledInference(setup)) as service:
            current = c.store.get(101, run.run_id)
            c.conn.execute("BEGIN IMMEDIATE")
            task = asyncio.create_task(
                service.reconcile(
                    project_id=101,
                    run_id=run.run_id,
                    attempt_id=lease.attempt_id,
                    expected_fence=current.fence,
                    operation_key="recover-busy",
                )
            )
            try:
                assert await asyncio.to_thread(poller.poll, 1000), (
                    "Recovery waited for SQLite before local closure"
                )
                if disconnect:
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
            finally:
                c.conn.rollback()
                if disconnect:
                    await asyncio.wait_for(
                        service.reconcile(
                            project_id=101,
                            run_id=run.run_id,
                            attempt_id=lease.attempt_id,
                            expected_fence=current.fence,
                            operation_key="recover-busy",
                        ),
                        10,
                    )
                else:
                    await asyncio.wait_for(task, 10)
    finally:
        c.conn.rollback()
        if fd is not None:
            os.close(fd)
        cleanup(peers.registry, peer, process)


def test_recovery_restores_pending_question_without_resuming_a_native_handle(
    coordination,
):
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.questions import Question, QuestionSet
    from backend.runtime.recovery import RunRecovery
    from backend.runtime.sqlite_questions import SQLiteQuestionStore

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "lost-owner")
    AttemptPeers.prepare(c.store, lease)
    c.store.bind_native(lease, thread_id="old-thread", turn_id="old-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=c.spec.actor_id,
        permissions={"questions.ask"},
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    questions = SQLiteQuestionStore(c.store, c.research)
    asked = questions.ask(
        scope, "ask", QuestionSet((Question("base", "¿Qué base prefieres?"),))
    )
    c.store.recover_owners("new-owner")
    current = c.store.get(101, run.run_id)
    recovered = RunRecovery(c.store).reconcile(
        project_id=101,
        run_id=run.run_id,
        attempt_id=lease.attempt_id,
        expected_fence=current.fence,
        operation_key="recover-question",
    )
    assert recovered["status"] == "waiting_input"
    assert (
        questions.answer(
            project_id=101,
            task_id=1001,
            request_id=asked["request_id"],
            expected_version=1,
            operation_key="answer",
            answers={"base": "200"},
        )
        == 2
    )
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 1


async def test_same_recovery_intent_rechecks_a_transient_failed_closure(
    service_setup, monkeypatch
):
    from backend.runtime.peer_process import PeerUncertain
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    setup = service_setup
    _recovery, peers, _lease, command = lost_attempt(setup.c)
    service = coordinator(setup, ControlledInference(setup))
    original = service.recovery.peers.close
    failed = []

    def temporary_denial(peer_id):
        if peer_id == peers.ids["native"] and not failed:
            failed.append(peer_id)
            raise PeerUncertain("Temporary kernel observation failure")
        return original(peer_id)

    monkeypatch.setattr(service.recovery.peers, "close", temporary_denial)
    async with service:
        with pytest.raises(PeerUncertain):
            await service.reconcile(**command)
        assert setup.c.store.get(101, command["run_id"]).status == "reconciling"
        assert (await service.reconcile(**command))["status"] == "failed"
        assert peers.closed()
