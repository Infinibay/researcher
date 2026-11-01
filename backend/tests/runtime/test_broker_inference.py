"""Complete host composition over original owned peers, without model calls."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_broker_ken import ken_peer
from backend.tests.runtime.test_broker_native import native_peer
from backend.tests.runtime.test_ken_mediation import Peer, tool


@pytest.fixture
def composed_setup(broker_setup, ken_installation, tmp_path):
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.ken_worker import KenInstallation

    s, registry, command, broker, storage, path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    ken_installation.write_text(
        "#!"
        + str(ken_installation.parent / "python")
        + "\n"
        + Path(__file__).with_name("fake_broker_ken.py").read_text()
    )
    installation = KenInstallation.inspect(ken_installation)
    prepared = broker.run_ken(
        registry,
        ken_peer(registry, command),
        operation_key="prepare",
        installation=installation,
        mode="prepare",
    )
    try:
        assert prepared.child.wait(timeout=3) == 0
    finally:
        prepared.child.close_handles()
    assert broker.close_peer(prepared.operation_id)["execution_closed"]
    broker.project_closed(operation_id=prepared.operation_id)
    binary = tmp_path / "controlled-native"
    binary.write_text(
        "#!/usr/bin/python3\n"
        + Path(__file__).with_name("fake_broker_inference_native.py").read_text()
    )
    binary.chmod(0o755)
    return SimpleNamespace(
        s=s,
        registry=registry,
        command=command,
        broker=broker,
        storage=storage,
        path=path,
        installation=installation,
        asset=CodexAsset.inspect(binary),
        prepared=prepared.operation_id,
    )


def native(owner, setup):
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.codex_session import CodexSession, ExecutionLimits
    from backend.runtime.egress_proxy import EgressPolicy
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.workspaces import PEER_WORKSPACE

    endpoint = owner.native(
        setup.registry,
        native_peer(setup.registry, setup.command),
        operation_key="inference",
        asset=setup.asset,
        network=NativeNetwork.inspect(
            resolver="/etc/resolv.conf", ca_bundle="/etc/ssl/certs/ca-certificates.crt"
        ),
        egress=EgressPolicy(("allowed.example",)),
        host_tools=True,
    )
    return CodexSession(
        JsonRpcClient(endpoint),
        workspace=PEER_WORKSPACE,
        model="controlled-only",
        limits=ExecutionLimits(5, 2, 2, 10, 1000),
        sandbox="read-only",
    )


async def test_owned_composition_requires_ken_before_thread_and_routes_both_tools(
    composed_setup,
):
    from backend.runtime.broker_inference import broker_inference
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.business_mediation import BusinessTools

    s = composed_setup
    business_peer = Peer([tool("researcher_source_read")])
    business = await BusinessTools.connect(business_peer)
    analysis = SimpleNamespace(catalog=[])
    active = [True]
    async with AsyncPeerBroker(s.broker) as owner:
        session = native(owner, s)
        endpoint = owner.ken(
            s.registry,
            ken_peer(s.registry, s.command),
            operation_key="ken",
            installation=s.installation,
        )
        async with broker_inference(
            session,
            endpoint,
            prepared_operation=s.prepared,
            business=business,
            analysis=analysis,
            active=lambda: active[0],
        ) as facade:
            result = await facade.run(
                "Read the source with Ken, then the business source"
            )
            assert result.status == "completed" and result.text == "137"
            summary = await session.rpc.request("test/summary")
            assert len(summary["catalog_names"]) == 6 and summary[
                "results_success"
            ] == [True, True]
            assert business_peer.calls == [
                ("researcher_source_read", {"path": "fact.txt"})
            ]
            (s.s.workspace / ".ken/incomplete").touch()
            with pytest.raises(RuntimeError, match="Ken"):
                await facade.run("Do not submit another turn")
            assert (await session.rpc.request("test/summary"))["methods"].count(
                "turn/start"
            ) == 1
        assert s.registry.inspect(endpoint.peer_id)["state"] == "closed"
        assert s.path.exists()
    assert not s.path.exists()


@pytest.mark.parametrize("failure", ["missing_prepare", "incomplete", "withdrawn"])
async def test_ken_admission_failure_never_opens_native_peer(composed_setup, failure):
    from backend.runtime.broker_inference import broker_inference
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.business_mediation import BusinessTools

    s = composed_setup
    business = await BusinessTools.connect(Peer([tool("researcher_source_read")]))
    if failure == "incomplete":
        (s.s.workspace / ".ken/incomplete").touch()
    async with AsyncPeerBroker(s.broker) as owner:
        session = native(owner, s)
        endpoint = owner.ken(
            s.registry,
            ken_peer(s.registry, s.command),
            operation_key="ken",
            installation=s.installation,
        )
        with pytest.raises(RuntimeError, match="Ken"):
            async with broker_inference(
                session,
                endpoint,
                prepared_operation="missing"
                if failure == "missing_prepare"
                else s.prepared,
                business=business,
                analysis=SimpleNamespace(catalog=[]),
                active=lambda: failure != "withdrawn",
            ):
                pytest.fail("Invalid Ken readiness admitted native work")
        assert session.thread_id is None
        assert not session.rpc._endpoint._opened
        assert not any(
            v.get("kind") == "native"
            for k, v in s.storage.load().records.items()
            if k.startswith("broker:op:")
        )


@pytest.mark.parametrize("failure", ["catalog", "closed"])
async def test_ken_failure_during_turn_prevents_business_effect(
    composed_setup, failure
):
    from backend.runtime.broker_inference import broker_inference
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.business_mediation import BusinessTools

    s = composed_setup
    peer = Peer([tool("researcher_source_read")])
    business = await BusinessTools.connect(peer)
    async with AsyncPeerBroker(s.broker) as owner:
        session = native(owner, s)
        endpoint = owner.ken(
            s.registry,
            ken_peer(s.registry, s.command),
            operation_key="ken",
            installation=s.installation,
        )
        async with broker_inference(
            session,
            endpoint,
            prepared_operation=s.prepared,
            business=business,
            analysis=SimpleNamespace(catalog=[]),
        ) as facade:

            async def fail_ken_before_effect(event):
                if event.get("params", {}).get("tool") == "researcher_source_read":
                    if failure == "catalog":
                        (s.s.workspace / ".ken/incomplete").touch()
                    else:
                        await endpoint.aclose(timeout=3)

            with pytest.raises(RuntimeError, match="Ken"):
                await facade.run(
                    "Read, then perform a business operation",
                    on_event=fail_ken_before_effect,
                )
            assert not peer.calls
