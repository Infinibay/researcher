"""Only verified broker closure may retire the original source peer record."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.tests.runtime.test_broker_peer_close import next_peer


def test_lost_reservation_ack_still_has_a_reconcilable_original_source(
    broker_setup, monkeypatch
):
    _s, registry, peer, broker, storage, path = broker_setup
    commit = storage.commit
    lost = False

    def lost_ack(*args, **kwargs):
        nonlocal lost
        receipt = commit(*args, **kwargs)
        if not lost and kwargs["transition_id"].startswith("broker-reserve:"):
            lost = True
            raise OSError("Lost committed reservation acknowledgement")
        return receipt

    monkeypatch.setattr(storage, "commit", lost_ack)
    with pytest.raises(OSError, match="acknowledgement"):
        start(broker, registry, peer)
    assert lost and registry.inspect(peer)["state"] == "prepared"
    broker.revoke()
    assert [row["id"] for row in broker.project_closed()] == [peer]
    assert registry.inspect(peer)["state"] == "closed" and not path.exists()


def test_separate_process_can_project_verified_retirement_without_live_broker_cache(
    broker_setup,
):
    _s, registry, peer, broker, storage, _path = broker_setup
    result = start(broker, registry, peer)
    try:
        assert result.child.stdout.readline() == b"READY\n"
        broker.revoke()
        config = {
            key: str(storage._paths[key]) for key in ("database", "witness", "mutex")
        }
        config["authority_id"] = storage.authority_id
        program = """import json,os,sys
sys.path.insert(0,sys.argv[1])
from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.peer_broker import PeerBroker
with WitnessedAuthorityJournal(**json.loads(sys.argv[2])) as journal:
 rows=PeerBroker.project_recovered(journal,sys.argv[3])
 print(json.dumps({'peers':[row['id'] for row in rows],'pid':os.getpid()}))
