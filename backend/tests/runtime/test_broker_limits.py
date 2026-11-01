"""Host-selected shared limits must be finite, durable and fixed before birth."""

from dataclasses import asdict

import pytest


@pytest.mark.parametrize("memory", [True, 0, 63 * 1024**2, 9 * 1024**3, "2147483648"])
def test_broker_memory_policy_rejects_unbounded_or_coerced_input(memory):
    from backend.runtime.peer_broker import BrokerLimits

    with pytest.raises(ValueError):
        BrokerLimits(memory_bytes=memory)


def test_host_limits_apply_before_birth_and_are_durable(broker_setup, monkeypatch):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.peer_broker import BrokerLimits, PeerBroker
    from backend.tests.runtime.test_broker_peer_close import next_peer

    _s, registry, peer, original, storage, path = broker_setup
    limits = BrokerLimits(memory_bytes=2 * 1024**3)
    broker = PeerBroker(storage, original.domain, limits=limits)
    spawn = broker.domain.spawn

    def observed(*args, **kwargs):
        grant = storage.load().records["broker:grant:" + broker.grant_id]
        assert grant["limits"] == asdict(limits)
        assert int((path / "memory.max").read_text()) == limits.memory_bytes
        assert (path / "memory.swap.max").read_text().strip() == "0"
        assert int((path / "pids.max").read_text()) == limits.pids
        return spawn(*args, **kwargs)

    monkeypatch.setattr(broker.domain, "spawn", observed)
    result = broker.run_peer(registry, peer, operation_key="bounded", code="print(137)")
    try:
        assert result.child.wait(timeout=3) == 0
        assert result.child.stdout.read() == b"137\n"
        broker._limits = BrokerLimits()
        sequence = storage.load().sequence
        with pytest.raises(AuthorityConflict):
            broker.run_peer(registry, peer, operation_key="bounded", code="print(137)")
        sibling = next_peer(registry, peer)
        with pytest.raises(AuthorityConflict):
            broker.run_peer(
                registry, sibling, operation_key="changed", code="print(200)"
            )
        assert storage.load().sequence == sequence
        assert int((path / "memory.max").read_text()) == limits.memory_bytes
    finally:
        broker.revoke()
        result.child.close_handles()
