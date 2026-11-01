"""Retained native data never substitutes for original execution authority."""

import sqlite3
from pathlib import Path

import pytest

from backend.tests.runtime.test_broker_native import native_peer


def provision(setup, path):
    from backend.runtime.native_state import NativeState

    _s, registry, command, _broker, journal, _domain = setup
    peer = native_peer(registry, command)
    return NativeState.provision(journal, registry, peer, path), peer


def replacement(registry, peer):
    with registry.runs._transaction() as conn:
        _row, lease = registry._lease(conn, registry._row(conn, peer))
    return registry.prepare(lease, "native")


def test_native_state_is_explicit_private_data_bound_to_original_admission(
    broker_setup, tmp_path
):
    from backend.runtime.native_state import NativeState

    state, peer = provision(broker_setup, tmp_path / "native-state")
    journal = broker_setup[4]
    assert NativeState.load(journal, state.state_id) == state
    record = journal.load().records[state.key]
    assert record["origin"]["attempt_id"] == broker_setup[1].inspect(peer)["attempt_id"]
    assert record["thread_id"] is None and record["turn"] is None
    assert Path(state.path).stat().st_mode & 0o777 == 0o700
    assert (Path(state.path) / "home").stat().st_mode & 0o777 == 0o700
    assert not journal.load().records.get("broker:active")


def test_attempt_cannot_create_another_home_to_reset_native_dispatch(
    broker_setup, tmp_path
):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.native_state import NativeState

    _state, peer = provision(broker_setup, tmp_path / "native-state")
    with pytest.raises(AuthorityConflict, match="already"):
        NativeState.provision(
            broker_setup[4], broker_setup[1], peer, tmp_path / "reset-state"
        )
    assert not (tmp_path / "reset-state").exists()


@pytest.mark.parametrize("defect", ["absent", "replaced", "credentials"])
def test_native_state_reopen_does_not_adopt_or_recreate_data(
    broker_setup, tmp_path, defect
):
    from backend.runtime.native_state import NativeState

    state, _peer = provision(broker_setup, tmp_path / "native-state")
    root = Path(state.path)
    if defect == "credentials":
        (root / "home/auth.json").write_text('{"OPENAI_API_KEY":"HOST_CANARY"}')
    else:
        root.rename(tmp_path / "retired-state")
        if defect == "replaced":
            root.mkdir(mode=0o700)
            (root / "home").mkdir(mode=0o700)
    with pytest.raises((ValueError, FileNotFoundError), match="state|auth|No such"):
        NativeState.load(broker_setup[4], state.state_id)
    if defect == "absent":
        assert not root.exists()


def test_native_state_cannot_be_provisioned_in_source(broker_setup):
    from backend.runtime.native_state import NativeState

    s, registry, command, _broker, journal, _domain = broker_setup
    with pytest.raises(ValueError, match="source"):
        NativeState.provision(
            journal, registry, native_peer(registry, command), s.workspace / "state"
        )
    assert not (s.workspace / "state").exists()


def test_native_state_record_rejects_another_origin_before_reservation(
    broker_setup, tmp_path
):
    from backend.runtime.authority_journal import AuthorityConflict

    state, peer = provision(broker_setup, tmp_path / "native-state")
    journal = broker_setup[4]
    admission = broker_setup[1].admission(peer)
    before = journal.load().sequence
    with pytest.raises(AuthorityConflict, match="another original attempt"):
        state.reservation(
            journal,
            journal.load(),
            {**admission, "context_version": admission["context_version"] + 1},
            "new-grant",
            "new-operation",
        )
    assert journal.load().sequence == before


