"""Real account-free Codex metadata through broker-contained native launch."""

import json
import shutil
import subprocess

import pytest


def native_peer(registry, command_peer):
    peer = registry.inspect(command_peer)
    with registry.runs._transaction() as conn:
        return conn.execute(
            "SELECT id FROM runtime_peers WHERE attempt_id=? AND kind='native'",
            (peer["attempt_id"],),
        ).fetchone()[0]


async def test_real_codex_uses_broker_and_private_credential_free_home(
    broker_setup, native_asset, monkeypatch, tmp_path
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient

    s, registry, command, broker, storage, path = broker_setup
    peer = native_peer(registry, command)
    host_home = tmp_path / "forbidden-host-home"
    host_home.mkdir()
    (host_home / "auth.json").write_text('{"OPENAI_API_KEY":"FORBIDDEN-HOST-CANARY"}')
    monkeypatch.setenv("CODEX_HOME", str(host_home))
    monkeypatch.setenv("OPENAI_API_KEY", "FORBIDDEN-ENV-CANARY")
    project_config = s.workspace / ".codex"
    project_config.mkdir()
    (project_config / "config.toml").write_text("forbidden_config_from_source = true\n")
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.native(
                registry, peer, operation_key="native-metadata", asset=native_asset
            ),
            request_timeout=10,
        ) as rpc,
    ):
        initialization = await rpc.request(
            "initialize",
            {"clientInfo": {"name": "researcher-profile-test", "version": "0.1.0"}},
        )
        await rpc.notify("initialized")
        assert "0.166.0" in initialization["userAgent"]
        account = await rpc.request("account/read", {"refreshToken": False})
        assert account["account"] is None
        config = (await rpc.request("config/read", {"includeLayers": False}))["config"]
        assert config["forced_login_method"] == "chatgpt"
        assert config["model_provider"] == "openai"
        assert config.get("mcp_servers") in (None, {})
        assert config["features"]["shell_tool"] is False
        assert (
            config["projects"]["/run/researcher-source"]["trust_level"] == "untrusted"
        )
        assert registry.inspect(peer)["state"] == "bound"
        assert storage.load().records["broker:active"] == broker.grant_id
        operation = next(
            v for k, v in storage.load().records.items() if k.startswith("broker:op:")
        )
        assert operation["runtime_manifest"]["asset"]["sha256"] == native_asset.sha256
        before = storage.load().sequence
        retry = broker.run_native(
            registry, peer, operation_key="native-metadata", asset=native_asset
        )
        assert not retry.fresh and retry.child is None
        assert storage.load().sequence == before
    assert not path.exists()
    assert registry.inspect(peer)["state"] == "closed"


def test_native_manifest_is_rechecked_before_gate(broker_setup, tmp_path):
    from backend.runtime.broker_profile import CodexAsset

    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    binary = tmp_path / "changed-runtime"
    binary.write_bytes(b"old runtime")
    binary.chmod(0o700)
    asset = CodexAsset.inspect(binary)
    binary.write_bytes(b"replaced runtime")
    with pytest.raises(ValueError, match="asset"):
        broker.run_native(registry, peer, operation_key="changed", asset=asset)
    broker.revoke()
    operations = [
        v for k, v in storage.load().records.items() if k.startswith("broker:op:")
    ]
    assert len(operations) == 1 and operations[0]["gate_sent"] is False


def test_native_launch_rejects_a_command_peer_before_reserving(
    broker_setup, native_asset
):
    from backend.runtime.authority_journal import AuthorityConflict

    _s, registry, command, broker, storage, _path = broker_setup
    with pytest.raises(AuthorityConflict):
        broker.run_native(
            registry, command, operation_key="wrong-kind", asset=native_asset
        )
    assert storage.load().records.get("broker:active") is None


