"""Explicit successor deliveries preserve original failures and effects; SQLite peer witnesses here are synthetic."""

import json

import pytest

from backend.runtime.contracts import RunConflict
from backend.runtime.peer_registry import AttemptPeers
from backend.tests.runtime.test_plan_execution import accepted_plan, authorize


def interrupted_delivery(service_setup, *, close=True):
    """Admit one original root and record cancellation without inventing peer closure."""
    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    eid = receipt["execution_id"]
    spec, binding = executions.prepare(eid, graph["tasks"]["learn"])
    run = s.c.store.admit(spec, binding=binding)
    lease, peers = AttemptPeers.claim(s.c.store, 101, run.run_id, "fixture-owner")
    s.c.store.cancel(101, run.run_id)
    if close:
        for peer in peers.ids.values():
            peers.registry.close(peer)
        s.c.store.retire_withdrawn(lease)
    delivery = next(
        d
        for d in executions.state(101, plan.run_id)["execution"]["deliveries"]
        if d["run_id"] == run.run_id
    )
    return s, plan, executions, eid, delivery, run, lease, peers


def test_owner_continuation_creates_one_successor_and_keeps_original_history(
    service_setup,
):
    """Duplicate owner requests and a store reopen cannot replace/replay the stopped run or fork its causal delivery."""
    from backend.planning.execution import PlanExecutions

    s, plan, executions, eid, original, run, lease, _ = interrupted_delivery(
        service_setup
    )
    preview = executions.continuation_state(101, eid, original["delivery_id"])
    assert preview["eligible"], preview
    assert preview["snapshot"]["previous_run"]["run_id"] == run.run_id
    assert preview["snapshot"]["previous_run"]["attempt_id"] == lease.attempt_id
    command = {
        "operation_key": "owner-continue",
        "snapshot_sha256": preview["snapshot_sha256"],
    }
    receipt = executions.continue_delivery(101, eid, original["delivery_id"], **command)
    assert (
        executions.continue_delivery(101, eid, original["delivery_id"], **command)
        == receipt
    )
    assert s.c.store.get(101, run.run_id).status == "cancelled"
    assert (
        len(s.c.store.task_runs(101, run.task_id)) == 1
    )  # Authorization alone starts no inference.
    spec, binding = PlanExecutions(s.c.store).prepare(eid, run.task_id)
    successor = s.c.store.admit(spec, binding=binding)
    assert successor.run_id != run.run_id
    with s.c.store._transaction() as conn:
        packet = executions.input(conn, s.c.store._row(conn, 101, successor.run_id))
    assert packet["continuation"]["previous_run"]["run_id"] == run.run_id
    assert packet["continuation"]["owner_operation_key"] == "owner-continue"
    assert packet["delivery_id"] == receipt["delivery_id"]
    history = executions.state(101, plan.run_id)["execution"]["deliveries"]
    assert len(history) == 3
    assert next(d for d in history if d["run_id"] == run.run_id)["current"] is False
    assert (
        next(d for d in history if d["run_id"] == successor.run_id)[
            "predecessor_delivery_id"
        ]
        == original["delivery_id"]
    )
    with pytest.raises(RunConflict):
        executions.continue_delivery(
            101, eid, original["delivery_id"], **{**command, "operation_key": "fork"}
        )


def test_continuation_refuses_unclosed_attempt_and_obsolete_owner_snapshot(
    service_setup,
):
    """A terminal label or old snapshot cannot substitute for current closure and exact owner evidence."""
    s, plan, executions, eid, original, run, lease, peers = interrupted_delivery(
        service_setup, close=False
    )
    did = original["delivery_id"]
    preview = executions.continuation_state(101, eid, did)
    assert not preview["eligible"]
    with pytest.raises(RunConflict):
        executions.continue_delivery(
            101, eid, did, operation_key="too-early", snapshot_sha256="0" * 64
        )
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.retire_withdrawn(lease)
    preview = executions.continuation_state(101, eid, did)
    # A late observation is not silently folded into the decision the owner saw.
    s.c.conn.execute(
        "UPDATE runtime_runs SET issue_json=? WHERE id=?",
        (json.dumps({"code": "late_observation"}), run.run_id),
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="snapshot|obsolete|changed"):
        executions.continue_delivery(
            101,
            eid,
            did,
            operation_key="stale-continuation",
            snapshot_sha256=preview["snapshot_sha256"],
        )
    assert len(executions.state(101, plan.run_id)["execution"]["deliveries"]) == 2


