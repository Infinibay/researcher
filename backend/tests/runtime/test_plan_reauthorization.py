"""Owner adoption of corrected graph premises preserves prior execution evidence; storage peer witnesses here are synthetic."""

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_plan_continuation import interrupted_delivery
from backend.tests.runtime.test_plan_execution import (
    accept_documentary_result,
    accepted_plan,
    authorize,
)


def corrected_graph(service_setup, *, project=False):
    """Correct actual persisted premises after a closed interrupted root, without inventing a new plan acceptance."""
    s, plan, executions, eid, original, run, _lease, _peers = interrupted_delivery(
        service_setup
    )
    if project:
        s.c.conn.execute(
            "UPDATE projects SET description='Corrected project objective: inspect 138 units.' WHERE id=101"
        )
    else:
        s.c.conn.execute(
            "UPDATE tasks SET description='Inspect the corrected 138-unit sample.' WHERE id=?",
            (run.task_id,),
        )
    s.c.conn.commit()
    return s, plan, executions, eid, original, run


@pytest.mark.parametrize("project", [False, True])
def test_owner_reauthorizes_corrected_graph_once_without_rewriting_original(
    service_setup, project
):
    """Revised task/project premises require a new exact decision and resume; new input distinguishes the owner's corrected graph from the original model plan."""
    s, plan, executions, eid, _original, run = corrected_graph(
        service_setup, project=project
    )
    before = s.c.conn.execute(
        "SELECT manifest_json,manifest_sha256,operation_key FROM runtime_plan_executions WHERE id=?",
        (eid,),
    ).fetchone()
    preview = executions.reauthorization_state(101, eid)
    assert preview["eligible"], preview
    assert preview["snapshot"]["changes"]
    command = {
        "operation_key": "owner-adopt-corrected-graph",
        "snapshot_sha256": preview["snapshot_sha256"],
    }
    receipt = executions.reauthorize(101, eid, **command)
    assert executions.reauthorize(101, eid, **command) == receipt
    assert tuple(
        s.c.conn.execute(
            "SELECT manifest_json,manifest_sha256,operation_key FROM runtime_plan_executions WHERE id=?",
            (eid,),
        ).fetchone()
    ) == tuple(before)
    state = executions.state(101, plan.run_id)["execution"]
    assert state["current"] and state["status"] == "paused"
    assert state["authorization_revision"] == 1
    assert executions.prepare(eid, run.task_id) is None
    executions.control(
        101,
        eid,
        operation_key="resume-corrected-graph",
        manifest_sha256=receipt["manifest_sha256"],
        status="active",
        authorization_revision=receipt["authorization_revision"],
    )
    spec, binding = executions.prepare(eid, run.task_id)
    revised = s.c.store.admit(spec, binding=binding)
    with s.c.store._transaction() as conn:
        packet = executions.input(conn, s.c.store._row(conn, 101, revised.run_id))
    assert packet["reauthorization"]["owner_operation_key"] == command["operation_key"]
    assert packet["reauthorization"]["snapshot"]["corrected_tasks"]
    assert (
        packet["plan_context"]["original_material"]["owner_request"]
        == "Investigate the issue and propose a plan."
    )
    assert s.c.store.get(101, run.run_id).status == "cancelled"
    accept_documentary_result(s, revised)
    child_id = next(
        t["task_id"]
        for t in executions.state(101, plan.run_id)["manifest"]["tasks"]
        if t["task_id"] != run.task_id
    )
    assert executions.prepare(eid, child_id) is not None
    assert len(s.c.store.task_runs(101, run.task_id)) == 2


