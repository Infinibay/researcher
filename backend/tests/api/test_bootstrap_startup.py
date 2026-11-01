"""Serving failures must not recreate data or leave owner credentials alive."""

import sqlite3

import pytest
from starlette.testclient import TestClient

from backend.api.local_access import LocalAccess
from backend.api.main import create_app
from backend.runtime.live_grants import LiveGrants


@pytest.fixture(autouse=True)
def serving_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("INFINIBAY_AUTH_DIR", str(tmp_path / "private-auth"))
    monkeypatch.delenv("INFINIBAY_RUNTIME_CONFIG", raising=False)
    monkeypatch.setenv("INFINIBAY_DATA", str(tmp_path / "logs"))


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_api_refuses_missing_or_empty_database_and_withdraws_grants(
    tmp_path, monkeypatch, kind
):
    path = tmp_path / "not-created" / "source.db"
    if kind == "empty":
        path.parent.mkdir()
        path.touch()
    monkeypatch.setenv("INFINIBAY_DB", str(path))
    app = create_app()
    app.state.live_grants.activate("old")
    with pytest.raises((sqlite3.OperationalError, RuntimeError)), TestClient(app):
        pass
    assert not app.state.live_grants.allows("old")
    assert app.state.local_access.key_file is None
    if kind == "missing":
        assert not path.parent.exists()
    else:
        assert path.read_bytes() == b""


def test_configuration_failure_removes_pairing_file_and_live_grants(
    tmp_path, monkeypatch, _isolated_db
):
    def failed_configuration(*args, **kwargs):
        raise RuntimeError("injected configuration failure")

    monkeypatch.setattr(
        "backend.api.runtime_dependencies.configured_runtime", failed_configuration
    )
    access = LocalAccess()
    app = create_app(access=access)
    app.state.live_grants.activate("old")
    with (
        pytest.raises(RuntimeError, match="injected configuration failure"),
        TestClient(app),
    ):
        pass
    assert access.key_file is None
    assert not list((tmp_path / "private-auth").glob("*.key"))
    assert not app.state.live_grants.allows("old")


@pytest.mark.parametrize("failure", ["enter", "exit"])
def test_runtime_lifecycle_failure_still_closes_owner_access_and_grants(
    tmp_path, _isolated_db, failure
):
    class FailedRuntime:
        def __init__(self):
            self.live_grants = LiveGrants()

        async def __aenter__(self):
            if failure == "enter":
                raise RuntimeError("injected runtime enter")
            return self

        async def __aexit__(self, *args):
            if failure == "exit":
                raise RuntimeError("injected runtime exit")

    runtime = FailedRuntime()
    runtime.live_grants.activate("old")
    access = LocalAccess()
    app = create_app(access=access, runtime_service=runtime)
    with (
        pytest.raises(RuntimeError, match=f"injected runtime {failure}"),
        TestClient(app),
    ):
        pass
    assert access.key_file is None
    assert not list((tmp_path / "private-auth").glob("*.key"))
    assert not runtime.live_grants.allows("old")


async def test_cancelled_owner_start_drains_thread_before_removing_its_file(
    tmp_path, _isolated_db
):
    import asyncio
    import threading

    from backend.api.main import lifespan

    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    class SlowAccess(LocalAccess):
        def start(self):
            started.set()
            try:
                if not release.wait(3):
                    raise RuntimeError("fixture release timeout")
                super().start()
            finally:
                finished.set()

    access = SlowAccess()
    app = create_app(access=access)

    async def serve():
        async with lifespan(app):
            pytest.fail("Cancelled startup must never serve")

    task = asyncio.create_task(serve())
    assert await asyncio.to_thread(started.wait, 3)
    task.cancel()
    try:
        done, _ = await asyncio.wait({task}, timeout=0.05)
        assert not done, "Cleanup returned while its file-creating thread still ran"
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 3)
        with pytest.raises(asyncio.CancelledError):
            await task
    assert access.key_file is None
    assert not list((tmp_path / "private-auth").glob("*.key"))


def test_failed_startup_closes_its_log_file(tmp_path, monkeypatch):
    import logging

    monkeypatch.setenv("INFINIBAY_DB", str(tmp_path / "missing.db"))
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        with (
            pytest.raises((RuntimeError, sqlite3.OperationalError)),
            TestClient(create_app()),
        ):
            pass
        assert root.handlers == before, (
            "Startup failure left its file handler registered"
        )
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()
