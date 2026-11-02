"""Native search policy and provenance contracts, without account inference."""

import json

import pytest


def test_search_observation_is_bounded_and_distinguishes_missing_results():
    """Optional native results must never become invented captured evidence."""
    from backend.runtime.native_search import search_observation

    item = {"type": "webSearch", "id": "s1", "query": "what changed?"}
    observation = search_observation(item, mode="live", thread_id="th", turn_id="t")
    assert observation["results_state"] == "not_supplied"
    assert observation["candidate_urls"] == []
    assert observation["evidence_status"] == "uncaptured_search_observation"
    item["results"] = [
        {"url": "https://example.org/paper", "title": "Paper", "token": "SECRET"},
        {"url": "https://user:SECRET@example.org/private"},
        {"url": "javascript:alert(1)"},
    ]
    observation = search_observation(item, mode="live", thread_id="th", turn_id="t")
    assert observation["results_state"] == "supplied"
    assert observation["candidate_urls"] == ["https://example.org/paper"]
    assert "SECRET" not in json.dumps(observation)
    item["results"] = [{"url": "https://example.org/" + "a" * 4000}]
    observation = search_observation(item, mode="live", thread_id="th", turn_id="t")
    assert observation["candidate_urls"] == [] and observation["truncated"] is True
    item["query"] = "á" * 100000
    item["results"] = [{"url": "https://example.org/" + "a" * 4000}] * 1000
    observation = search_observation(item, mode="live", thread_id="th", turn_id="t")
    assert len(json.dumps(observation, ensure_ascii=False).encode()) < 32000
    assert observation["truncated"] is True
    item["query"] = "\x00" * 10000
    item["action"] = {
        "type": "search",
        "query": "\x00" * 10000,
        "queries": ["\x00" * 10000] * 8,
    }
    item["results"] = [
        {"url": "https://example.org/" + chr(92) * 1800 + str(i)} for i in range(10)
    ]
    observation = search_observation(item, mode="live", thread_id="th", turn_id="t")
    assert len(json.dumps(observation, ensure_ascii=False).encode()) < 32000


@pytest.mark.parametrize("mode", ["live", "cached", "indexed"])
async def test_real_native_search_mode_is_manifested_without_account(
    broker_setup, native_asset, code_host_asset, mode
):
    """The actual native process must read the same policy as its launch receipt."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.egress_proxy import EgressPolicy
    from backend.runtime.native_network import NativeNetwork
    from backend.tests.runtime.test_broker_native import native_peer

    _, registry, command, broker, storage, _ = broker_setup
    async with AsyncPeerBroker(broker) as owner:
        endpoint = owner.native(
            registry,
            native_peer(registry, command),
            operation_key="search-policy",
            asset=native_asset,
            host_tools=True,
            code_host=code_host_asset,
            network=NativeNetwork.inspect(
                resolver="/etc/resolv.conf",
                ca_bundle="/etc/ssl/certs/ca-certificates.crt",
            ),
            egress=EgressPolicy(("chatgpt.com",)),
            web_search=mode,
        )
        async with JsonRpcClient(endpoint) as rpc:
            await rpc.request(
                "initialize", {"clientInfo": {"name": "search-test", "version": "1"}}
            )
            await rpc.notify("initialized")
            config = (await rpc.request("config/read", {"includeLayers": False}))[
                "config"
            ]
            assert config["web_search"] == mode
            assert config["features"]["shell_tool"] is False
            assert (await rpc.request("account/read", {"refreshToken": False}))[
                "account"
            ] is None
            manifest = storage.load().records["broker:op:" + endpoint._operation][
                "runtime_manifest"
            ]
            assert manifest["web_search"] == mode


def test_search_cannot_be_enabled_on_an_unowned_native_peer(broker_setup, native_asset):
    """Diagnostic and command sessions must retain their disabled search policy."""
    from backend.tests.runtime.test_broker_native import native_peer

    _, registry, command, broker, storage, _ = broker_setup
    with pytest.raises(ValueError, match="search|Search"):
        broker.run_native(
            registry,
            native_peer(registry, command),
            operation_key="invalid-search",
            asset=native_asset,
            web_search="live",
        )
    assert storage.load().records.get("broker:active") is None


@pytest.mark.parametrize("stop", ["cancel", "correct"])
def test_late_search_remains_old_context_evidence_without_authority(coordination, stop):
    """Late discovery cannot revive a cancelled run or adopt a corrected context."""
    from backend.runtime.native_search import search_observation
    from backend.runtime.sqlite_runs import SQLiteRunStore

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "host")
    c.store.bind_native(lease, thread_id="native-1", turn_id="turn-1")
    if stop == "cancel":
        c.store.cancel(101, run.run_id)
    else:
        c.store.correct_context(
            project_id=101,
            task_id=1001,
            expected_version=1,
            operation_key="correct-before-late-search",
            statement="Use the revised scope.",
            source_kind="user_message",
            source_reference="message-42",
        )
    payload = search_observation(
        {
            "id": "s1",
            "query": "old context query",
            "results": [{"url": "https://example.org/old"}],
        },
        mode="live",
        thread_id="native-1",
        turn_id="turn-1",
    )
    status_before_observation = c.store.get(101, run.run_id).status
    event_id = c.store.observe_native(
        lease,
        observation_key="late-search",
        native_kind="tool.completed",
        payload=payload,
    )
    reopened = SQLiteRunStore(c.database, clock=lambda: c.now[0])
    assert not reopened.attempt_active(lease)
    assert reopened.get(101, run.run_id).status == status_before_observation
    assert status_before_observation == (
        "cancelling" if stop == "cancel" else "reconciling"
    )
    event = next(e for e in reopened.events(101).events if e.event_id == event_id)
    assert event.data["context_version"] == 1
    assert event.data["payload"]["candidate_urls"] == ["https://example.org/old"]
    assert c.conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )
