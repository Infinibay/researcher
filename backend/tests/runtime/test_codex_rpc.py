"""Exercise a real child process without model calls or network access."""

import os
import sys
from pathlib import Path

import pytest


def connection(**kwargs):
    from backend.runtime.codex_rpc import StdioRpcClient

    return StdioRpcClient(
        (sys.executable, "-u", str(Path(__file__).with_name("fake_rpc_server.py"))),
        cwd=Path(__file__).parent,
        **kwargs,
    )


async def test_request_response_and_notification_have_independent_paths():
    async with connection() as client:
        assert await client.request("notification") == {"ok": True}
        event = await client.next_message(timeout=1)
        assert event == {
            "method": "item/agentMessage/delta",
            "params": {"delta": "Working"},
        }
        assert await client.request("echo", {"value": 42}) == {"value": 42}


async def test_response_barrier_identifies_preceding_events_before_they_are_consumed():
    async with connection() as client:
        first = await client.request_ordered("notification")
        assert first.result == {"ok": True}
        assert first.preceding_messages == 1
        assert (
            await client.request_ordered("echo", {"value": 7})
        ).preceding_messages == 1
        assert (await client.next_message(timeout=1))["params"]["delta"] == "Working"
        second = await client.request_ordered("notification")
        assert second.preceding_messages == 2


async def test_server_request_can_be_answered_while_client_request_is_pending():
    import asyncio

    async with connection() as client:
        pending = asyncio.create_task(client.request("approval"))
        question = await client.next_message(timeout=1)
        assert question["id"] == "approval-1"
        await client.respond(question["id"], {"decision": "decline"})
        assert await pending == {"decision": "decline"}


async def test_timeout_does_not_replay_request_or_attach_late_response_to_next_request():
    async with connection() as client:
        with pytest.raises(TimeoutError):
            await client.request("hold", timeout=0.02)
        assert await client.request("release", timeout=1) == {"current": True}


async def test_process_eof_fails_pending_request_without_waiting_for_request_timeout():
    from backend.runtime.codex_rpc import RpcDisconnected

    async with connection() as client:
        with pytest.raises(RpcDisconnected):
            await client.request("exit", timeout=1)


@pytest.mark.parametrize("method", ["invalid", "oversized"])
async def test_malformed_or_oversized_protocol_frame_fails_closed(method):
    from backend.runtime.codex_rpc import RpcProtocolError

    async with connection(max_message_bytes=1024) as client:
        with pytest.raises(RpcProtocolError):
            await client.request(method)


async def test_slow_consumer_fails_explicitly_instead_of_silently_dropping_events():
    from backend.runtime.codex_rpc import RpcBackpressure

    async with connection(max_messages=2) as client:
        with pytest.raises(RpcBackpressure):
            await client.request("burst")
        with pytest.raises(RpcBackpressure):
            await client.next_message(timeout=1)


async def test_stderr_is_drained_without_blocking_response():
    async with connection() as client:
        assert await client.request("stderr", timeout=1) == {"ok": True}


async def test_rpc_errors_are_not_reported_as_success():
    from backend.runtime.codex_rpc import RpcError

    async with connection() as client:
        with pytest.raises(RpcError, match="Invalid params") as exc:
            await client.request("error")
        assert exc.value.code == -32602


async def test_close_terminates_a_child_that_ignores_eof_and_termination():
    client = connection(close_timeout=0.02)
    async with client:
        pid = (await client.request("stubborn"))["pid"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_event_waiter_is_woken_when_client_closes():
    import asyncio

    from backend.runtime.codex_rpc import RpcDisconnected

    client = connection()
    async with client:
        pending = asyncio.create_task(client.next_message())
    with pytest.raises(RpcDisconnected):
        await asyncio.wait_for(pending, timeout=1)


async def test_request_deadline_also_bounds_a_blocked_stdin_write():
    import asyncio

    async with connection(close_timeout=0.02) as client:
        await client.request("stubborn")
        pending = asyncio.create_task(
            client.request("echo", {"text": "x" * 200000}, timeout=0.02)
        )
        try:
            done, _ = await asyncio.wait((pending,), timeout=0.3)
            assert pending in done, "Request deadline did not cover writing to the peer"
            with pytest.raises(TimeoutError):
                pending.result()
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)


async def test_close_during_pending_birth_never_returns_a_live_connection(monkeypatch):
    import asyncio

    from backend.runtime.codex_rpc import RpcDisconnected

    born = asyncio.Event()
    release = asyncio.Event()
    create = asyncio.create_subprocess_exec
    children = []

    async def delayed(*args, **kwargs):
        process = await create(*args, **kwargs)
        children.append(process)
        born.set()
        await release.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
    client = connection(close_timeout=0.02)
    starting = asyncio.create_task(client.__aenter__())
    closing = None
    try:
        await asyncio.wait_for(born.wait(), 1)
        closing = asyncio.create_task(client.aclose())
        await asyncio.sleep(0)
        release.set()
        await closing
        with pytest.raises(RpcDisconnected):
            await starting
        assert children[0].returncode is not None
    finally:
        release.set()
        await asyncio.gather(starting, return_exceptions=True)
        await client.aclose()
        if closing is not None:
            await closing


async def test_start_error_retains_cleanup_failure_as_evidence():
    from backend.runtime.codex_rpc import JsonRpcClient

    class FailedEndpoint:
        async def open(self, **_):
            raise ValueError("Start was not admitted")

        async def aclose(self, **_):
            raise RuntimeError("Closure cannot be proved")

    with pytest.raises(ValueError, match="not admitted") as error:
        await JsonRpcClient(FailedEndpoint()).__aenter__()
    assert isinstance(error.value.__cause__, RuntimeError)
    assert "cannot be proved" in str(error.value.__cause__)
