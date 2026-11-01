"""Actual pinned Codex TLS against local synthetic routing, never real tokens."""

import json
import socket
import ssl
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from backend.tests.runtime.test_broker_native import native_peer

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@contextmanager
def routing_server(tmp_path, *, hostname_matches=True, dns_name=None, redirect=None):
    """An ephemeral CA signs a server leaf; private keys never enter the capsule."""
    root_key, root_cert = tmp_path / "root.key", tmp_path / "root.pem"
    leaf_key, csr, leaf_cert = (
        tmp_path / "leaf.key",
        tmp_path / "leaf.csr",
        tmp_path / "leaf.pem",
    )
    commands = [
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(root_key),
            "-out",
            str(root_cert),
            "-days",
            "1",
            "-subj",
            "/CN=Ephemeral test CA",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
        ],
        [
            "openssl",
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(leaf_key),
            "-out",
            str(csr),
            "-subj",
            "/CN=Local routing fixture",
        ],
    ]
    for command in commands:
        subprocess.run(command, capture_output=True, check=True, timeout=5)
    extensions = tmp_path / "extensions"
    extensions.write_text(
        "basicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\nsubjectAltName="
        + (
            ("DNS:" + dns_name if dns_name else "IP:127.0.0.1")
            if hostname_matches
            else "DNS:other.example.invalid"
        )
        + "\n"
    )
    subprocess.run(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(csr),
            "-CA",
            str(root_cert),
            "-CAkey",
            str(root_key),
            "-CAcreateserial",
            "-out",
            str(leaf_cert),
            "-days",
            "1",
            "-extfile",
            str(extensions),
        ],
        capture_output=True,
        check=True,
        timeout=5,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(leaf_cert, leaf_key)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    listener.settimeout(0.1)
    stop = threading.Event()
    state = {"requests": 0, "tls_rejections": 0}

    def respond():
        while not stop.is_set():
            try:
                raw, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            try:
                raw.settimeout(1)
                with raw, context.wrap_socket(raw, server_side=True) as conn:
                    conn.settimeout(1)
                    data = b""
                    while b"\r\n\r\n" not in data and len(data) < 16384:
                        block = conn.recv(4096)
                        if not block:
                            break
                        data += block
                    if b"\r\n\r\n" in data:
                        # Never retain request headers (even synthetic tokens).
                        state["requests"] += 1
                        conn.sendall(
                            b"HTTP/1.1 302 Found\r\nLocation: "
                            + redirect.encode("ascii")
                            + b"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                            if redirect
                            else b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
                        )
            except OSError:
                state["tls_rejections"] += 1

    thread = threading.Thread(target=respond, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1], root_cert, state
    finally:
        stop.set()
        listener.close()
        thread.join(timeout=2)
        assert not thread.is_alive()


@pytest.mark.parametrize("condition", ["trusted", "unknown_issuer", "wrong_hostname"])
async def test_real_codex_honors_public_roots_and_hostname_in_broker_profile(
    broker_setup, native_asset, monkeypatch, tmp_path, condition
):
    from backend.runtime.broker_profile import NativeCapsule
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient, RpcError
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.subscription_auth import (
        ChatGPTCredentials,
        ExternalChatGPTAuth,
    )

    resolver = tmp_path / "resolv.conf"
    resolver.write_text("nameserver 127.0.0.1\n")
    program = NativeCapsule._program
    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    with routing_server(tmp_path, hostname_matches=condition != "wrong_hostname") as (
        port,
        ca,
        state,
    ):
        roots = (
            Path(ssl.get_default_verify_paths().cafile)
            if condition == "unknown_issuer"
            else ca
        )
        network = NativeNetwork.inspect(resolver=resolver, ca_bundle=roots)
        if condition == "trusted":
            spawn = broker.domain.spawn

            def change_after_sealing(*args, **kwargs):
                # Changes after capsule preparation cannot change sealed inputs.
                ca.write_text("invalid roots after sealing")
                resolver.write_text("nameserver invalid.after.sealing\n")
                return spawn(*args, **kwargs)

            monkeypatch.setattr(broker.domain, "spawn", change_after_sealing)

        def controlled_program(capsule):
            # Synthetic local routing only; product endpoint policy is unchanged.
            return program(capsule) + [
                "-c",
                "chatgpt_base_url="
                + json.dumps(f"https://127.0.0.1:{port}/backend-api"),
            ]

        monkeypatch.setattr(NativeCapsule, "_program", controlled_program)

        async def tokens(**_kwargs):
            return ChatGPTCredentials("e30.e30.synthetic", "account-A")

        auth = ExternalChatGPTAuth(tokens)
        async with AsyncPeerBroker(broker) as owner:
            rpc = JsonRpcClient(
                owner.native(
                    registry,
                    peer,
                    operation_key="native-local-tls",
                    asset=native_asset,
                    network=network,
                ),
                request_timeout=5,
            )
            auth.bind(rpc)
            try:
                async with rpc:
                    await rpc.request(
                        "initialize",
                        {
                            "clientInfo": {
                                "name": "researcher-local-tls-test",
                                "version": "0.1.0",
                            },
                            "capabilities": {"experimentalApi": True},
                        },
                    )
                    await rpc.notify("initialized")
                    await auth.login()
                    with pytest.raises(
                        RpcError,
                        match="selected workspace missing from routing discovery"
                        if condition == "trusted"
                        else "workspace routing discovery failed",
                    ):
                        await rpc.request("account/read", {"refreshToken": False})
                    operation = next(
                        v
                        for k, v in storage.load().records.items()
                        if k.startswith("broker:op:")
                    )
                    assert (
                        operation["runtime_manifest"]["network"]["ca_bundle"]["sha256"]
                        == network.ca_bundle.sha256
                    )
                    assert (
                        operation["runtime_manifest"]["network"]["resolver"]["sha256"]
                        == network.resolver.sha256
                    )
                    sequence = storage.load().sequence
                    retry = broker.run_native(
                        registry,
                        peer,
                        operation_key="native-local-tls",
                        asset=native_asset,
                        network=network,
                    )
                    assert not retry.fresh and retry.child is None
                    assert storage.load().sequence == sequence
            finally:
                auth.close()
        if condition == "trusted":
            assert state["requests"] > 0
        else:
            assert state["requests"] == 0 and state["tls_rejections"] > 0
        assert registry.inspect(peer)["state"] == "closed"


