"""Actual private-network native execution: no tokens beyond controlled TLS."""

import json
import os
import socket
import ssl
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests.runtime.test_broker_native import native_peer
from backend.tests.runtime.test_native_network_rpc import routing_server

pytestmark = pytest.mark.allow_hosts(["127.0.0.1", "127.0.0.2"])


def network_inputs(tmp_path, ca=None):
    from backend.runtime.native_network import NativeNetwork

    resolver = tmp_path / "resolv.conf"
    resolver.write_text("nameserver 127.0.0.1\n")
    return NativeNetwork.inspect(
        resolver=resolver, ca_bundle=ca or ssl.get_default_verify_paths().cafile
    )


def probe_asset(tmp_path, code):
    from backend.runtime.broker_profile import CodexAsset

    compile(code, "<controlled-native-probe>", "exec")
    source, binary = tmp_path / "probe.c", tmp_path / "probe"
    interpreter = json.dumps(str(Path(sys.executable).resolve()))
    source.write_text(
        "#include <unistd.h>\nint main(void){execl("
        + interpreter
        + ","
        + interpreter
        + ',"-I","-S","-c",'
        + json.dumps(code)
        + ",(char*)0);return 111;}\n"
    )
    subprocess.run(
        ["cc", "-Wall", "-Werror", str(source), "-o", str(binary)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    return CodexAsset.inspect(binary)


@pytest.mark.parametrize(
    "condition", ["trusted", "unknown_issuer", "wrong_hostname", "redirect"]
)
async def test_actual_codex_https_uses_private_net_host_connect_gate(
    broker_setup, native_asset, monkeypatch, tmp_path, condition
):
    from backend.runtime import peer_broker
    from backend.runtime.broker_profile import NativeCapsule
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient, RpcError
    from backend.runtime.egress_proxy import EgressPolicy, TunnelProxy
    from backend.runtime.subscription_auth import (
        ChatGPTCredentials,
        ExternalChatGPTAuth,
    )

    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    program = NativeCapsule._program
    calls = []
    lookups = []
    with routing_server(
        tmp_path,
        hostname_matches=condition != "wrong_hostname",
        dns_name="routing.example.test",
        redirect="https://denied.example.test/off-policy"
        if condition == "redirect"
        else None,
    ) as (port, ca, state):

        def factory(policy):
            def resolve(host, timeout):
                lookups.append(host)
                assert host == "routing.example.test"
                return ["93.184.216.34"]

            def dial(address, remote_port, timeout, admit):
                assert (address, remote_port) == ("93.184.216.34", 443)
                calls.append((address, remote_port))
                raw = socket.socket()
                admit(raw)
                raw.settimeout(timeout)
                raw.connect(("127.0.0.1", port))
                return raw

            return TunnelProxy(policy, resolver=resolve, dial=dial)

        monkeypatch.setattr(peer_broker, "TunnelProxy", factory, raising=False)
        monkeypatch.setattr(
            NativeCapsule,
            "_program",
            lambda self: (
                program(self)
                + ["-c", 'chatgpt_base_url="https://routing.example.test/backend-api"']
            ),
        )
        network = network_inputs(
            tmp_path, None if condition == "unknown_issuer" else ca
        )
        policy = EgressPolicy(("routing.example.test",))

        async def tokens(**_kwargs):
            return ChatGPTCredentials("e30.e30.synthetic", "account-A")

        auth = ExternalChatGPTAuth(tokens)
        async with AsyncPeerBroker(broker) as owner:
            rpc = JsonRpcClient(
                owner.native(
                    registry,
                    peer,
                    operation_key="private-net-https",
                    asset=native_asset,
                    network=network,
                    egress=policy,
                ),
                request_timeout=5,
            )
            auth.bind(rpc)
            try:
                async with rpc:
                    info = await rpc.request(
                        "initialize",
                        {
                            "clientInfo": {
                                "name": "researcher-private-net-test",
                                "version": "0.1.0",
                            },
                            "capabilities": {"experimentalApi": True},
                        },
                    )
                    assert "0.166.0" in info["userAgent"]
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
                    assert operation["runtime_manifest"]["egress"]["hosts"] == [
                        "routing.example.test"
                    ]
            finally:
                auth.close()
        assert calls
        if condition in ("trusted", "redirect"):
            assert state["requests"] > 0
        else:
            assert state["requests"] == 0 and state["tls_rejections"] > 0
        assert registry.inspect(peer)["state"] == "closed"
        assert set(lookups) == {"routing.example.test"}
        if condition == "redirect":
            assert next(iter(broker._egress.values())).proxy._connections >= 2
        assert all(
            not channel._reader.is_alive() for channel in broker._egress.values()
        )


def test_native_private_net_has_no_host_path_or_inherited_control_fd(
    broker_setup, tmp_path, monkeypatch
):
    from backend.runtime.egress_proxy import EgressPolicy

    s, registry, command, broker, _storage, _path = broker_setup
    peer = native_peer(registry, command)
    monkeypatch.setenv("HTTPS_PROXY", "http://FORBIDDEN:SECRET@127.0.0.1:9")
    with socket.socket() as host:
        host.bind(("127.0.0.2", 0))
        host.listen(1)
        port = host.getsockname()[1]
        code = f"""import ctypes,json,os,socket
raw=socket.socket();raw.settimeout(.2)
try:raw.connect(('127.0.0.2',{port}));direct=True
except OSError:direct=False
raw.close()
listener=socket.socket()
try:listener.bind(('127.0.0.1',0));bind=True
except OSError:bind=False
listener.close()
try:socket.socket(socket.AF_UNIX);unix=True
except OSError:unix=False
libc=ctypes.CDLL(None,use_errno=True)
libc.syscall(438,-1,-1,0);pidfd_denied=ctypes.get_errno()==1
try:
 open('/run/researcher-source/forbidden','w').close();write=True
except OSError:write=False
try:
 os.listdir('/proc/'+str(os.getppid())+'/fd');parent_access=True
except OSError:parent_access=False
descriptors=[]
for item in os.listdir('/proc/self/fd'):
 try:descriptors.append((int(item),os.readlink('/proc/self/fd/'+item)))
 except OSError:pass
print(json.dumps({{'direct':direct,'write':write,'parent_access':parent_access,'bind':bind,'unix':unix,'pidfd_denied':pidfd_denied,'fds':descriptors,'net':os.readlink('/proc/self/ns/net'),'proxy':os.environ.get('HTTPS_PROXY')}}))
"""
        result = broker.run_native(
            registry,
            peer,
            operation_key="private-net-probe",
            asset=probe_asset(tmp_path, code),
            network=network_inputs(tmp_path),
            egress=EgressPolicy(("allowed.example",)),
        )
        try:
            assert result.child.wait(timeout=4) == 0
            report = json.loads(result.child.stdout.read())
            assert (
                not report["direct"]
                and not report["write"]
                and not report["parent_access"]
            )
            assert report["net"] != os.readlink("/proc/self/ns/net")
            assert {fd for fd, _ in report["fds"]} == {0, 1, 2}
            assert report["proxy"].startswith("http://127.0.0.1:")
            assert not report["bind"] and not report["unix"] and report["pidfd_denied"]
            assert "SECRET" not in json.dumps(report)
            assert not (s.workspace / "forbidden").exists()
        finally:
            result.child.close_handles()


async def test_private_native_retry_is_receipt_only_and_policy_change_conflicts(
    broker_setup, native_asset, tmp_path
):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.egress_proxy import EgressPolicy

    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    network = network_inputs(tmp_path)
    policy = EgressPolicy(("allowed.example",))
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.native(
                registry,
                peer,
                operation_key="policy-retry",
                asset=native_asset,
                network=network,
                egress=policy,
            )
        ) as rpc,
    ):
        await rpc.request(
            "initialize",
            {"clientInfo": {"name": "researcher-policy-test", "version": "0.1.0"}},
        )
        await rpc.notify("initialized")
        assert (await rpc.request("account/read", {"refreshToken": False}))[
            "account"
        ] is None
        sequence = storage.load().sequence
        retry = broker.run_native(
            registry,
            peer,
            operation_key="policy-retry",
            asset=native_asset,
            network=network,
            egress=policy,
        )
        assert not retry.fresh and retry.child is None and len(broker._egress) == 1
        with pytest.raises(AuthorityConflict):
            broker.run_native(
                registry,
                peer,
                operation_key="policy-retry",
                asset=native_asset,
                network=network,
                egress=EgressPolicy(("other.example",)),
            )
        assert storage.load().sequence == sequence
