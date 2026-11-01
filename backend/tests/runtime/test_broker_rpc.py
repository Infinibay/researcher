"""Actual RPC frames through broker-owned kernel peers, without model calls."""

import asyncio
import sqlite3
from pathlib import Path
from threading import Event

import pytest

from backend.tests.runtime.test_broker_peer_close import next_peer


def code():
    return Path(__file__).with_name("fake_rpc_server.py").read_text()


async def test_rpc_uses_broker_transport_and_closes_only_its_original_peer(
    broker_setup,
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, storage, path = broker_setup
    another = next_peer(registry, peer)
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.peer(registry, another, operation_key="sibling", code=code())
        ) as second,
    ):
        async with JsonRpcClient(
            owner.peer(registry, peer, operation_key="first-rpc", code=code())
        ) as first:
            assert await first.request("echo", {"value": 137}) == {"value": 137}
            reply = await first.request_ordered("notification")
            assert reply.preceding_messages == 1
            assert (await first.next_message(timeout=1))["params"]["delta"] == "Working"
        assert (
            path.exists() and storage.load().records["broker:active"] == broker.grant_id
        )
        assert registry.inspect(peer)["state"] == "closed"
        assert registry.inspect(another)["state"] == "bound"
        assert await second.request("echo", {"value": 200}) == {"value": 200}
    assert not path.exists() and storage.load().records["broker:active"] is None


async def test_broker_rpc_bounds_blocked_write_and_shutdown_remains_available(
    broker_setup,
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, _storage, path = broker_setup
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.peer(registry, peer, operation_key="blocked-write", code=code()),
            request_timeout=0.05,
        ) as client,
    ):
        await client.request("stubborn")
        pending = asyncio.create_task(
            client.request("echo", {"text": "x" * 200000}, timeout=0.05)
        )
        done, _ = await asyncio.wait((pending,), timeout=0.5)
        assert pending in done, "Pipe backpressure blocked the event loop/deadline"
        with pytest.raises(TimeoutError):
            pending.result()
    assert not path.exists()


async def test_cancellation_during_start_withdraws_before_slow_bind_returns(
    broker_setup, monkeypatch
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, storage, path = broker_setup
    entered = Event()
    release = Event()
    original = registry.bind

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(registry, "bind", blocked)
    owner = AsyncPeerBroker(broker)
    await owner.__aenter__()
    client = JsonRpcClient(
        owner.peer(registry, peer, operation_key="cancel-start", code=code())
    )
    starting = asyncio.create_task(client.__aenter__())
    try:
        async with asyncio.timeout(3):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        starting.cancel()
        async with asyncio.timeout(2):
            while path.exists():
                await asyncio.sleep(0.01)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await starting
        operations = [
            v for k, v in storage.load().records.items() if k.startswith("broker:op:")
        ]
        assert len(operations) == 1 and operations[0]["gate_sent"] is False
        assert registry.inspect(peer)["state"] == "closed"
    finally:
        release.set()
        await owner.aclose()


async def test_attempt_stop_reaches_kernel_while_peer_close_worker_is_busy(
    broker_setup, monkeypatch
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, _storage, path = broker_setup
    entered, release = Event(), Event()
    original = broker.close_peer

    def blocked(operation_id):
        entered.set()
        assert release.wait(5)
        return original(operation_id)

    monkeypatch.setattr(broker, "close_peer", blocked)
    owner = await AsyncPeerBroker(broker).__aenter__()
    client = await JsonRpcClient(
        owner.peer(registry, peer, operation_key="busy-close", code=code())
    ).__aenter__()
    closing = asyncio.create_task(client.aclose())
    stopping = None
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        stopping = asyncio.create_task(owner.aclose())
        async with asyncio.timeout(2):
            while path.exists():
                await asyncio.sleep(0.01)
        # Stop has already killed/removed the domain. Scope cleanup still owns
        # the outstanding receipt worker, and must drain it before returning.
        done, _ = await asyncio.wait((stopping,), timeout=0.1)
        assert not done, "Owner returned with its peer-close worker still running"
    finally:
        release.set()
        await closing
        await owner.aclose()
        if stopping is not None:
            await stopping


@pytest.mark.parametrize(
    ("method", "failure"),
    [
        ("exit", "RpcDisconnected"),
        ("invalid", "RpcProtocolError"),
        ("oversized", "RpcProtocolError"),
        ("burst", "RpcBackpressure"),
    ],
)
async def test_broker_wire_failures_are_explicit_and_domain_remains_closable(
    broker_setup, method, failure
):
    from backend.runtime import codex_rpc
    from backend.runtime.broker_stdio import AsyncPeerBroker

    _s, registry, peer, broker, storage, path = broker_setup
    async with (
        AsyncPeerBroker(broker) as owner,
        codex_rpc.JsonRpcClient(
            owner.peer(registry, peer, operation_key=method, code=code()),
            max_message_bytes=1024,
            max_messages=2,
        ) as client,
    ):
        with pytest.raises(getattr(codex_rpc, failure)):
            await client.request(method)
    assert not path.exists()
    assert storage.load().records["broker:active"] is None


async def test_broker_drains_stderr_and_can_answer_native_requests(broker_setup):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, _storage, _path = broker_setup
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.peer(registry, peer, operation_key="duplex", code=code())
        ) as client,
    ):
        assert await client.request("stderr", timeout=1) == {"ok": True}
        pending = asyncio.create_task(client.request("approval"))
        question = await client.next_message(timeout=1)
        assert question["id"] == "approval-1"
        await client.respond(question["id"], {"decision": "decline"})
        assert await pending == {"decision": "decline"}


