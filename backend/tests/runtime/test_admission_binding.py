"""Admission preserves the owner's repository choice; retries cannot retarget it."""

import asyncio

import pytest

from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator


def add_repository(setup):
    other = setup.root / "beta"
    other.mkdir()
    setup.c.conn.execute(
        "INSERT INTO repositories(id,project_id,name,local_path) VALUES(12,101,'beta',?)",
        (str(other),),
    )
    setup.c.conn.commit()
    return other


async def queue_after_preparation_failure(setup, monkeypatch):
    from backend.runtime.peer_registry import AttemptPeers

    service = coordinator(setup, ControlledInference(setup))
    with monkeypatch.context() as patch:
        patch.setattr(
            AttemptPeers,
            "_prepare",
            classmethod(
                lambda *args: (_ for _ in ()).throw(
                    RuntimeError("Preparation unavailable")
                )
            ),
        )
        async with service:
            run = await service.submit(setup.c.spec)
            await service.wait(run.run_id)
    assert setup.c.store.get(101, run.run_id).status == "queued"
    return run


async def test_an_admission_key_cannot_change_its_explicit_repository(service_setup):
    from backend.runtime.contracts import RunConflict

    s = service_setup
    add_repository(s)
    native = ControlledInference(s)
    async with coordinator(s, native) as service:
        run = await service.submit(s.c.spec, repository_id=11)
        await asyncio.wait_for(native.started.wait(), 2)
        with pytest.raises(RunConflict, match="intent"):
            await service.submit(s.c.spec, repository_id=12)
        assert s.c.store.get(101, run.run_id).repository_id == 11


async def test_duplicate_admission_only_reads_a_queued_receipt_even_when_catalog_changes(
    service_setup, monkeypatch
):
    s = service_setup
    run = await queue_after_preparation_failure(s, monkeypatch)
    add_repository(s)
    native = ControlledInference(s)
    async with coordinator(s, native) as service:
        receipt = await service.submit(s.c.spec)
        assert receipt.run_id == run.run_id and receipt.status == "queued"
        assert not service._workers and not native.prompts


async def test_explicit_queued_retry_after_restart_uses_the_original_auto_selected_repository(
    service_setup, monkeypatch
):
    s = service_setup
    run = await queue_after_preparation_failure(s, monkeypatch)
    add_repository(s)
    native = ControlledInference(s)
    native.release.set()
    async with coordinator(s, native) as service:
        await service.retry_start(
            project_id=101,
            run_id=run.run_id,
            expected_fence=0,
            context_version=1,
            operation_key="explicit-retry",
        )
        await service.wait(run.run_id)
        result = s.c.store.get(101, run.run_id)
        assert result.repository_id == 11 and result.repository_name == "alpha"
        assert result.status == "needs_review" and len(native.prompts) == 1
        await service.retry_start(
            project_id=101,
            run_id=run.run_id,
            expected_fence=0,
            context_version=1,
            operation_key="explicit-retry",
        )
        assert len(native.prompts) == 1


@pytest.mark.parametrize("change", ["registration", "directory"])
async def test_a_queued_request_cannot_follow_a_changed_repository_or_replaced_directory(
    service_setup, monkeypatch, change
):
    s = service_setup
    run = await queue_after_preparation_failure(s, monkeypatch)
    if change == "registration":
        other = add_repository(s)
        s.c.conn.execute(
            "UPDATE repositories SET local_path=? WHERE id=11", (str(other),)
        )
        s.c.conn.commit()
    else:
        s.workspace.rename(s.root / "original-alpha")
        s.workspace.mkdir()
    native = ControlledInference(s)
    async with coordinator(s, native) as service:
        result = await service.retry_start(
            project_id=101,
            run_id=run.run_id,
            expected_fence=0,
            context_version=1,
            operation_key="try-original",
        )
        assert result.status == "queued" and result.repository_id == 11
        assert (
            result.issue["code"] == "workspace_changed"
            and result.issue["inference_started"] is False
        )
        assert not service._workers and not native.prompts
        assert (
            s.c.conn.execute("SELECT COUNT(*) FROM runtime_attempts").fetchone()[0] == 0
        )


async def test_legacy_queued_receipt_is_readable_but_cannot_gain_an_inferred_repository(
    service_setup,
):
    s = service_setup
    run = s.c.store.admit(s.c.spec)
    native = ControlledInference(s)
    async with coordinator(s, native) as service:
        receipt = await service.submit(s.c.spec, repository_id=11)
        assert receipt.run_id == run.run_id and receipt.repository_id is None
        result = await service.retry_start(
            project_id=101,
            run_id=run.run_id,
            expected_fence=0,
            context_version=1,
            operation_key="old-request",
        )
        assert result.issue["code"] == "binding_missing"
        assert result.issue["inference_started"] is None
        assert not service._workers and not native.prompts


async def test_full_capacity_returns_the_durable_queued_request_without_automatic_dispatch(
    service_setup,
):
    from dataclasses import replace

    s = service_setup
    native = ControlledInference(s)
    async with coordinator(s, native) as service:
        first = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        second_spec = replace(s.c.spec, task_id=1002, operation_key="queued-second")
        second = await service.submit(second_spec)
        assert second.status == "queued" and second.issue["code"] == "capacity"
        native.release.set()
        await service.wait(first.run_id)
        assert (await service.submit(second_spec)).status == "queued"
        assert len(native.prompts) == 1


