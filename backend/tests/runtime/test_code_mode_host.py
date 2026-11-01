"""Native tool readiness needs an executable, not just enabled feature flags."""

import pytest

from backend.tests.runtime.test_broker_native import native_peer


def network():
    from backend.runtime.native_network import NativeNetwork

    return NativeNetwork.inspect(
        resolver="/etc/resolv.conf", ca_bundle="/etc/ssl/certs/ca-certificates.crt"
    )


def test_host_tools_missing_helper_rejected_before_global_reservation(
    broker_setup, native_asset
):
    _s, registry, command, broker, storage, _path = broker_setup
    from backend.runtime.egress_proxy import EgressPolicy

    with pytest.raises(TypeError, match="code-mode"):
        broker.run_native(
            registry,
            native_peer(registry, command),
            operation_key="missing-helper",
            asset=native_asset,
            network=network(),
            egress=EgressPolicy(("allowed.example",)),
            host_tools=True,
        )
    assert storage.load().records.get("broker:active") is None


async def test_real_code_host_is_measured_mounted_and_executes_offline_before_turn(
    broker_setup, native_asset, code_host_asset
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.code_mode_probe import probe_code_mode
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.egress_proxy import EgressPolicy

    _s, registry, command, broker, storage, path = broker_setup
    peer = native_peer(registry, command)
    async with AsyncPeerBroker(broker) as owner:
        endpoint = owner.native(
            registry,
            peer,
            operation_key="host-probe",
            asset=native_asset,
            network=network(),
            egress=EgressPolicy(("allowed.example",)),
            host_tools=True,
            code_host=code_host_asset,
        )
        async with JsonRpcClient(endpoint, request_timeout=10) as rpc:
            await rpc.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "researcher-code-host-probe",
                        "version": "1",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            await rpc.notify("initialized")
            request = rpc.request

            async def checked(method, *args, **kwargs):
                result = await request(method, *args, **kwargs)
                if method == "command/exec":
                    assert result.get("exitCode") == 0, result.get(
                        "stderr", ""
                    ) + result.get("stdout", "")
                return result

            rpc.request = checked
            result = await probe_code_mode(rpc)
            assert result.get("delegate_roundtrip") is True
            assert result == {
                "protocol": 1,
                "computed": 200,
                "isolated_globals": True,
                "session_closed": True,
                "delegate_roundtrip": True,
            }
            assert (await rpc.request("account/read", {"refreshToken": False}))[
                "account"
            ] is None
            operation = storage.load().records["broker:op:" + endpoint._operation]
            assert (
                operation["runtime_manifest"]["code_host"]["sha256"]
                == code_host_asset.sha256
            )
            assert operation["runtime_manifest"]["code_host_probe_sha256"]
        assert registry.inspect(peer)["state"] == "closed" and path.exists()


def test_code_host_replacement_never_opens_the_gate(
    broker_setup, native_asset, tmp_path
):
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.egress_proxy import EgressPolicy

    _s, registry, command, broker, storage, _path = broker_setup
    helper = tmp_path / "code-host"
    helper.write_bytes(b"old")
    helper.chmod(0o700)
    measured = CodexAsset.inspect(helper)
    helper.write_bytes(b"changed")
    with pytest.raises(ValueError, match="asset"):
        broker.run_native(
            registry,
            native_peer(registry, command),
            operation_key="changed-helper",
            asset=native_asset,
            network=network(),
            egress=EgressPolicy(("allowed.example",)),
            host_tools=True,
            code_host=measured,
        )
    broker.revoke()
    records = [
        v for k, v in storage.load().records.items() if k.startswith("broker:op:")
    ]
    assert len(records) == 1 and records[0]["gate_sent"] is False