def test_changed_network_input_cannot_reach_exec_gate(
    broker_setup, native_asset, tmp_path
):
    from backend.runtime.native_network import NativeNetwork

    resolver = tmp_path / "resolv.conf"
    resolver.write_text("nameserver 127.0.0.1\n")
    ca = tmp_path / "ca.pem"
    ca.write_bytes(Path(ssl.get_default_verify_paths().cafile).read_bytes())
    network = NativeNetwork.inspect(resolver=resolver, ca_bundle=ca)
    ca.write_text("changed after manifest")
    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    with pytest.raises(ValueError, match="network"):
        broker.run_native(
            registry,
            peer,
            operation_key="changed-network",
            asset=native_asset,
            network=network,
        )
    broker.revoke()
    operations = [
        v for k, v in storage.load().records.items() if k.startswith("broker:op:")
    ]
    assert len(operations) == 1 and operations[0]["gate_sent"] is False


@pytest.mark.parametrize("kind", ["resolver", "ca_bundle"])
def test_source_workspace_cannot_supply_native_trust_or_dns_inputs(
    broker_setup, native_asset, tmp_path, kind
):
    from backend.runtime.native_network import NativeNetwork

    s, registry, command, broker, storage, _path = broker_setup
    resolver = (s.workspace if kind == "resolver" else tmp_path) / "resolv.conf"
    resolver.write_text("nameserver 127.0.0.1\n")
    ca = (s.workspace if kind == "ca_bundle" else tmp_path) / "ca.pem"
    ca.write_bytes(Path(ssl.get_default_verify_paths().cafile).read_bytes())
    network = NativeNetwork.inspect(resolver=resolver, ca_bundle=ca)
    peer = native_peer(registry, command)
    with pytest.raises(ValueError, match="source workspace"):
        broker.run_native(
            registry,
            peer,
            operation_key="source-network",
            asset=native_asset,
            network=network,
        )
    broker.revoke()
    operation = next(
        v for k, v in storage.load().records.items() if k.startswith("broker:op:")
    )
    assert operation["gate_sent"] is False


async def test_changed_network_manifest_cannot_reuse_an_operation_key(
    broker_setup, native_asset, tmp_path
):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.native_network import NativeNetwork

    resolver = tmp_path / "resolv.conf"
    resolver.write_text("nameserver 127.0.0.1\n")
    ca = Path(ssl.get_default_verify_paths().cafile)
    network = NativeNetwork.inspect(resolver=resolver, ca_bundle=ca)
    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.native(
                registry,
                peer,
                operation_key="network-intent",
                asset=native_asset,
                network=network,
            )
        ) as rpc,
    ):
        await rpc.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "researcher-network-intent-test",
                    "version": "0.1.0",
                }
            },
        )
        await rpc.notify("initialized")
        assert (await rpc.request("account/read", {"refreshToken": False}))[
            "account"
        ] is None
        resolver.write_text("nameserver 127.0.0.2\n")
        changed = NativeNetwork.inspect(resolver=resolver, ca_bundle=ca)
        sequence = storage.load().sequence
        with pytest.raises(AuthorityConflict):
            broker.run_native(
                registry,
                peer,
                operation_key="network-intent",
                asset=native_asset,
                network=changed,
            )
        assert storage.load().sequence == sequence