async def test_real_codex_thread_survives_original_native_peer_closure_without_model(
    broker_setup, native_asset, tmp_path
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.workspaces import PEER_WORKSPACE

    _s, registry, _command, broker, journal, domain = broker_setup
    state, peer = provision(broker_setup, tmp_path / "native-state")
    catalog = [
        {
            "name": "fixture_echo",
            "description": "Offline fixture",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]
    async with AsyncPeerBroker(broker) as owner:
        async with JsonRpcClient(
            owner.native(
                registry,
                peer,
                operation_key="first",
                asset=native_asset,
                native_state=state,
            )
        ) as rpc:
            await rpc.request(
                "initialize",
                {
                    "clientInfo": {"name": "state-offline", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            await rpc.notify("initialized")
            result = await rpc.request(
                "thread/start",
                {
                    "model": "gpt-6.1-sol",
                    "modelProvider": "openai",
                    "cwd": str(PEER_WORKSPACE),
                    "sandbox": "read-only",
                    "dynamicTools": catalog,
                },
            )
            thread = result["thread"]["id"]
            # Codex intentionally materializes a fresh rollout only after its
            # first user message. Seed fixed TEST history without a model turn;
            # production never uses injection as a lost-thread restore fallback.
            await rpc.request(
                "thread/inject_items",
                {
                    "threadId": thread,
                    "items": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "OFFLINE_PERSISTENCE_FIXTURE",
                                }
                            ],
                        }
                    ],
                },
            )
        assert registry.inspect(peer)["state"] == "closed" and domain.exists()
        assert any((Path(state.path) / "home").iterdir())
        other = replacement(registry, peer)
        async with JsonRpcClient(
            owner.native(
                registry,
                other,
                operation_key="second",
                asset=native_asset,
                native_state=state,
            )
        ) as rpc:
            await rpc.request(
                "initialize", {"clientInfo": {"name": "state-offline", "version": "1"}}
            )
            await rpc.notify("initialized")
            read = (
                await rpc.request(
                    "thread/read", {"threadId": thread, "includeTurns": False}
                )
            )["thread"]
            assert read["id"] == thread and read["cwd"] == str(PEER_WORKSPACE)
            result = await rpc.request(
                "thread/resume", {"threadId": thread, "excludeTurns": True}
            )
            assert result["thread"]["id"] == thread
            assert (await rpc.request("account/read", {"refreshToken": False}))[
                "account"
            ] is None
        assert not (Path(state.path) / "home/auth.json").exists()
    assert Path(state.path).exists() and not domain.exists()
    assert all(
        op.get("execution_closed")
        for key, op in journal.load().records.items()
        if key.startswith("broker:op:")
    )


def test_native_peer_upgrade_retains_history_and_one_live_native(tmp_path):
    from backend.db.migrations import apply_sql_resource
    from backend.db.peer_kind_migration import migrate_ken_peers
    from backend.tests.runtime.test_ken_peer_migration import legacy, snapshot

    with legacy(tmp_path) as conn:
        migrate_ken_peers(conn)
        before = snapshot(conn)
        apply_sql_resource(
            conn, Path(__file__).parents[2] / "db/native_state_schema.sql"
        )
        assert snapshot(conn) == before
        insert = "INSERT INTO runtime_peers(id,attempt_id,kind,protocol_version,state,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at) VALUES(?, 'attempt','native',1,'prepared',9,123,456,'boot',789,4.5)"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert, ("concurrent",))
        conn.execute(
            "UPDATE runtime_peers SET state='closed',reason='verified',closed_at=5 WHERE id='native'"
        )
        conn.execute(insert, ("replacement",))
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM runtime_peers WHERE kind='native'"
            ).fetchone()[0]
            == 2
        )
        assert conn.execute("SELECT peer_id FROM custom_ref").fetchone()[0] == "native"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_native_peer_index_migration_failure_rolls_back(tmp_path):
    from backend.db.migrations import apply_sql_resource
    from backend.db.peer_kind_migration import migrate_ken_peers
    from backend.tests.runtime.test_ken_peer_migration import legacy

    with legacy(tmp_path) as conn:
        migrate_ken_peers(conn)
        before = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='idx_one_inference_peer_kind'"
        ).fetchone()[0]
        conn.set_authorizer(
            lambda action, *_: (
                sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_CREATE_INDEX
                else sqlite3.SQLITE_OK
            )
        )
        try:
            with pytest.raises(sqlite3.DatabaseError):
                apply_sql_resource(
                    conn, Path(__file__).parents[2] / "db/native_state_schema.sql"
                )
        finally:
            conn.set_authorizer(None)
        assert (
            conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='idx_one_inference_peer_kind'"
            ).fetchone()[0]
            == before
        )
        assert not conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=32"
        ).fetchone()
