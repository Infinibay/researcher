"""A host-owned managed RPC coordinates credential rotation across connections."""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from backend.tests.runtime.test_subscription_auth import auth_file


def provider(tmp_path, *, timeout=1):
    from backend.runtime.codex_rpc import StdioRpcClient
    from backend.runtime.subscription_auth import ManagedTokenFile
    from backend.runtime.subscription_provider import HostSubscription

    managed = tmp_path / "managed"
    managed.mkdir()
    path = auth_file(managed)
    rpc = StdioRpcClient(
        (
            sys.executable,
            "-I",
            "-u",
            str(Path(__file__).with_name("fake_managed_auth_server.py")),
        ),
        cwd=managed,
        request_timeout=2,
        close_timeout=0.03,
    )
    return HostSubscription(ManagedTokenFile(path), rpc, timeout=timeout), path


def native(tmp_path, host, name):
    from backend.runtime.codex_rpc import StdioRpcClient
    from backend.runtime.codex_session import CodexSession, ExecutionLimits

    workspace = tmp_path / name
    workspace.mkdir()
    (workspace / "phase").write_text("turn")
    rpc = StdioRpcClient(
        (
            sys.executable,
            "-I",
            "-u",
            str(Path(__file__).with_name("fake_subscription_server.py")),
        ),
        cwd=workspace,
        request_timeout=2,
        close_timeout=0.03,
    )
    return CodexSession(
        rpc,
        workspace=workspace,
        model="synthetic",
        limits=ExecutionLimits(3, 2, 1, 3, 1000),
        subscription_auth=host.connection(),
    )


async def started(host):
    event = await host.rpc.next_message(timeout=1)
    assert event == {"method": "test/refresh-started", "params": {"count": 1}}


async def test_two_native_connections_share_one_rotation_and_never_replay_turns(
    tmp_path,
):
    host, _path = provider(tmp_path)
    async with host, AsyncExitStack() as stack:
        a = await stack.enter_async_context(native(tmp_path, host, "a"))
        b = await stack.enter_async_context(native(tmp_path, host, "b"))
        tasks = [asyncio.create_task(s.run("answer")) for s in (a, b)]
        await started(host)
        await host.rpc.request("test/release")
        assert [r.text for r in await asyncio.gather(*tasks)] == ["ok", "ok"]
        assert await host.rpc.request("test/summary") == {"forced_refreshes": 1}
        for s in (a, b):
            summary = await s.rpc.request("test/summary")
            assert (
                summary["token_changed"] and summary["methods"].count("turn/start") == 1
            )


async def test_cancelled_consumer_does_not_cancel_or_repeat_shared_rotation(tmp_path):
    host, _path = provider(tmp_path)
    async with host, AsyncExitStack() as stack:
        a = await stack.enter_async_context(native(tmp_path, host, "a"))
        b = await stack.enter_async_context(native(tmp_path, host, "b"))
        first = asyncio.create_task(a.run("answer"))
        await started(host)
        second = asyncio.create_task(b.run("answer"))
        # Closing the client's transport cancels its private callback. The host
        # already owns the in-flight rotation and must keep its serial lock.
        a.subscription_auth.withdraw()
        await a.rpc.aclose()
        await host.rpc.request("test/release")
        await asyncio.gather(first, return_exceptions=True)
        assert (await second).text == "ok"
        assert await host.rpc.request("test/summary") == {"forced_refreshes": 1}


async def test_withdrawn_waiter_does_not_retire_the_shared_account(tmp_path):
    host, _path = provider(tmp_path)
    async with host, AsyncExitStack() as stack:
        a = await stack.enter_async_context(native(tmp_path, host, "a"))
        b = await stack.enter_async_context(native(tmp_path, host, "b"))
        c = await stack.enter_async_context(native(tmp_path, host, "c"))
        first = asyncio.create_task(a.run("answer"))
        await started(host)
        waiter = asyncio.create_task(b.run("answer"))
        async with asyncio.timeout(1):
            while len(host._pending) < 2:
                await asyncio.sleep(0)
        b.subscription_auth.withdraw()
        await b.rpc.aclose()
        await host.rpc.request("test/release")
        # The withdrawn queued request must neither renew again nor withdraw
        # the account still used by a and c.
        assert (await first).text == "ok"
        await asyncio.gather(waiter, return_exceptions=True)
        assert (await c.run("answer")).text == "ok"
        assert await host.rpc.request("test/summary") == {"forced_refreshes": 1}