async def test_shutdown_during_workspace_validation_cannot_leave_a_late_worker(
    service_setup, monkeypatch
):
    import threading

    from backend.runtime.contracts import RunConflict

    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    entered, release = threading.Event(), threading.Event()
    validate = service.workspaces.validate

    def blocked(*args):
        entered.set()
        if not release.wait(5):
            raise TimeoutError("Test did not release validation")
        return validate(*args)

    monkeypatch.setattr(service.workspaces, "validate", blocked)
    await service.__aenter__()
    pending = asyncio.create_task(service.submit(s.c.spec))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        await service.__aexit__(None, None, None)

        release.set()
        with pytest.raises(RunConflict):
            await pending
        assert not service._workers and not native.prompts
    finally:
        release.set()
        if not pending.done():
            await asyncio.gather(pending, return_exceptions=True)
        await service.__aexit__(None, None, None)


async def test_owner_retry_endpoint_rejects_retargeting_and_keeps_its_receipt_after_start(
    service_setup, monkeypatch
):
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s = service_setup
    run = await queue_after_preparation_failure(s, monkeypatch)
    native = ControlledInference(s)
    native.release.set()
    service = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=service,
    )
    path = f"/api/projects/101/runs/{run.run_id}/retry-start"
    body = {"operation_key": "owner-start", "expected_fence": 0, "context_version": 1}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as anonymous:
            assert (await anonymous.post(path, json=body)).status_code == 401
        async with owner_client(app) as owner:
            assert (
                await owner.post(path, json={**body, "repository_id": 12})
            ).status_code == 422
            started = await owner.post(path, json=body)
            assert started.status_code == 202, started.text
            assert (
                started.json()["repository_id"] == 11
                and str(s.root) not in started.text
            )
            await service.wait(run.run_id)
            duplicate = await owner.post(path, json=body)
            assert (
                duplicate.status_code == 202
                and duplicate.json()["status"] == "needs_review"
            )
            assert (
                await owner.post(path, json={**body, "expected_fence": 1})
            ).status_code == 409
            assert (
                await owner.post(path.replace("/101/", "/202/"), json=body)
            ).status_code == 404
            assert len(native.prompts) == 1


def test_binding_and_conversation_roll_back_when_admission_event_fails(service_setup):
    import sqlite3

    from backend.runtime.workspaces import WorkspaceRegistry

    s = service_setup
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101)
    s.c.conn.execute(
        "CREATE TRIGGER reject_bound_admission BEFORE INSERT ON events_log WHEN new.event_type='run.admitted' BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    s.c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        s.c.store.admit(
            s.c.spec, conversation_thread="bound-conversation", binding=binding
        )
    for table in (
        "runtime_runs",
        "runtime_workspace_bindings",
        "runtime_commands",
        "conversation_threads",
        "chat_messages",
    ):
        assert s.c.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0


def test_an_issue_without_its_event_does_not_commit(coordination):
    import sqlite3

    c = coordination
    run = c.store.admit(c.spec)
    c.conn.execute(
        "CREATE TRIGGER reject_issue BEFORE INSERT ON events_log WHEN new.event_type='run.issue' BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        c.store.record_issue(
            101,
            run.run_id,
            {
                "code": "preparation_failed",
                "message": "Guardada sin iniciar",
                "next_action": "retry_start",
                "inference_started": False,
            },
        )
    assert c.store.get(101, run.run_id).issue is None


async def test_a_changed_task_type_supersedes_queued_work_before_retry(
    service_setup, monkeypatch
):
    s = service_setup
    run = await queue_after_preparation_failure(s, monkeypatch)
    s.c.conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    s.c.conn.commit()
    native = ControlledInference(s)
    native.release.set()
    async with coordinator(s, native) as service:
        from backend.runtime.contracts import RunConflict

        with pytest.raises(RunConflict):
            await service.retry_start(
                project_id=101,
                run_id=run.run_id,
                expected_fence=0,
                context_version=1,
                operation_key="changed-type",
            )
        result = s.c.store.get(101, run.run_id)
        assert result.status == "superseded"
        assert not native.prompts


@pytest.mark.parametrize("stage", ["setup", "dispatch_unknown", "started"])
async def test_start_explanation_distinguishes_no_dispatch_from_unknown_and_observed_inference(
    service_setup, stage
):
    """Keep inference uncertainty separate from the independently observed closure of the original peers."""
    import json
    from contextlib import asynccontextmanager
    from dataclasses import asdict

    class Failing(ControlledInference):
        @asynccontextmanager
        async def open(self, **kwargs):
            if stage == "setup":
                raise RuntimeError("PRIVATE_DIAGNOSTIC_MUST_STAY_PRIVATE")
            async with super().open(**kwargs) as session:
                yield session

        async def run(self, prompt, *, on_started, on_event):
            if stage == "started":
                await on_started(self.thread_id, "observed-turn")
            raise RuntimeError("PRIVATE_DIAGNOSTIC_MUST_STAY_PRIVATE")

    s = service_setup
    async with coordinator(s, Failing(s)) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        result = s.c.store.get(101, run.run_id)
        assert result.issue["code"] == "runtime_failed"
        expected = False if stage == "setup" else True if stage == "started" else None
        assert result.issue["inference_started"] is expected
        assert result.issue["closure_confirmed"] is (stage != "setup")
        if stage != "setup":
            assert "cierre no confirmado" not in result.issue["message"]
            assert "No se pudo confirmar el cierre" not in result.issue["message"]
            assert "se comprobó el cierre" in result.issue["message"]
        if stage == "dispatch_unknown":
            assert "No se pudo confirmar si se inició inferencia" in result.issue["message"]
        assert "PRIVATE_DIAGNOSTIC" not in json.dumps(asdict(result))
        assert result.status in ("failed", "reconciling")
        assert (
            s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            != "done"
        )