def test_continuation_keeps_paused_dispatch_and_rejects_changed_graph(service_setup):
    """New owner permission for one successor cannot resume a paused graph or reuse corrected premises."""
    s, plan, executions, eid, original, run, _, _ = interrupted_delivery(service_setup)
    manifest = executions.state(101, plan.run_id)["execution"]["manifest_sha256"]
    executions.control(
        101, eid, operation_key="pause", manifest_sha256=manifest, status="paused"
    )
    preview = executions.continuation_state(101, eid, original["delivery_id"])
    executions.continue_delivery(
        101,
        eid,
        original["delivery_id"],
        operation_key="continue-while-paused",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    assert executions.prepare(eid, run.task_id) is None
    executions.control(
        101, eid, operation_key="resume", manifest_sha256=manifest, status="active"
    )
    assert executions.prepare(eid, run.task_id) is not None
    s.c.conn.execute(
        "UPDATE tasks SET description='A corrected premise' WHERE id=?", (run.task_id,)
    )
    s.c.conn.commit()
    assert executions.prepare(eid, run.task_id) is None
    assert executions.state(101, plan.run_id)["execution"]["current"] is False


async def test_owner_http_continuation_survives_reply_loss_and_uses_existing_dispatcher(
    service_setup,
):
    """Strict owner controls retain the original decision across restart; only resume dispatches one new native author input with causal history."""
    import asyncio

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_plan_execution import DeliveryInference
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, plan, executions, eid, original, run, _, _ = interrupted_delivery(service_setup)
    manifest = executions.state(101, plan.run_id)["execution"]["manifest_sha256"]
    executions.control(
        101,
        eid,
        operation_key="pause-before-continuation",
        manifest_sha256=manifest,
        status="paused",
    )
    path = f"/api/projects/101/plan-executions/{eid}/deliveries/{original['delivery_id']}/continuation"
    inference = DeliveryInference(s)
    runtime = coordinator(s, inference)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        preview = await client.get(path)
        assert preview.status_code == 200, preview.text
        command = {
            "operation_key": "http-continue",
            "snapshot_sha256": preview.json()["snapshot_sha256"],
        }
        assert (
            await client.post(
                path, json=command, headers={"X-Researcher-CSRF": "invalid"}
            )
        ).status_code == 403
        assert (
            await client.post(path, json={**command, "prompt": "invented"})
        ).status_code == 422
        assert (
            await client.post(path.replace("/101/", "/202/"), json=command)
        ).status_code == 404
        first = await client.post(path, json=command)
        assert first.status_code == 200, first.text
        assert inference.inputs == []
        assert (await client.post(path, json=command)).json() == first.json()
    # The first response can be lost; reopening the owner returns the same receipt.
    inference = DeliveryInference(s)
    runtime = coordinator(s, inference)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        assert (await client.post(path, json=command)).json() == first.json()
        executions.control(
            101,
            eid,
            operation_key="resume-successor",
            manifest_sha256=manifest,
            status="active",
        )
        await runtime.dispatch_planned_work()
        await asyncio.wait_for(inference.started.wait(), 3)
        packet = json.loads(inference.inputs[0])["work_delivery"]
        assert packet["continuation"]["previous_run"]["run_id"] == run.run_id
        assert packet["continuation"]["owner_operation_key"] == "http-continue"
        assert (await client.post(path, json=command)).json() == first.json()
        await runtime.stop_project(101)
        successors = s.c.store.task_runs(101, run.task_id)
        assert len(successors) == 2
        for successor in successors:
            await runtime.wait(successor.run_id)
        assert len(inference.inputs) == 1


def test_continuation_revalidates_prior_effects_before_dispatch_and_preserves_receipts(
    service_setup,
):
    """A fresh owner decision conveys previous real research effects, and a late receipt change prevents starting from unseen evidence."""
    from backend.research.models import RESEARCH_PERMISSIONS, SourceDraft

    s, _, executions, eid, original, run, lease, _ = interrupted_delivery(
        service_setup, close=False
    )
    # Capture a real operation under a separate fixture grant, then link its original
    # author attempt as the runtime would have done before cancellation.
    token = s.c.research.issue_grant(
        project_id=101,
        task_id=run.task_id,
        agent_id=run.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = s.c.research.authorize(token)
    effect = s.c.research.capture_source(
        scope,
        "preserved-source",
        SourceDraft("attachment", "fixture:source", "Prior source", "137 units"),
        intent={},
    )
    s.c.conn.execute(
        "UPDATE tool_grants SET runtime_attempt_id=?,runtime_bound=1 WHERE id=?",
        (lease.attempt_id, scope.grant_id),
    )
    s.c.conn.commit()
    peers = s.c.conn.execute(
        "SELECT id FROM runtime_peers WHERE attempt_id=?", (lease.attempt_id,)
    ).fetchall()
    from backend.runtime.peer_registry import PeerRegistry

    for peer in peers:
        PeerRegistry(s.c.store).close(peer[0])
    s.c.store.retire_withdrawn(lease)
    preview = executions.continuation_state(101, eid, original["delivery_id"])
    assert preview["snapshot"]["attempts"][0]["effects"][0]["receipt"] == effect
    executions.continue_delivery(
        101,
        eid,
        original["delivery_id"],
        operation_key="preserve-effects",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    spec, binding = executions.prepare(eid, run.task_id)
    successor = s.c.store.admit(spec, binding=binding)
    s.c.conn.execute(
        "UPDATE tool_operations SET result_json=? WHERE project_id=101 AND task_id=? AND operation_key='preserved-source'",
        (json.dumps({**effect, "late_observation": True}), run.task_id),
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="continuation|evidence|changed"):
        AttemptPeers.claim(s.c.store, 101, successor.run_id, "new-owner")
    assert s.c.store.get(101, successor.run_id).attempt_id is None


def test_successor_result_acceptance_releases_dependent_with_new_author_identity(
    service_setup,
):
    """A successor uses the ordinary report/owner acceptance path, and its dependent receives the new author's accepted result rather than the failed predecessor."""
    from backend.tests.runtime.test_plan_execution import accept_documentary_result

    s, _, executions, eid, original, run, _, _ = interrupted_delivery(service_setup)
    preview = executions.continuation_state(101, eid, original["delivery_id"])
    executions.continue_delivery(
        101,
        eid,
        original["delivery_id"],
        operation_key="continue-for-result",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    spec, binding = executions.prepare(eid, run.task_id)
    successor = s.c.store.admit(spec, binding=binding)
    accept_documentary_result(s, successor)
    state = executions.state(
        101,
        s.c.conn.execute(
            "SELECT plan_run_id FROM runtime_plan_executions WHERE id=?", (eid,)
        ).fetchone()[0],
    )
    child_id = next(
        t["task_id"] for t in state["manifest"]["tasks"] if t["task_id"] != run.task_id
    )
    child_spec, binding = executions.prepare(eid, child_id)
    child = s.c.store.admit(child_spec, binding=binding)
    with s.c.store._transaction() as conn:
        packet = executions.input(conn, s.c.store._row(conn, 101, child.run_id))
    assert packet["prerequisites"][0]["run_id"] == successor.run_id
    assert s.c.store.get(101, run.run_id).status == "cancelled"


def test_delivery_migration_preserves_original_packets_and_rolls_back_whole_rebuild(
    request, monkeypatch
):
    """A failed migration cannot leave rebuilt half-tables; upgrading an actual schema49 preserves original identities and exact handoff bytes."""
    import sqlite3

    from backend.db import migrations
    from backend.planning.execution import PlanExecutions
    from backend.runtime.contracts import RunSpec
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource

    def skip_fifty(conn, path):
        """Prepare the real pre-upgrade schema without modifying its historical SQL resources."""
        if path.name not in ("plan_continuation_schema.sql", "plan_reauthorization_schema.sql", "investigation_schema.sql", "scientific_schema.sql"):
            apply(conn, path)

    monkeypatch.setattr(migrations, "apply_sql_resource", skip_fifty)
    s = request.getfixturevalue("service_setup")
    s, plan, graph = accepted_plan(s)
    executions = PlanExecutions(s.c.store)
    with s.c.store._transaction() as conn:
        manifest = executions._manifest(conn, 101, plan.run_id)
    from backend.knowledge.reviews import digest

    authorization = executions.authorize(
        101, plan.run_id, operation_key="original49", manifest_sha256=digest(manifest)
    )
    eid = authorization["execution_id"]
    task = graph["tasks"]["learn"]
    native = s.c.store.admit(
        RunSpec(
            101,
            task,
            "native-researcher",
            1,
            "historical-manual",
            "Read the evidence",
            "codex",
        )
    )
    did = s.c.conn.execute(
        "SELECT id FROM runtime_plan_deliveries WHERE task_id=?", (task,)
    ).fetchone()[0]
    packet = '{ "original": "bytes, spacing, and order" }'
    s.c.conn.execute(
        "UPDATE runtime_plan_deliveries SET run_id=? WHERE id=?", (native.run_id, did)
    )
    s.c.conn.execute(
        "INSERT INTO runtime_plan_handoffs VALUES(?,?,?,?)",
        (did, packet, "a" * 64, 1000),
    )
    s.c.conn.execute(
        "CREATE TRIGGER reject50 BEFORE INSERT ON schema_migrations WHEN new.version=50 BEGIN SELECT RAISE(ABORT,'injected migration failure'); END"
    )
    s.c.conn.commit()
    monkeypatch.setattr(migrations, "apply_sql_resource", apply)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        ensure_migrations(s.c.database)
    assert "predecessor_delivery_id" not in {
        r[1] for r in s.c.conn.execute("PRAGMA table_info(runtime_plan_deliveries)")
    }
    assert (
        s.c.conn.execute(
            "SELECT packet_json FROM runtime_plan_handoffs WHERE delivery_id=?", (did,)
        ).fetchone()[0]
        == packet
    )
    s.c.conn.execute("DROP TRIGGER reject50")
    s.c.conn.commit()
    ensure_migrations(s.c.database)
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    old = s.c.conn.execute(
        "SELECT *FROM runtime_plan_deliveries WHERE id=?", (did,)
    ).fetchone()
    assert old["run_id"] == native.run_id and old["execution_id"] == eid
    assert old["predecessor_delivery_id"] is None
    assert (
        s.c.conn.execute(
            "SELECT packet_json FROM runtime_plan_handoffs WHERE delivery_id=?", (did,)
        ).fetchone()[0]
        == packet
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        s.c.conn.execute(
            "UPDATE runtime_plan_handoffs SET packet_json='{}' WHERE delivery_id=?",
            (did,),
        )