def test_reauthorization_blocks_live_work_and_rejects_changed_snapshot_or_cycle(
    service_setup,
):
    """A correction or terminal label cannot replace physical closure, and another unseen edit/cycle cannot inherit old owner permission."""
    s, plan, executions, eid, _original, run, lease, peers = interrupted_delivery(
        service_setup, close=False
    )
    s.c.conn.execute(
        "UPDATE tasks SET description='Corrected requirements' WHERE id=?",
        (run.task_id,),
    )
    s.c.conn.commit()
    assert not executions.reauthorization_state(101, eid)["eligible"]
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.retire_withdrawn(lease)
    preview = executions.reauthorization_state(101, eid)
    assert preview["eligible"], preview
    s.c.conn.execute(
        "UPDATE tasks SET acceptance_criteria='Another unseen criterion' WHERE id=?",
        (run.task_id,),
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="snapshot|changed|obsolete"):
        executions.reauthorize(
            101,
            eid,
            operation_key="stale-graph",
            snapshot_sha256=preview["snapshot_sha256"],
        )
    child_id = next(
        t["task_id"]
        for t in executions.state(101, plan.run_id)["manifest"]["tasks"]
        if t["task_id"] != run.task_id
    )
    s.c.conn.execute(
        "INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type)VALUES(?,?,'blocks')",
        (run.task_id, child_id),
    )
    s.c.conn.commit()
    preview = executions.reauthorization_state(101, eid)
    assert not preview["eligible"] and "cycle" in preview["blocked_reason"].lower()


