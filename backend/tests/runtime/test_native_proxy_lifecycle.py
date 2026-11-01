"""Kernel private-NET helper and host sockets stop before durable closure receipts."""

import select
import socket
import sqlite3
import time

import pytest

from backend.tests.runtime.test_broker_native import native_peer
from backend.tests.runtime.test_native_proxy import network_inputs, probe_asset

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def live_tunnel(broker_setup, tmp_path, monkeypatch, *, descendant=False):
    from backend.runtime import peer_broker
    from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy

    _s, registry, command, broker, _storage, _path = broker_setup
    remotes = []

    def factory(policy):
        def dial(address, port, timeout, admit):
            assert (address, port) == ("93.184.216.34", 443)
            raw, remote = socket.socketpair()
            remotes.append(remote)
            admit(raw)
            return raw

        return TunnelProxy(policy, resolver=lambda *_: ["93.184.216.34"], dial=dial)

    monkeypatch.setattr(peer_broker, "TunnelProxy", factory)
    code = r"""import os,socket,sys,time
from urllib.parse import urlsplit
proxy=urlsplit(os.environ['HTTPS_PROXY'])
raw=socket.create_connection((proxy.hostname,proxy.port),timeout=1)
raw.sendall(b'CONNECT allowed.example:443 HTTP/1.1\r\nHost: allowed.example:443\r\n\r\n')
reply=b''
while b'\r\n\r\n' not in reply:reply+=raw.recv(4096)
assert reply.startswith(b'HTTP/1.1 200')
raw.sendall(b'hello')
"""
    if descendant:
        code += "if os.fork()==0:\n time.sleep(30)\n os._exit(0)\n"
    code += "print('READY',flush=True)\nsys.stdin.readline()\n"
    started = broker.run_native(
        registry,
        native_peer(registry, command),
        operation_key="live-private-tunnel",
        asset=probe_asset(tmp_path, code),
        network=network_inputs(tmp_path),
        egress=EgressPolicy(("allowed.example",)),
    )
    assert select.select([started.child.stdout], [], [], 3)[0]
    assert started.child.stdout.readline() == b"READY\n"
    remotes[0].settimeout(1)
    assert remotes[0].recv(5) == b"hello"
    return started, remotes[0]


def test_private_tunnel_closes_when_global_sql_is_busy(
    broker_setup, tmp_path, monkeypatch
):
    from backend.runtime.authority_journal import AuthorityBusy

    _s, _registry, _command, broker, storage, path = broker_setup
    started, remote = live_tunnel(broker_setup, tmp_path, monkeypatch)
    try:
        with remote, sqlite3.connect(storage._paths["database"]) as writer:
            writer.execute("BEGIN IMMEDIATE")
            try:
                with pytest.raises(AuthorityBusy):
                    broker.revoke()
                assert not path.exists()
                assert remote.recv(1) == b""
                assert all(
                    not channel._reader.is_alive()
                    for channel in broker._egress.values()
                )
            finally:
                writer.rollback()
        assert broker.revoke()["state"] == "retired"
    finally:
        started.child.close_handles()


def test_host_channel_loss_stops_native_and_its_descendants_without_global_stop(
    broker_setup, tmp_path, monkeypatch
):
    _s, _registry, _command, broker, storage, path = broker_setup
    started, remote = live_tunnel(broker_setup, tmp_path, monkeypatch, descendant=True)
    try:
        channel = broker._egress[started.operation_id]
        channel.close()
        assert started.child.wait(timeout=4) == 125
        with remote:
            assert remote.recv(1) == b""
        deadline = time.monotonic() + 2
        while "populated 0" not in (path / "cgroup.events").read_text():
            assert time.monotonic() < deadline, (path / "cgroup.procs").read_text()
            time.sleep(0.01)
        assert storage.load().records["broker:active"] == broker.grant_id
    finally:
        started.child.close_handles()


