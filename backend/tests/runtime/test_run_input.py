"""A turn uses its exact frozen host input, with bounded and scoped continuity."""

import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator

CATALOG = [
    {
        "name": "fixture_read",
        "description": "Read recorded evidence",
        "inputSchema": {"type": "object", "properties": {}},
    }
]
INSTRUCTIONS = "Use the current request. Historical proposals are not authority."


def prepare(c, *, thread="conversation"):
    run = c.store.admit(c.spec, conversation_thread=thread)
    lease = c.store.claim(101, run.run_id, "host")
    c.store.bind_thread(lease, thread_id="native-thread")
    return run, lease


def reserve(c, lease, **kwargs):
    return c.store.reserve_input(
        lease,
        workspace="/host/alpha",
        catalog_hash=hashlib.sha256(
            json.dumps(
                CATALOG, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest(),
        model="fixture-model",
        catalog=CATALOG,
        developer_instructions=INSTRUCTIONS,
        limits=ExecutionLimits(60, 30, 1, 10, 100),
        **kwargs,
    )


def message(c, text, *, thread="conversation", project=101, sender="user"):
    return c.conn.execute(
        "INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,conversation_type,message) VALUES(?,?,?,'researcher','user_to_agent',?)",
        (project, thread, sender, text),
    ).lastrowid


def test_frozen_input_contains_prior_task_exchange_but_not_future_or_other_scope(
    coordination,
):
    c = coordination
    old = c.store.admit(c.spec, conversation_thread="conversation")
    old_lease = c.store.claim(101, old.run_id, "host")
    c.store.finish(
        old_lease, native_status="completed", summary="Provisional: no proof yet."
    )
    c.store.cancel(101, old.run_id)
    note = message(c, "An earlier note, without native submission proof.")
    c.conn.commit()
    new_spec = replace(
        c.spec,
        operation_key="continue",
        prompt="Check the earlier proposal with base 200.",
    )
    run = c.store.admit(new_spec, conversation_thread="conversation")
    lease = c.store.claim(101, run.run_id, "host")
    c.store.bind_thread(lease, thread_id="native-next")
    future = message(c, "Late note must not enter this turn.")
    c.conn.commit()
    frozen = reserve(c, lease)
    payload = json.loads(frozen.input_text)
    assert payload["request"] == "Check the earlier proposal with base 200."
    history = payload["conversation"]
    assert history["thread_id"] == "conversation"
    assert [m["message_id"] for m in history["messages"]] == [1, 2, note]
    assert [m["kind"] for m in history["messages"]] == [
        "owner_instruction",
        "agent_proposal",
        "unattributed_record",
    ]
    assert history["messages"][1]["content"] == "Provisional: no proof yet."
    assert history["messages"][1]["run_status_at_snapshot"] == "cancelled"
    assert history["messages"][2]["recorded_sender"] == "user"
    assert all(m["message_id"] != future for m in history["messages"])
    assert frozen.input_sha256 == hashlib.sha256(frozen.input_text.encode()).hexdigest()
    # This is exact input evidence, not an inference-start/understanding receipt.
    assert c.store.input_record(101, run.run_id)["native_start_observed"] is False


def test_other_tasks_in_a_legacy_mixed_thread_are_excluded_and_reported(coordination):
    c = coordination
    other = c.store.admit(
        replace(c.spec, task_id=1002, operation_key="other"),
        conversation_thread="conversation",
    )
    c.store.cancel(101, other.run_id)
    # A legacy/unbound thread may retain a message linked to another task.
    c.conn.execute(
        "UPDATE conversation_threads SET task_id=NULL WHERE thread_id='conversation'"
    )
    c.conn.commit()
    run, lease = prepare(c)
    frozen = reserve(c, lease)
    payload = json.loads(frozen.input_text)
    assert payload["conversation"]["messages"] == []
    assert payload["conversation"]["other_task_messages_excluded"] == 1
    assert payload["scope"]["task_id"] == 1001
    assert c.store.input_record(101, run.run_id)["input_text"] == frozen.input_text


def test_snapshot_survives_message_edits_and_repeat_reservation_never_replays(
    coordination,
):
    c = coordination
    c.conn.execute(
        "INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('conversation',101,'user_chat')"
    )
    original = message(c, "Original note")
    c.conn.commit()
    run, lease = prepare(c)
    frozen = reserve(c, lease)
    c.conn.execute(
        "UPDATE chat_messages SET message='Changed later' WHERE id=?", (original,)
    )
    c.conn.commit()
    assert reserve(c, lease) is None
    record = c.store.input_record(101, run.run_id)
    assert record["input_text"] == frozen.input_text
    assert (
        "Original note" in record["input_text"]
        and "Changed later" not in record["input_text"]
    )
    assert (
        record["developer_instructions"] == INSTRUCTIONS
        and record["business_catalog"] == CATALOG
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        c.conn.execute("UPDATE runtime_input_snapshots SET input_text='{}'")
    c.conn.rollback()


def test_input_event_failure_rolls_back_dispatch_budget_and_snapshot(coordination):
    c = coordination
    _run, lease = prepare(c)
    c.conn.execute(
        "CREATE TRIGGER fail_input BEFORE INSERT ON events_log WHEN new.event_type='run.input_frozen' BEGIN SELECT RAISE(ABORT,'input event failed'); END"
    )
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="input event failed"):
        reserve(c, lease)
    for table in (
        "runtime_input_snapshots",
        "runtime_inference_dispatches",
        "runtime_project_budgets",
    ):
        assert c.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert not [
        e for e in c.store.events(101).events if e.event_type == "run.dispatch_reserved"
    ]


def test_oversized_history_is_not_silently_truncated_or_reserved(coordination):
    c = coordination
    c.conn.execute(
        "INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('conversation',101,'user_chat')"
    )
    for _ in range(201):
        message(c, "Keep the important final condition.")
    c.conn.commit()
    _, lease = prepare(c)
    with pytest.raises(RunConflict, match="input|history|context"):
        reserve(c, lease)
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )


def test_snapshot_preserves_context_strength_and_excludes_other_projects(coordination):
    c = coordination
    c.conn.execute(
        "INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('foreign',202,'user_chat')"
    )
    message(c, "Foreign private context", thread="foreign", project=202)
    c.conn.commit()
    version = c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=1,
        operation_key="example",
        statement="Example: base 200 gives tax 42",
        source_kind="user_example",
        source_reference="owner-example",
    )
    c.spec = replace(c.spec, context_version=version)
    _, lease = prepare(c)
    frozen = reserve(c, lease)
    data = json.loads(frozen.input_text)
    assert data["corrections"][0]["source_kind"] == "user_example"
    assert "Foreign private context" not in frozen.input_text
    assert data["context_version"] == 2