def test_reauthorization_preserves_still_current_accepted_result_without_repeating_it(
    service_setup,
):
    """Replacing an unused delivery explicitly retains an exact accepted prerequisite; its existing owner acceptance is neither fabricated nor rerun."""
    s, plan, _ = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    eid = receipt["execution_id"]
    state = executions.state(101, plan.run_id)
    root_id = next(
        t["task_id"] for t in state["manifest"]["tasks"] if not t["depends_on"]
    )
    spec, binding = executions.prepare(eid, root_id)
    root = s.c.store.admit(spec, binding=binding)
    accept_documentary_result(s, root)
    executions.control(
        101,
        eid,
        operation_key="pause-for-revision",
        manifest_sha256=receipt["manifest_sha256"],
        status="paused",
    )
    preview = executions.reauthorization_state(101, eid)
    assert preview["snapshot"]["retained_results"][0]["run_id"] == root.run_id
    revised = executions.reauthorize(
        101,
        eid,
        operation_key="retain-root",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    executions.control(
        101,
        eid,
        operation_key="resume-retained",
        manifest_sha256=revised["manifest_sha256"],
        status="active",
        authorization_revision=revised["authorization_revision"],
    )
    assert executions.prepare(eid, root_id) is None
    assert len(s.c.store.task_runs(101, root_id)) == 1
    with s.c.store._transaction() as conn:
        assert executions.input(conn, s.c.store._row(conn, 101, root.run_id))[
            "delivery_id"
        ]


def test_graph_revision_controls_require_the_observed_authorization_not_just_same_manifest(
    service_setup,
):
    """An old resume selection cannot activate a newer owner decision whose unchanged task graph happens to have the same manifest hash."""
    _s, plan, executions, eid, _original, _run = corrected_graph(service_setup)
    first = executions.reauthorization_state(101, eid)
    one = executions.reauthorize(
        101, eid, operation_key="revision-one", snapshot_sha256=first["snapshot_sha256"]
    )
    second = executions.reauthorization_state(101, eid)
    two = executions.reauthorize(
        101,
        eid,
        operation_key="revision-two",
        snapshot_sha256=second["snapshot_sha256"],
    )
    assert one["manifest_sha256"] == two["manifest_sha256"]
    with pytest.raises(RunConflict, match="revision|authorization"):
        executions.control(
            101,
            eid,
            operation_key="stale-resume",
            manifest_sha256=one["manifest_sha256"],
            status="active",
            authorization_revision=1,
        )
    assert executions.state(101, plan.run_id)["execution"]["status"] == "paused"
    result = executions.control(
        101,
        eid,
        operation_key="current-resume",
        manifest_sha256=two["manifest_sha256"],
        status="active",
        authorization_revision=2,
    )
    assert result["authorization_revision"] == 2


def test_reauthorization_replaces_unissued_successor_with_late_changed_evidence(
    service_setup,
):
    """Fresh graph permission replaces an obsolete unused delivery without pretending that it ran or deleting its original authorization."""
    s, plan, executions, eid, original, run, _lease, _peers = interrupted_delivery(
        service_setup
    )
    preview = executions.continuation_state(101, eid, original["delivery_id"])
    unused = executions.continue_delivery(
        101,
        eid,
        original["delivery_id"],
        operation_key="unused-successor",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    s.c.conn.execute(
        "UPDATE runtime_runs SET issue_json='{}' WHERE id=?", (run.run_id,)
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="evidence|changed"):
        executions.prepare(eid, run.task_id)
    state = executions.state(101, plan.run_id)
    executions.control(
        101,
        eid,
        operation_key="pause-obsolete",
        manifest_sha256=state["execution"]["manifest_sha256"],
        status="paused",
    )
    current = executions.reauthorization_state(101, eid)
    revision = executions.reauthorize(
        101,
        eid,
        operation_key="adopt-late-observation",
        snapshot_sha256=current["snapshot_sha256"],
    )
    executions.control(
        101,
        eid,
        operation_key="resume-late-observation",
        manifest_sha256=revision["manifest_sha256"],
        status="active",
        authorization_revision=revision["authorization_revision"],
    )
    spec, binding = executions.prepare(eid, run.task_id)
    new_run = s.c.store.admit(spec, binding=binding)
    history = executions.state(101, plan.run_id)["execution"]["deliveries"]
    retired = next(d for d in history if d["delivery_id"] == unused["delivery_id"])
    assert retired["run_id"] is None and not retired["current"]
    assert (
        next(d for d in history if d["run_id"] == new_run.run_id)[
            "predecessor_delivery_id"
        ]
        == unused["delivery_id"]
    )
    assert s.c.store.get(101, run.run_id).status == "cancelled"


def test_later_correction_fences_effective_revision_and_new_author_lease(service_setup):
    """Invalidation follows current revision versions; another edit cannot leave its native author authorized under obsolete premises."""
    from backend.runtime.peer_registry import AttemptPeers

    s, plan, executions, eid, _original, run = corrected_graph(service_setup)
    preview = executions.reauthorization_state(101, eid)
    receipt = executions.reauthorize(
        101,
        eid,
        operation_key="adopt-first-edit",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    executions.control(
        101,
        eid,
        operation_key="resume-first-edit",
        manifest_sha256=receipt["manifest_sha256"],
        status="active",
        authorization_revision=receipt["authorization_revision"],
    )
    spec, binding = executions.prepare(eid, run.task_id)
    new = s.c.store.admit(spec, binding=binding)
    lease, _peers = AttemptPeers.claim(s.c.store, 101, new.run_id, "revised-author")
    s.c.conn.execute(
        "UPDATE tasks SET description='A second corrected requirement' WHERE id=?",
        (run.task_id,),
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict):
        s.c.store.heartbeat(lease)
    state = executions.state(101, plan.run_id)["execution"]
    assert not state["current"] and state["status"] == "paused"
    assert s.c.store.get(101, new.run_id).status == "reconciling"


async def test_http_reauthorization_recovers_revision_and_only_resumes_explicitly(
    service_setup,
):
    """Paired decisions bind exact corrected evidence across restart and emit one author input only after revision-bound resume."""
    import asyncio
    import json

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_plan_execution import DeliveryInference
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, _plan, _executions, eid, _original, _run = corrected_graph(
        service_setup, project=True
    )
    path = f"/api/projects/101/plan-executions/{eid}/reauthorization"
    native = DeliveryInference(s)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=coordinator(s, native),
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        observed = await client.get(path)
        assert observed.status_code == 200 and observed.json()["eligible"], (
            observed.text
        )
        command = {
            "operation_key": "http-corrected-graph",
            "snapshot_sha256": observed.json()["snapshot_sha256"],
        }
        assert (
            await client.post(
                path, json=command, headers={"X-Researcher-CSRF": "invalid"}
            )
        ).status_code == 403
        assert (
            await client.post(path, json={**command, "tasks": []})
        ).status_code == 422
        assert (
            await client.post(path.replace("/101/", "/202/"), json=command)
        ).status_code == 404
        first = await client.post(path, json=command)
        assert first.status_code == 200, first.text
        assert native.inputs == []
    native = DeliveryInference(s)
    runtime = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        assert (await client.post(path, json=command)).json() == first.json()
        assert native.inputs == []
        control = {
            "operation_key": "resume-http-corrected",
            "manifest_sha256": first.json()["manifest_sha256"],
            "authorization_revision": first.json()["authorization_revision"],
            "status": "active",
        }
        response = await client.post(
            path.replace("/reauthorization", "/control"), json=control
        )
        assert response.status_code == 200, response.text
        await asyncio.wait_for(native.started.wait(), 3)
        packet = json.loads(native.inputs[0])["work_delivery"]
        assert (
            packet["reauthorization"]["snapshot"]["manifest"]["project"]["description"]
            == "Corrected project objective: inspect 138 units."
        )
        await runtime.stop_project(101)
        for run in runtime.store.task_runs(101, packet["target"]["task_id"]):
            await runtime.wait(run.run_id)
        assert len(native.inputs) == 1


def test_revision_migration_rolls_back_failed_upgrade_and_preserves_original_execution(
    request, monkeypatch
):
    """A failed schema51 install cannot change existing manifests or replace the old invalidation view; successful retry retains exact original intent and foreign keys."""
    import sqlite3

    from backend.db import migrations
    from backend.knowledge.reviews import digest
    from backend.planning.execution import PlanExecutions
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource

    def skip_revision(conn, path):
        """Prepare the actual schema50 while leaving its historical SQL resources unchanged."""
        if path.name not in ("plan_reauthorization_schema.sql", "investigation_schema.sql", "scientific_schema.sql"):
            apply(conn, path)

    monkeypatch.setattr(migrations, "apply_sql_resource", skip_revision)
    s = request.getfixturevalue("service_setup")
    s, plan, _graph = accepted_plan(s)
    executions = PlanExecutions(s.c.store)
    with s.c.store._transaction() as conn:
        manifest = executions._manifest(conn, 101, plan.run_id)
    original = executions.authorize(
        101,
        plan.run_id,
        operation_key="schema50-owner",
        manifest_sha256=digest(manifest),
    )
    before = s.c.conn.execute(
        "SELECT manifest_json FROM runtime_plan_executions WHERE id=?",
        (original["execution_id"],),
    ).fetchone()[0]
    s.c.conn.execute(
        "CREATE TRIGGER reject51 BEFORE INSERT ON schema_migrations WHEN new.version=51 BEGIN SELECT RAISE(ABORT,'injected revision migration failure'); END"
    )
    s.c.conn.commit()
    monkeypatch.setattr(migrations, "apply_sql_resource", apply)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        ensure_migrations(s.c.database)
    assert (
        s.c.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='runtime_plan_execution_revisions'"
        ).fetchone()
        is None
    )
    assert (
        s.c.conn.execute("SELECT count(*)FROM runtime_plan_context_members").fetchone()[
            0
        ]
        == 2
    )
    s.c.conn.execute("DROP TRIGGER reject51")
    s.c.conn.commit()
    ensure_migrations(s.c.database)
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    current = s.c.conn.execute(
        "SELECT *FROM runtime_plan_effective_executions WHERE id=?",
        (original["execution_id"],),
    ).fetchone()
    assert current["manifest_json"] == before and current["authorization_revision"] == 0
    assert (
        s.c.conn.execute("SELECT count(*)FROM runtime_plan_context_members").fetchone()[
            0
        ]
        == 2
    )


def test_late_history_change_cannot_admit_child_using_stale_revised_parent_authority(
    service_setup,
):
    """A separate owner child request cannot borrow revised parent authority after its observed original effects change."""
    from backend.runtime.contracts import RunSpec

    s, _plan, executions, eid, _original, run = corrected_graph(
        service_setup, project=True
    )
    preview = executions.reauthorization_state(101, eid)
    receipt = executions.reauthorize(
        101,
        eid,
        operation_key="correct-parent",
        snapshot_sha256=preview["snapshot_sha256"],
    )
    executions.control(
        101,
        eid,
        operation_key="resume-parent",
        manifest_sha256=receipt["manifest_sha256"],
        authorization_revision=receipt["authorization_revision"],
        status="active",
    )
    s.c.conn.execute(
        "UPDATE runtime_runs SET issue_json='{}' WHERE id=?", (run.run_id,)
    )
    s.c.conn.commit()
    version = s.c.store.context_snapshot(101, run.task_id)["context_version"]
    with pytest.raises(RunConflict):
        s.c.store.admit(
            RunSpec(
                101,
                run.task_id,
                "manual-owner-author",
                version,
                "manual-after-late-effect",
                "Inspect the current task.",
                "codex",
            )
        )