def test_private_peer_close_leaves_sibling_analysis_alive(
    broker_setup, tmp_path, monkeypatch
):
    _s, registry, command, broker, storage, path = broker_setup
    native, remote = live_tunnel(broker_setup, tmp_path, monkeypatch)
    analysis = broker.run_peer(
        registry,
        command,
        operation_key="sibling",
        code="print('READY',flush=True);input();print(42,flush=True)",
    )
    try:
        assert analysis.child.stdout.readline() == b"READY\n"
        receipt = broker.close_peer(native.operation_id)
        assert receipt["execution_closed"]
        with remote:
            assert remote.recv(1) == b""
        analysis.child.stdin.write(b"continue\n")
        assert analysis.child.stdout.readline() == b"42\n"
        assert analysis.child.wait(timeout=3) == 0
        assert (
            path.exists() and storage.load().records["broker:active"] == broker.grant_id
        )
    finally:
        native.child.close_handles()
        analysis.child.close_handles()


@pytest.mark.parametrize("phase", ["channel", "bind"])
def test_stop_racing_private_proxy_start_cannot_send_gate_or_leak_channel(
    broker_setup, native_asset, tmp_path, monkeypatch, phase
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from backend.runtime import peer_broker
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.egress_proxy import EgressPolicy

    _s, registry, command, broker, storage, path = broker_setup
    entered, release = Event(), Event()
    created = []
    if phase == "channel":
        constructor = peer_broker.EgressChannel

        def block(proxy):
            channel = constructor(proxy)
            created.append(channel)
            entered.set()
            assert release.wait(3)
            return channel

        monkeypatch.setattr(peer_broker, "EgressChannel", block)
    else:
        bind = registry.bind

        def block(*args):
            entered.set()
            assert release.wait(3)
            return bind(*args)

        monkeypatch.setattr(registry, "bind", block)
    with ThreadPoolExecutor(2) as pool:
        starting = pool.submit(
            broker.run_native,
            registry,
            native_peer(registry, command),
            operation_key="stop-start-race",
            asset=native_asset,
            network=network_inputs(tmp_path),
            egress=EgressPolicy(("allowed.example",)),
        )
        stopping = None
        try:
            assert entered.wait(3)
            stopping = pool.submit(broker.revoke)
            deadline = time.monotonic() + 2
            while path.exists():
                assert time.monotonic() < deadline
                time.sleep(0.01)
            release.set()
            with pytest.raises(AuthorityConflict):
                starting.result(timeout=5)
            assert stopping.result(timeout=5)["state"] == "retired"
        finally:
            release.set()
            if stopping is not None:
                stopping.result(timeout=5)
    operation = next(
        v for k, v in storage.load().records.items() if k.startswith("broker:op:")
    )
    assert operation["gate_sent"] is False
    assert all(
        not channel._reader.is_alive()
        for channel in [*created, *broker._egress.values()]
    )


def test_post_birth_channel_cleanup_failure_keeps_child_owned_and_reaped(
    broker_setup, native_asset, tmp_path, monkeypatch
):
    from backend.runtime import peer_broker
    from backend.runtime.egress_proxy import EgressPolicy

    _s, registry, command, broker, _storage, _path = broker_setup
    captured = []
    constructor = peer_broker.EgressChannel
    spawn = broker.domain.spawn

    def observe(*args, **kwargs):
        child = spawn(*args, **kwargs)
        captured.append(child)
        return child

    def channel_factory(proxy):
        channel = constructor(proxy)
        close = channel.close_child_end
        first = True

        def fail_once():
            nonlocal first
            if first:
                first = False
                raise OSError("Controlled post-birth child-end close failure")
            close()

        monkeypatch.setattr(channel, "close_child_end", fail_once)
        return channel

    monkeypatch.setattr(peer_broker, "EgressChannel", channel_factory)
    monkeypatch.setattr(broker.domain, "spawn", observe)
    try:
        with pytest.raises(OSError, match="post-birth"):
            broker.run_native(
                registry,
                native_peer(registry, command),
                operation_key="post-birth-failure",
                asset=native_asset,
                network=network_inputs(tmp_path),
                egress=EgressPolicy(("allowed.example",)),
            )
        assert broker.revoke()["state"] == "retired"
        assert len(captured) == 1 and captured[0]._status is not None
    finally:
        for child in captured:
            child.wait(timeout=3)
            child.close_handles()
