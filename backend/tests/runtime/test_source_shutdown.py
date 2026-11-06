"""Coordinator shutdown must drain every worker family even when source-receipt persistence fails; inference here is controlled, not physical closure evidence."""

import asyncio

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator
from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414


@pytest.mark.timeout(30)
async def test_source_shutdown_error_cannot_skip_native_worker_withdrawal(service_setup):
    """A source cleanup failure propagates only after the actual coordinator has withdrawn and drained its already-registered native adapter worker."""
    s=service_setup;native=ControlledInference(s);runtime=coordinator(s,native)

    class UnavailableSourceReceipts:
        """Model only the source family reporting failed SQL persistence after it drained its own physical handles."""

        async def close(self):
            """Report an original source-receipt failure; this must not prevent independent native worker teardown."""
            raise RunConflict('Controlled unavailable source receipt')

    with pytest.raises(RunConflict,match='Controlled unavailable source receipt'):
        async with runtime:
            run=await runtime.submit(s.c.spec,repository_id=11)
            await asyncio.wait_for(native.started.wait(),5)
            worker=runtime._workers[run.run_id].task
            runtime._sources=UnavailableSourceReceipts()
    assert native.interrupted.is_set() and native.closed.is_set()
    assert worker.done()
    assert runtime._lock_fd is None


@pytest.mark.timeout(30)
async def test_shutdown_drains_source_admission_before_releasing_store_owner(owned_config, monkeypatch):
    """An in-flight preparation cannot enqueue an administrative worker after source shutdown took its final handle snapshot and released store ownership."""
    from threading import Event

    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.git.source_operations import SourceRequest

    c=owned_config;app=create_app();runtime=configured_runtime(app.state.live_grants,app=app)
    sources=runtime.sources;entered=Event();release=Event();closing_started=asyncio.Event();closing_finished=asyncio.Event()
    prepare=sources.records.prepare;close=sources.close

    def held_prepare(*args, **kwargs):
        """Hold the actual admission handoff before its real transaction, without starting Git or fabricating closure evidence."""
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Controlled preparation was not released')
        return prepare(*args,**kwargs)

    async def held_worker(*_args, **_kwargs):
        """Represent a registered finite worker handle only; no process, lease, file or model is created in this admission-order test."""
        await asyncio.Event().wait()

    async def observed_close():
        """Observe the real source shutdown boundary; finishing before admission drains demonstrates the ownership defect."""
        closing_started.set()
        try:
            await close()
        finally:
            closing_finished.set()

    monkeypatch.setattr(sources.records,'prepare',held_prepare)
    monkeypatch.setattr(sources,'_run',held_worker)
    monkeypatch.setattr(sources,'close',observed_close)
    await runtime.__aenter__()
    submitting=asyncio.create_task(sources.submit(202,'shutdown-admission',SourceRequest(mode='create',name='shutdown-admission',path=str(c.s.root/'shutdown-admission'),branch='main')))
    assert await asyncio.to_thread(entered.wait,5)
    shutting_down=asyncio.create_task(runtime.__aexit__(None,None,None))
    try:
        await asyncio.wait_for(closing_started.wait(),5)
        closed_before_admission=closing_finished.is_set()
    finally:
        release.set()
        results=await asyncio.gather(submitting,shutting_down,return_exceptions=True)
        await asyncio.gather(close(),return_exceptions=True)
    assert not closed_before_admission
    assert not any(isinstance(result,BaseException) for result in results)
    assert all(task.done() for task in sources._workers.values())
    assert sources.records.read(202,'shutdown-admission')['status']=='stopped'
    assert runtime._lock_fd is None and not (c.s.root/'shutdown-admission').exists()