async def test_owned_native_host_tools_profile_is_explicit_and_keeps_shell_disabled(
    broker_setup, native_asset, code_host_asset
):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.egress_proxy import EgressPolicy
    from backend.runtime.native_network import NativeNetwork

    _s, registry, command, broker, storage, _path = broker_setup
    peer = native_peer(registry, command)
    network = NativeNetwork.inspect(
        resolver="/etc/resolv.conf", ca_bundle="/etc/ssl/certs/ca-certificates.crt"
    )
    policy = EgressPolicy(("allowed.example",))
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.native(
                registry,
                peer,
                operation_key="host-tools",
                asset=native_asset,
                network=network,
                egress=policy,
                host_tools=True,
                code_host=code_host_asset,
            ),
            request_timeout=10,
        ) as rpc,
    ):
        await rpc.request(
            "initialize",
            {"clientInfo": {"name": "researcher-host-tools-test", "version": "1"}},
        )
        await rpc.notify("initialized")
        config = (await rpc.request("config/read", {"includeLayers": False}))["config"]
        assert all(
            config["features"][name] is True
            for name in (
                "code_mode_host",
                "code_mode_interrupt",
                "skip_host_skill_discovery",
            )
        )
        assert all(
            config["features"][name] is False
            for name in ("code_mode", "shell_tool", "plugins", "apps", "multi_agent")
        )
        assert config.get("mcp_servers") in (None, {})
        assert (await rpc.request("account/read", {"refreshToken": False}))[
            "account"
        ] is None
        operation = next(
            v for k, v in storage.load().records.items() if k.startswith("broker:op:")
        )
        assert operation["runtime_manifest"]["host_tools"] is True
        assert (
            operation["runtime_manifest"]["profile"]
            == "readonly-native-codex-connect-host-tools-v1"
        )
        with pytest.raises(AuthorityConflict):
            broker.run_native(
                registry,
                peer,
                operation_key="host-tools",
                asset=native_asset,
                network=network,
                egress=policy,
            )


@pytest.mark.parametrize("host_tools", [True, "true"])
def test_host_tool_profile_requires_private_network_policy_before_reserving(
    broker_setup, native_asset, host_tools
):
    _s, registry, command, broker, storage, _path = broker_setup
    with pytest.raises(TypeError, match="Host tools"):
        broker.run_native(
            registry,
            native_peer(registry, command),
            operation_key="invalid-host-tools",
            asset=native_asset,
            host_tools=host_tools,
        )
    assert storage.load().records.get("broker:active") is None


@pytest.mark.parametrize("host_tools", [0, "", None])
async def test_async_host_tool_option_does_not_coerce_false_values(
    broker_setup, native_asset, host_tools
):
    from backend.runtime.broker_stdio import AsyncPeerBroker

    _s, registry, command, broker, storage, _path = broker_setup
    async with AsyncPeerBroker(broker) as owner:
        endpoint = owner.native(
            registry,
            native_peer(registry, command),
            operation_key="invalid-false",
            asset=native_asset,
            host_tools=host_tools,
        )
        with pytest.raises(TypeError, match="Host tools"):
            await endpoint.open(limit=4096)
        assert storage.load().records.get("broker:active") is None


def test_native_profile_allows_internet_client_sockets_without_host_controls(
    broker_setup, tmp_path, monkeypatch
):
    """A controlled ELF probes the native profile; it is not a Codex substitute."""
    from backend.runtime.broker_profile import CodexAsset

    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("Requires C compiler for native capsule policy probe")
    source = tmp_path / "profile-probe.c"
    binary = tmp_path / "profile-probe"
    source.write_text("""#define _GNU_SOURCE
#include <fcntl.h>
#include <netinet/in.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>
int main(void) {
 int net=socket(AF_INET,SOCK_STREAM,0);
 int bus=socket(AF_UNIX,SOCK_STREAM,0);
 struct sockaddr_in address={0};
 address.sin_family=AF_INET;
 address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
 int listening=bind(net,(struct sockaddr*)&address,sizeof(address));
 int file=open("/run/researcher-source/forbidden-write",O_WRONLY|O_CREAT,0600);
 int hidden=access("/sys/fs/cgroup/cgroup.procs",R_OK);
 int control=unshare(0);
 printf("{\\"internet\\":%d,\\"unix_control\\":%d,\\"source_write\\":%d,\\"cgroup_visible\\":%d,\\"unshare\\":%d,\\"key\\":%d,\\"bind\\":%d}\\n",
        net>=0,bus>=0,file>=0,hidden==0,control==0,getenv("OPENAI_API_KEY")!=NULL,listening==0);
 if(net>=0) close(net);
 if(bus>=0) close(bus);
 if(file>=0) close(file);
 return 0;
}
""")
    subprocess.run(
        [compiler, "-Wall", "-Werror", str(source), "-o", str(binary)],
        check=True,
        timeout=10,
    )
    s, registry, command, broker, _storage, _path = broker_setup
    peer = native_peer(registry, command)
    monkeypatch.setenv("OPENAI_API_KEY", "FORBIDDEN-PROBE-CANARY")
    result = broker.run_native(
        registry, peer, operation_key="profile-probe", asset=CodexAsset.inspect(binary)
    )
    try:
        assert result.child.wait(timeout=3) == 0
        report = json.loads(result.child.stdout.read())
        assert report == {
            "internet": 1,
            "unix_control": 0,
            "source_write": 0,
            "cgroup_visible": 0,
            "unshare": 0,
            "key": 0,
            "bind": 0,
        }
        assert not (s.workspace / "forbidden-write").exists()
    finally:
        result.child.close_handles()