"""
        child = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                program,
                str(Path.cwd()),
                json.dumps(config),
                broker.grant_id,
            ],
            check=False,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert child.returncode == 0, child.stderr
        receipt = json.loads(child.stdout)
        assert receipt["pid"] != os.getpid() and receipt["peers"] == [peer]
        assert registry.inspect(peer)["state"] == "closed"
    finally:
        result.child.close_handles()


def start(broker, registry, peer, key="projection"):
    return broker.run_peer(
        registry,
        peer,
        operation_key=key,
        code="print('READY',flush=True);input();print('LIVE',flush=True)",
    )


def test_source_projection_requires_closure_and_is_event_idempotent(broker_setup):
    from backend.runtime.authority_journal import AuthorityConflict

    s, registry, peer, broker, storage, _path = broker_setup
    result = start(broker, registry, peer)
    try:
        assert result.child.stdout.readline() == b"READY\n"
        with pytest.raises(AuthorityConflict):
            broker.project_closed(operation_id=result.operation_id)
        with pytest.raises(AuthorityConflict):
            type(broker).project_recovered(storage, broker.grant_id)
        assert registry.inspect(peer)["state"] == "bound"
        broker.close_peer(result.operation_id)
        closed = broker.project_closed(operation_id=result.operation_id)
        assert [row["id"] for row in closed] == [peer]
        assert closed[0]["state"] == "closed"
        count = s.c.conn.execute(
            "SELECT COUNT(*) FROM events_log WHERE event_type='peer.closed'"
        ).fetchone()[0]
        assert count == 1
        assert broker.project_closed(operation_id=result.operation_id) == closed
        assert (
            s.c.conn.execute(
                "SELECT COUNT(*) FROM events_log WHERE event_type='peer.closed'"
            ).fetchone()[0]
            == count
        )
    finally:
        result.child.close_handles()


@pytest.mark.parametrize("change", ["namespace", "namespace_missing", "fence"])
def test_projection_cannot_close_a_different_local_binding(broker_setup, change):
    from backend.runtime.authority_journal import AuthorityUncertain

    s, registry, peer, broker, _storage, _path = broker_setup
    sibling = next_peer(registry, peer)
    first = start(broker, registry, peer, "first")
    second = start(broker, registry, sibling, "second")
    try:
        assert (
            first.child.stdout.readline()
            == second.child.stdout.readline()
            == b"READY\n"
        )
        broker.close_peer(first.operation_id)
        if change == "namespace":
            other = registry.inspect(sibling)
            s.c.conn.execute(
                "UPDATE runtime_peers SET init_pid=?,start_ticks=?,init_namespace=? WHERE id=?",
                (
                    other["init_pid"],
                    other["start_ticks"],
                    other["init_namespace"],
                    peer,
                ),
            )
        elif change == "namespace_missing":
            s.c.conn.execute(
                "UPDATE runtime_peers SET state='prepared',init_pid=NULL,start_ticks=NULL,init_namespace=NULL WHERE id=?",
                (peer,),
            )
        else:
            s.c.conn.execute(
                "UPDATE runtime_peers SET fence=fence+1 WHERE id=?", (peer,)
            )
        s.c.conn.commit()
        with pytest.raises(AuthorityUncertain):
            broker.project_closed(operation_id=first.operation_id)
        assert registry.inspect(peer)["state"] == (
            "prepared" if change == "namespace_missing" else "bound"
        )
        second.child.stdin.write(b"continue\n")
        assert second.child.stdout.readline() == b"LIVE\n"
    finally:
        first.child.close_handles()
        second.child.close_handles()


def test_global_retirement_survives_missing_source_projection(broker_setup):
    s, registry, peer, broker, storage, path = broker_setup
    result = start(broker, registry, peer)
    try:
        assert result.child.stdout.readline() == b"READY\n"
        database = Path(s.c.database)
        database.unlink()
        broker.revoke()
        with pytest.raises((sqlite3.OperationalError, FileNotFoundError)):
            broker.project_closed()
        assert not database.exists() and not path.exists()
        assert storage.load().records["broker:active"] is None
    finally:
        result.child.close_handles()


def test_one_mismatched_source_row_rolls_back_all_local_closure_events(broker_setup):
    from backend.runtime.authority_journal import AuthorityUncertain

    s, registry, peer, broker, _storage, _path = broker_setup
    sibling = next_peer(registry, peer)
    first = start(broker, registry, peer, "atomic-first")
    second = start(broker, registry, sibling, "atomic-second")
    try:
        assert (
            first.child.stdout.readline()
            == second.child.stdout.readline()
            == b"READY\n"
        )
        broker.revoke()
        s.c.conn.execute(
            "UPDATE runtime_peers SET fence=fence+1 WHERE id=?", (sibling,)
        )
        s.c.conn.commit()
        with pytest.raises(AuthorityUncertain):
            broker.project_closed()
        assert (
            registry.inspect(peer)["state"]
            == registry.inspect(sibling)["state"]
            == "bound"
        )
        assert (
            s.c.conn.execute(
                "SELECT COUNT(*) FROM events_log WHERE event_type='peer.closed'"
            ).fetchone()[0]
            == 0
        )
    finally:
        first.child.close_handles()
        second.child.close_handles()


def test_historical_grant_without_locator_never_guesses_a_recovery_source(broker_setup):
    from backend.runtime.authority_journal import AuthorityUncertain

    _s, registry, peer, broker, storage, _path = broker_setup
    result = start(broker, registry, peer)
    try:
        assert result.child.stdout.readline() == b"READY\n"
        broker.revoke()
        snapshot = storage.load()
        grant = dict(snapshot.records[broker._grant_key])
        del grant["source_database"]
        storage.commit(
            snapshot,
            transition_id="historical-without-locator",
            puts={broker._grant_key: grant},
        )
        with pytest.raises(AuthorityUncertain, match="locator"):
            type(broker).project_recovered(storage, broker.grant_id)
        assert registry.inspect(peer)["state"] == "bound"
        # This live owner still has the actual original registry, verified again.
        assert [row["id"] for row in broker.project_closed()] == [peer]
    finally:
        result.child.close_handles()


def test_projection_rejects_an_existing_copy_of_the_original_source(
    broker_setup, tmp_path
):
    from backend.runtime.authority_journal import AuthorityUncertain

    s, registry, peer, broker, _storage, _path = broker_setup
    result = start(broker, registry, peer)
    try:
        assert result.child.stdout.readline() == b"READY\n"
        replacement = tmp_path / "replacement.db"
        with sqlite3.connect(replacement) as target:
            s.c.conn.backup(target)
        s.c.conn.close()
        database = Path(s.c.database)
        database.replace(tmp_path / "original.db")
        replacement.replace(database)
        broker.revoke()
        with pytest.raises(AuthorityUncertain, match="origin differs"):
            broker.project_closed()
        with sqlite3.connect(database) as foreign:
            assert (
                foreign.execute(
                    "SELECT state FROM runtime_peers WHERE id=?", (peer,)
                ).fetchone()[0]
                == "bound"
            )
    finally:
        result.child.close_handles()