@pytest.mark.parametrize("condition", ["unchanged", "switch", "error"])
async def test_unconfirmed_or_wrong_account_rotation_cannot_authenticate_native(
    tmp_path, condition
):
    from backend.runtime.codex_rpc import RpcDisconnected

    host, _path = provider(tmp_path)
    async with host, native(tmp_path, host, "a") as a:
        task = asyncio.create_task(a.run("answer"))
        await started(host)
        # A mismatch or lost managed receipt retires the provider. Its physical
        # close may race this diagnostic release ACK, which is not business state.
        await asyncio.gather(
            host.rpc.request("test/release", {"condition": condition}),
            return_exceptions=True,
        )
        with pytest.raises(RpcDisconnected) as error:
            await task
        assert "SECRET" not in str(error.value)
        summary = json.loads((tmp_path / "a" / "wire-summary.json").read_text())
        assert summary["private_responses"] == 0
        with pytest.raises(RuntimeError):
            host.connection()


async def test_external_rotation_is_reused_without_another_oauth_request(tmp_path):
    host, path = provider(tmp_path)
    async with host, native(tmp_path, host, "a") as a:
        value = json.loads(path.read_text())
        value["tokens"]["access_token"] = "e30.e30.external"
        path.write_text(json.dumps(value))
        assert (await a.run("answer")).text == "ok"
        assert await host.rpc.request("test/summary") == {"forced_refreshes": 0}


async def test_missing_managed_source_does_not_start_credential_process(tmp_path):
    from backend.runtime.codex_session import SubscriptionRequired

    host, path = provider(tmp_path)
    path.unlink()
    with pytest.raises(SubscriptionRequired):
        async with host:
            pytest.fail("Missing managed source was accepted")
    assert host.rpc._process is None and not path.exists()


async def test_host_deadline_retires_refresh_and_closes_managed_peer(tmp_path):
    from backend.runtime.codex_rpc import RpcDisconnected

    host, _path = provider(tmp_path, timeout=0.15)
    async with host, native(tmp_path, host, "a") as a:
        task = asyncio.create_task(a.run("answer"))
        await started(host)
        with pytest.raises(RpcDisconnected):
            await task
        with pytest.raises(RuntimeError):
            host.connection()
        assert host.rpc._process.returncode is not None


async def test_host_close_promptly_retires_waiting_native_connections(tmp_path):
    from backend.runtime.codex_rpc import RpcDisconnected

    host, _path = provider(tmp_path)
    async with host, native(tmp_path, host, "a") as a:
        task = asyncio.create_task(a.run("answer"))
        await started(host)
        await host.aclose()
        await asyncio.wait_for(a.rpc._failed.wait(), 0.5)
        with pytest.raises(RpcDisconnected):
            await task
        assert host.rpc._process.returncode is not None and not host._pending


async def test_pending_capacity_rejects_one_consumer_without_poisoning_owner(tmp_path):
    from backend.runtime.codex_rpc import RpcDisconnected

    host, _path = provider(tmp_path)
    host.max_pending = 1
    async with host, AsyncExitStack() as stack:
        a = await stack.enter_async_context(native(tmp_path, host, "a"))
        b = await stack.enter_async_context(native(tmp_path, host, "b"))
        first = asyncio.create_task(a.run("answer"))
        await started(host)
        overflow = asyncio.create_task(b.run("answer"))
        await asyncio.wait_for(b.rpc._failed.wait(), 0.5)
        await host.rpc.request("test/release")
        assert (await first).text == "ok"
        with pytest.raises(RpcDisconnected):
            await overflow
        assert await host.rpc.request("test/summary") == {"forced_refreshes": 1}
        assert host.connection() is not None


async def test_cancelled_close_waiter_keeps_physical_shutdown_before_callback_drain(
    tmp_path, monkeypatch
):
    from backend.runtime.codex_rpc import RpcDisconnected

    host, _path = provider(tmp_path)
    async with host, native(tmp_path, host, "a") as a:
        task = asyncio.create_task(a.run("answer"))
        await started(host)
        entered, release = asyncio.Event(), asyncio.Event()
        physical_close = host.rpc._endpoint.aclose

        async def delayed_close(*, timeout):
            entered.set()
            await release.wait()
            await physical_close(timeout=timeout)

        monkeypatch.setattr(host.rpc._endpoint, "aclose", delayed_close)
        closing = asyncio.create_task(host.aclose())
        await asyncio.wait_for(entered.wait(), 0.5)
        closing.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await closing
            # No token can be delivered, but callback retirement must not outrun
            # the owned physical close when its original waiter disappears.
            assert not a.rpc._failed.is_set()
        finally:
            release.set()
            await host.aclose()
        await asyncio.wait_for(a.rpc._failed.wait(), 0.5)
        with pytest.raises(RpcDisconnected):
            await task
