"""Per-peer closure must not revoke other participants of the original attempt."""

import sqlite3

import pytest


def next_peer(registry, peer):
    with registry.runs._transaction() as conn:
        _, lease = registry._lease(conn, registry.inspect(peer))
    return registry.prepare(lease, "command")


def test_closing_one_peer_preserves_other_transport_and_global_concession(broker_setup):
    _s, registry, peer, broker, storage, path = broker_setup
    another = next_peer(registry, peer)
    first = broker.run_peer(
        registry, peer, operation_key="one", code="print('FIRST',flush=True);input()"
    )
    second = broker.run_peer(
        registry,
        another,
        operation_key="two",
        code="print('SECOND',flush=True);input();print('STILL LIVE',flush=True)",
    )
    try:
        assert first.child.stdout.readline() == b"FIRST\n"
        assert second.child.stdout.readline() == b"SECOND\n"
        closed = broker.close_peer(first.operation_id)
        assert closed["execution_closed"] is True
        assert (
            path.exists() and storage.load().records["broker:active"] == broker.grant_id
        )
        second.child.stdin.write(b"continue\n")
        assert second.child.stdout.readline() == b"STILL LIVE\n"
        assert second.child.wait(timeout=3) == 0
        before = storage.load().sequence
        assert broker.close_peer(first.operation_id) == closed
        assert storage.load().sequence == before
    finally:
        first.child.close_handles()
        second.child.close_handles()


def test_peer_closure_stops_before_busy_global_sql_and_retries_receipt(broker_setup):
    from backend.runtime.authority_journal import AuthorityBusy

    _s, registry, peer, broker, storage, path = broker_setup
    started = broker.run_peer(
        registry,
        peer,
        operation_key="busy-close",
        code="print('LIVE',flush=True);input()",
    )
    try:
        assert started.child.stdout.readline() == b"LIVE\n"
        with sqlite3.connect(storage._paths["database"]) as writer:
            writer.execute("BEGIN IMMEDIATE")
            try:
                with pytest.raises(AuthorityBusy):
                    broker.close_peer(started.operation_id)
                assert started.child.wait(timeout=1) != 0
                assert path.exists()
            finally:
                writer.rollback()
        assert broker.close_peer(started.operation_id)["execution_closed"] is True
    finally:
        started.child.close_handles()