async def test_product_dispatch_sends_the_recorded_bytes_and_continues_its_product_thread(
    service_setup,
):
    s = service_setup
    native = ControlledInference(s)
    native.release.set()
    # The production port must expose the exact host-owned instructions/catalog.
    native.developer_instructions = INSTRUCTIONS
    native.catalog = CATALOG
    async with coordinator(s, native) as service:
        first = await service.submit(s.c.spec, conversation_thread="conversation")
        await service.wait(first.run_id)
        await service.stop(101, first.run_id)
        second = await service.submit(
            replace(
                s.c.spec, operation_key="next", prompt="Recheck the earlier proposal."
            ),
            conversation_thread="conversation",
        )
        await service.wait(second.run_id)
        record = s.c.store.input_record(101, second.run_id)
        assert native.prompts[-1] == record["input_text"]
        assert record["native_start_observed"] is True
        data = json.loads(native.prompts[-1])
        assert any(
            m["kind"] == "agent_proposal" for m in data["conversation"]["messages"]
        )
        assert len(native.prompts) == 2


async def test_a_previously_reserved_input_is_unknown_not_permission_to_send_again(
    service_setup, monkeypatch
):
    s = service_setup
    native = ControlledInference(s)
    original = s.c.store.reserve_input

    def existing(*args, **kwargs):
        original(*args, **kwargs)
        # Simulates finding an earlier durable reservation, no replay.

    monkeypatch.setattr(s.c.store, "reserve_input", existing)
    async with coordinator(s, native) as service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        result = s.c.store.get(101, run.run_id)
        assert result.issue["inference_started"] is None
        assert not native.prompts


def test_input_bytes_limit_keeps_the_final_constraint_or_refuses_the_whole_input(
    coordination,
):
    c = coordination
    c.conn.execute(
        "UPDATE tasks SET description=? WHERE id=1001",
        ("é" * 600000 + " NEVER MODIFY FILES",),
    )
    c.conn.commit()
    c.spec = replace(c.spec, context_version=2)
    _, lease = prepare(c)
    with pytest.raises(RunConflict, match="input"):
        reserve(c, lease)
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_input_snapshots").fetchone()[0]
        == 0
    )


async def test_owner_reads_frozen_input_without_reconstructing_historical_runs(
    coordination,
):
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = coordination
    run, lease = prepare(c)
    frozen = reserve(c, lease)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )
    path = f"/api/projects/101/runs/{run.run_id}/input"
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as anonymous:
            assert (await anonymous.get(path)).status_code == 401
        async with owner_client(app) as owner:
            response = await owner.get(path)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["input_sha256"] == frozen.input_sha256
            assert response.json()["input_text"] == frozen.input_text
            assert (await owner.get(path.replace("/101/", "/202/"))).status_code == 404
            old = c.store.admit(replace(c.spec, task_id=1002, operation_key="old"))
            missing = await owner.get(f"/api/projects/101/runs/{old.run_id}/input")
            assert missing.json()["available"] is False
            assert missing.json()["reason"] == "no_record"
