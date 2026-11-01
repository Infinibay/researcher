"""Private auth control cannot wait behind turns or reach public event consumers."""

import asyncio
import sys
from pathlib import Path

import pytest

METHOD = "account/chatgptAuthTokens/refresh"


async def test_withdrawal_fences_a_private_reply_already_waiting_for_write_lock(
    tmp_path,
):
    from backend.runtime.codex_rpc import RpcDisconnected

    rpc = connection(tmp_path)
    active = [True]
    entered, release, returned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def handler(_):
        entered.set()
        await release.wait()
        returned.set()
        return {"credential": "PRIVATE-ONLY"}

    rpc.register_private_request(METHOD, handler, allowed=lambda: active[0])
    async with rpc:
        pending = asyncio.create_task(rpc.request("private"))
        await asyncio.wait_for(entered.wait(), 0.5)
        await rpc._write_lock.acquire()
        try:
            release.set()
            await asyncio.wait_for(returned.wait(), 0.5)
            active[0] = False
        finally:
            rpc._write_lock.release()
        with pytest.raises(RpcDisconnected):
            await pending


async def test_malformed_private_notification_never_reaches_public_event_queue(
    tmp_path,
):
    from backend.runtime.codex_rpc import RpcProtocolError

    rpc = connection(tmp_path)

    async def unexpected(_):
        pytest.fail("Malformed private request invoked host provider")

    rpc.register_private_request(METHOD, unexpected)
    async with rpc:
        with pytest.raises(RpcProtocolError):
            await rpc.request("private_notice")
        with pytest.raises(RpcProtocolError):
            await rpc.next_message(timeout=0.1)


def connection(tmp_path):
    from backend.runtime.codex_rpc import StdioRpcClient

    return StdioRpcClient(
        (sys.executable, "-u", str(Path(__file__).with_name("fake_private_server.py"))),
        cwd=tmp_path,
        request_timeout=1,
        close_timeout=0.03,
    )


async def test_private_handler_responds_while_original_rpc_is_still_pending(tmp_path):
    rpc = connection(tmp_path)
    seen = []

    async def handler(params):
        seen.append(params)
        return {"opaque": "PRIVATE-ONLY"}

    rpc.register_private_request(METHOD, handler)
    async with rpc:
        reply = await rpc.request_ordered("private")
        assert reply.result == {"private_response_received": True}
        assert reply.preceding_messages == 1
        assert seen == [{"reason": "unauthorized", "previousAccountId": "account-A"}]
        assert (await rpc.next_message(timeout=0.2))["method"] == "progress"
        with pytest.raises(TimeoutError):
            await rpc.next_message(timeout=0.01)


async def test_private_failure_redacts_error_and_retires_peer(tmp_path, caplog):
    from backend.runtime.codex_rpc import RpcDisconnected

    rpc = connection(tmp_path)

    async def failed(_):
        raise RuntimeError("SECRET-TOKEN-DO-NOT-LOG")

    rpc.register_private_request(METHOD, failed)
    async with rpc:
        with pytest.raises(RpcDisconnected) as error:
            await rpc.request("private")
        assert "SECRET" not in str(error.value)
    assert rpc._process.returncode is not None
    assert "SECRET" not in caplog.text


async def test_private_work_is_bounded_and_cancelled_on_close(tmp_path):
    from backend.runtime.codex_rpc import RpcBackpressure

    rpc = connection(tmp_path)
    finished = asyncio.Event()

    async def held(_):
        try:
            await asyncio.Event().wait()
        finally:
            finished.set()

    rpc.register_private_request(METHOD, held)
    async with rpc:
        with pytest.raises(RpcBackpressure):
            await rpc.request("flood")
    assert rpc._process.returncode is not None


async def test_close_cancels_started_private_handler_without_waiting_for_reply(
    tmp_path,
):
    from backend.runtime.codex_rpc import RpcDisconnected

    rpc = connection(tmp_path)
    entered = asyncio.Event()
    finished = asyncio.Event()

    async def held(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.set()

    rpc.register_private_request(METHOD, held)
    async with rpc:
        pending = asyncio.create_task(rpc.request("private"))
        await asyncio.wait_for(entered.wait(), 0.5)
        await asyncio.wait_for(rpc.aclose(), 0.5)
        assert finished.is_set()
        with pytest.raises(RpcDisconnected):
            await pending