async def test_cancel_at_completed_birth_disposes_undelivered_data_fds(
    broker_setup, monkeypatch
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, _storage, path = broker_setup
    owner = await AsyncPeerBroker(broker).__aenter__()
    loop = asyncio.get_running_loop()
    submit, run = loop.run_in_executor, broker.run_peer
    results = []

    def capture(*args, **kwargs):
        result = run(*args, **kwargs)
        results.append(result)
        return result

    def cancel_at_receipt(executor, callback, *args):
        future = submit(executor, callback, *args)
        if executor is owner._launch_pool:
            # Cancellation and the completion observer run before _start resumes.
            # The underlying birth really succeeded and returned duplicated FDs.
            future.add_done_callback(lambda _: starting.cancel())
        return future

    monkeypatch.setattr(broker, "run_peer", capture)
    monkeypatch.setattr(loop, "run_in_executor", cancel_at_receipt)
    client = JsonRpcClient(
        owner.peer(registry, peer, operation_key="cancel-receipt", code=code())
    )
    starting = asyncio.create_task(client.__aenter__())
    try:
        with pytest.raises(asyncio.CancelledError):
            await starting
        assert not path.exists()
        assert len(results) == 1
        child = results[0].child
        assert child is not None
        assert all(
            stream.closed for stream in (child.stdin, child.stdout, child.stderr)
        )
    finally:
        await owner.aclose()
        for result in results:
            if result.child is not None:
                result.child.close_handles()


async def test_closed_command_peers_release_source_capacity_for_later_jobs(
    broker_setup,
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    _s, registry, peer, broker, _storage, _path = broker_setup
    async with AsyncPeerBroker(broker) as owner:
        current = peer
        for number in range(9):
            if number:
                current = next_peer(registry, peer)
            async with JsonRpcClient(
                owner.peer(
                    registry, current, operation_key=f"job-{number}", code=code()
                )
            ) as client:
                assert await client.request("echo", {"job": number}) == {"job": number}
            assert registry.inspect(current)["state"] == "closed"


async def test_local_sql_contention_cannot_delay_domain_stop(broker_setup, monkeypatch):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    s, registry, peer, broker, storage, path = broker_setup
    owner = await AsyncPeerBroker(broker).__aenter__()
    client = await JsonRpcClient(
        owner.peer(registry, peer, operation_key="local-busy", code=code())
    ).__aenter__()
    entered = Event()
    original = broker.project_closed

    def observe(**kwargs):
        entered.set()
        return original(**kwargs)

    monkeypatch.setattr(broker, "project_closed", observe)
    s.c.conn.execute("BEGIN IMMEDIATE")
    closing = asyncio.create_task(client.aclose())
    stopping = None
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        assert not closing.done()
        stopping = asyncio.create_task(owner.aclose())
        async with asyncio.timeout(2):
            while path.exists():
                await asyncio.sleep(0.01)
        assert not stopping.done(), "Source writer should still hold the receipt"
    finally:
        s.c.conn.rollback()
        await closing
        await owner.aclose()
        if stopping is not None:
            await stopping
    assert registry.inspect(peer)["state"] == "closed"
    assert storage.load().records["broker:active"] is None


async def test_async_stop_preserves_global_receipt_if_source_disappears(broker_setup):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    s, registry, peer, broker, storage, path = broker_setup
    owner = await AsyncPeerBroker(broker).__aenter__()
    client = await JsonRpcClient(
        owner.peer(registry, peer, operation_key="source-lost", code=code())
    ).__aenter__()
    database = Path(s.c.database)
    try:
        assert await client.request("echo", {"value": 137}) == {"value": 137}
        database.unlink()
        with pytest.raises(sqlite3.OperationalError):
            await client.aclose()
        with pytest.raises(sqlite3.OperationalError):
            await owner.aclose()
        assert not database.exists() and not path.exists()
        assert storage.load().records["broker:active"] is None
    finally:
        await asyncio.gather(client.aclose(), owner.aclose(), return_exceptions=True)
