"""Complete host composition over original owned peers, without model calls."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_broker_ken import ken_peer
from backend.tests.runtime.test_broker_native import native_peer
from backend.tests.runtime.test_ken_mediation import Peer, tool


@pytest.fixture
def composed_setup(broker_setup, ken_installation, tmp_path, code_host_asset):
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
        code_host=code_host_asset,
    )


def native(
    owner,
    setup,
    *,
    state=None,
    resume_thread_id=None,
    operation_key="inference",
    peer_id=None,
):
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.codex_session import CodexSession, ExecutionLimits
    from backend.runtime.egress_proxy import EgressPolicy
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.workspaces import PEER_WORKSPACE

    endpoint = owner.native(
        setup.registry,
        peer_id or native_peer(setup.registry, setup.command),
        operation_key=operation_key,
        asset=setup.asset,
        network=NativeNetwork.inspect(
            resolver="/etc/resolv.conf", ca_bundle="/etc/ssl/certs/ca-certificates.crt"
        ),
        egress=EgressPolicy(("allowed.example",)),
        host_tools=True,
        code_host=setup.code_host,
        native_state=state,
    )
    return CodexSession(
        JsonRpcClient(endpoint),
        workspace=PEER_WORKSPACE,
        model="controlled-only",
        limits=ExecutionLimits(5, 2, 2, 10, 1000),
        sandbox="read-only",
        resume_thread_id=resume_thread_id,
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


async def test_code_host_startup_failure_never_admits_thread_or_turn(composed_setup):
    from backend.runtime.broker_inference import broker_inference
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.business_mediation import BusinessTools

    s = composed_setup
    s.code_host = CodexAsset.inspect("/usr/bin/false")
    business = await BusinessTools.connect(Peer([tool("researcher_source_read")]))
    async with AsyncPeerBroker(s.broker) as owner:
        session = native(owner, s)
        methods = []
        request = session.rpc.request

        async def record(method, *args, **kwargs):
            methods.append(method)
            return await request(method, *args, **kwargs)

        session.rpc.request = record
        endpoint = owner.ken(
            s.registry,
            ken_peer(s.registry, s.command),
            operation_key="ken",
            installation=s.installation,
        )
        with pytest.raises(RuntimeError, match="Code-mode host readiness failed"):
            async with broker_inference(
                session,
                endpoint,
                prepared_operation=s.prepared,
                business=business,
                analysis=SimpleNamespace(catalog=[]),
            ):
                pytest.fail("Failed executable admitted inference")
        assert (
            "command/exec" in methods
            and "thread/start" not in methods
            and "turn/start" not in methods
        )
        assert session.turns_sent == 0 and session.thread_id is None


@pytest.mark.parametrize("dispatch", ["completed", "lost_reservation_ack"])
async def test_retained_composition_resumes_same_thread_and_never_replays_turn(
    composed_setup, tmp_path, monkeypatch, dispatch
):
    from backend.runtime.broker_inference import broker_inference
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.business_mediation import BusinessTools
    from backend.runtime.native_state import NativeState
    from backend.tests.runtime.test_native_state import replacement

    s = composed_setup
    original_peer = native_peer(s.registry, s.command)
    state = NativeState.provision(
        s.storage, s.registry, original_peer, tmp_path / "state"
    )
    business = await BusinessTools.connect(Peer([tool("researcher_source_read")]))
    analysis = SimpleNamespace(catalog=[])

    def ken(owner, key):
        return owner.ken(
            s.registry,
            ken_peer(s.registry, s.command),
            operation_key=key,
            installation=s.installation,
        )

    async with AsyncPeerBroker(s.broker) as owner:
        first = native(owner, s, state=state)
        async with broker_inference(
            first,
            ken(owner, "ken-first"),
            prepared_operation=s.prepared,
            business=business,
            analysis=analysis,
        ) as session:
            if dispatch == "lost_reservation_ack":
                from backend.runtime.authority_journal import AuthorityUncertain

                commit = s.storage.commit

                def uncertain(snapshot, **kwargs):
                    receipt = commit(snapshot, **kwargs)
                    if kwargs["transition_id"].startswith("native-turn-reserve:"):
                        raise AuthorityUncertain("Lost dispatch reservation receipt")
                    return receipt

                monkeypatch.setattr(s.storage, "commit", uncertain)
                with pytest.raises(AuthorityUncertain, match="Lost dispatch"):
                    await session.run("inspect fact")
                assert first.turns_sent == 0
                assert (
                    "turn/start"
                    not in (await first.rpc.request("test/summary", {}))["methods"]
                )
            else:
                assert (await session.run("inspect fact")).status == "completed"
            thread_id = session.thread_id
        second = native(
            owner,
            s,
            state=state,
            resume_thread_id=thread_id,
            operation_key="resume",
            peer_id=replacement(s.registry, original_peer),
        )
        async with broker_inference(
            second,
            ken(owner, "ken-second"),
            prepared_operation=s.prepared,
            business=business,
            analysis=analysis,
        ) as restored:
            assert restored.thread_id == thread_id
            with pytest.raises(RuntimeError, match="replay"):
                await restored.run("inspect fact")
            summary = await second.rpc.request("test/summary", {})
            assert (
                "thread/resume" in summary["methods"]
                and "thread/start" not in summary["methods"]
            )
            assert "turn/start" not in summary["methods"]
            assert set(summary["catalog_names"]) == {
                t["name"] for t in restored.catalog
            }


@pytest.mark.parametrize(
    "change",
    ["catalog", "model", "instructions", "lost_thread_receipt", "stored_metadata"],
)
async def test_retained_composition_rejects_changed_or_unknown_session_before_resume(
    composed_setup, tmp_path, change
):
    from backend.runtime.broker_inference import broker_inference
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.business_mediation import BusinessTools
    from backend.runtime.native_state import NativeState
    from backend.tests.runtime.test_native_state import replacement

    s = composed_setup
    original_peer = native_peer(s.registry, s.command)
    state = NativeState.provision(
        s.storage, s.registry, original_peer, tmp_path / "state"
    )
    business = await BusinessTools.connect(Peer([tool("researcher_source_read")]))
    async with AsyncPeerBroker(s.broker) as owner:
        first = native(owner, s, state=state)
        async with broker_inference(
            first,
            owner.ken(
                s.registry,
                ken_peer(s.registry, s.command),
                operation_key="k1",
                installation=s.installation,
            ),
            prepared_operation=s.prepared,
            business=business,
            analysis=SimpleNamespace(catalog=[]),
        ):
            pass
        thread = first.thread_id
        if change == "catalog":
            business.catalog[0]["description"] = "changed"
        if change == "lost_thread_receipt":
            snapshot = s.storage.load()
            row = snapshot.records[state.key]
            s.storage.commit(
                snapshot,
                transition_id="fixture-lost-thread",
                puts={state.key: {**row, "thread_id": None}},
            )
        if change == "stored_metadata":
            import json

            file = Path(state.path) / "home/controlled-thread.json"
            file.write_text(
                json.dumps({**json.loads(file.read_text()), "cwd": "/other-project"})
            )
        second = native(
            owner,
            s,
            state=state,
            resume_thread_id=thread,
            operation_key="resume",
            peer_id=replacement(s.registry, original_peer),
        )
        if change == "model":
            second.model = "another-model"
        if change == "instructions":
            second.developer_instructions = "another instruction"
        methods = []
        request = second.rpc.request

        async def observed(method, *args, **kwargs):
            methods.append(method)
            return await request(method, *args, **kwargs)

        second.rpc.request = observed
        with pytest.raises(RuntimeError, match="intent|receipt"):
            async with broker_inference(
                second,
                owner.ken(
                    s.registry,
                    ken_peer(s.registry, s.command),
                    operation_key="k2",
                    installation=s.installation,
                ),
                prepared_operation=s.prepared,
                business=business,
                analysis=SimpleNamespace(catalog=[]),
            ):
                pytest.fail("Changed or unknown native state resumed")
        assert (
            "thread/resume" not in methods
            and "thread/start" not in methods
            and "turn/start" not in methods
        )
