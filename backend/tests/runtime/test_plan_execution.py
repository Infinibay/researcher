"""Accepted-plan execution uses durable causal deliveries; all storage peer witnesses here are synthetic, with no model or process claim."""

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_project_planning import draft, planning_state


def accepted_plan(service_setup, *, research_only=False):
    """Expand a real original proposal after synthetic closure, without authorizing its pending children."""
    from backend.planning.store import ProjectPlans

    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    packet = draft()
    if research_only:
        packet["tasks"][1]["type"] = "research"
    proposal = plans.propose(lease, "plan-for-execution", packet)
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.finish(lease, native_status="completed", summary="Proposed work.")
    receipt = plans.accept(
        101,
        run.run_id,
        operation_key="accept-graph",
        proposal_sha256=proposal["proposal_sha256"],
        context_version=lease.context_version,
    )
    return s, run, receipt


def authorize(s, plan):
    """Use the owner-observed exact manifest to authorize work separately from graph acceptance."""
    from backend.planning.execution import PlanExecutions

    executions = PlanExecutions(s.c.store)
    preview = executions.state(101, plan.run_id)
    command = {
        "operation_key": "execute-graph",
        "manifest_sha256": preview["manifest_sha256"],
    }
    receipt = executions.authorize(101, plan.run_id, **command)
    assert executions.authorize(101, plan.run_id, **command) == receipt
    return executions, receipt


def test_new_delivery_version_supports_bounded_material_descriptors(service_setup):
    """New typed deliveries can describe accepted code artifacts without mutating an older immutable packet."""
    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    executions.prepare(receipt['execution_id'], graph['tasks']['learn'])
    packet = executions.state(101, plan.run_id)['execution']['deliveries'][0]['handoff']
    assert packet['schema_version'] == 3


def test_prepared_version_two_delivery_retains_its_original_bytes_and_hash(service_setup, monkeypatch):
    """A queued original delivery created under the previous schema cannot be silently rewritten or rejected merely by upgrading artifact readers."""
    import backend.planning.execution as module

    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    monkeypatch.setattr(module, 'HANDOFF_SCHEMA_VERSION', 2)
    original = executions.prepare(receipt['execution_id'], graph['tasks']['learn'])
    before = [tuple(row) for row in s.c.conn.execute('SELECT packet_json,packet_sha256 FROM runtime_plan_handoffs')]
    monkeypatch.setattr(module, 'HANDOFF_SCHEMA_VERSION', 3)
    assert executions.prepare(receipt['execution_id'], graph['tasks']['learn']) == original
    assert [tuple(row) for row in s.c.conn.execute('SELECT packet_json,packet_sha256 FROM runtime_plan_handoffs')] == before
    run = s.c.store.admit(original[0], binding=original[1])
    with s.c.store._transaction() as conn:
        assert executions.input(conn, s.c.store._row(conn, 101, run.run_id))['schema_version'] == 2


def accept_documentary_result(s, run, *, accept_now=True):
    """Write and explicitly accept a real report/evidence under the admitted author lease; peer closure witnesses are synthetic."""
    from backend.research.models import (
        RESEARCH_PERMISSIONS,
        EvidenceReference,
        FindingDraft,
        ReportDraft,
        ResultDraft,
        SourceDraft,
    )
    from backend.runtime.peer_registry import AttemptPeers
    from backend.tests.runtime.test_result_acceptance import accept

    lease, peers = AttemptPeers.claim(
        s.c.store, 101, run.run_id, "synthetic-work-owner"
    )
    s.c.store.bind_native(lease, thread_id="root-work-thread", turn_id="root-work-turn")
    token = s.c.research.issue_grant(
        project_id=101,
        task_id=run.task_id,
        agent_id=run.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = s.c.research.authorize(token)
    s.c.store.bind_grant(lease, scope.grant_id)
    sid = s.c.research.capture_source(
        scope,
        "source137",
        SourceDraft(
            "attachment", "synthetic:137", "Sample", "The sample contains 137 units."
        ),
        intent={},
    )["source_id"]
    fid = s.c.research.record_finding(
        scope,
        "finding137",
        FindingDraft(
            "Count",
            "The sample contains 137 units.",
            (EvidenceReference(sid, "137 units"),),
        ),
    )["finding_id"]
    report = s.c.research.write_report(
        scope,
        "report137",
        ReportDraft("Count report", "The sample contains 137 units.", (fid,)),
    )["artifact_id"]
    s.c.research.propose_result(
        scope,
        "deliver137",
        ResultDraft((report,), "Documentary count.", ("Measurement not repeated.",)),
    )
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.finish(
        lease, native_status="completed", summary="A report, awaiting the owner."
    )
    state = s.c.store.result_state(101, run.run_id)
    if not accept_now:
        return lease, state
    return accept(s.c, lease, state)


def test_execution_requires_distinct_owner_authorization_and_original_delivery(
    service_setup,
):
    """Graph acceptance and arbitrary text cannot activate work; one explicit execution decision yields one original root run."""
    from backend.planning.execution import PlanExecutions

    s, plan, graph = accepted_plan(service_setup)
    executions = PlanExecutions(s.c.store)
    assert executions.pending() == []
    assert s.c.store.task_runs(101, graph["tasks"]["learn"]) == ()
    executions, receipt = authorize(s, plan)
    assert len(executions.pending()) == 2
    root = executions.prepare(receipt["execution_id"], graph["tasks"]["learn"])
    assert executions.prepare(receipt["execution_id"], graph["tasks"]["change"]) is None
    spec, binding = root
    run, admitted = s.c.store.admit_once(spec, binding=binding)
    assert admitted
    again, admitted = s.c.store.admit_once(spec, binding=binding)
    assert again.run_id == run.run_id and not admitted
    view = executions.state(101, plan.run_id)
    delivery = next(
        d for d in view["execution"]["deliveries"] if d["task_id"] == run.task_id
    )
    assert delivery["run_id"] == run.run_id
    assert delivery["handoff"]["kind"] == "work.request"
    assert delivery["handoff"]["cause"]["plan_run_id"] == plan.run_id
    assert delivery["handoff"]["prerequisites"] == []
    with pytest.raises(RunConflict):
        executions.authorize(
            101, plan.run_id, operation_key="execute-graph", manifest_sha256="0" * 64
        )


def test_dependent_handoff_contains_original_accepted_evidence_and_blocks_changed_context(
    service_setup,
):
    """The consumer receives accepted source/result identities and limits, while changed premises withdraw even an already admitted consumer."""
    from backend.runtime.peer_registry import AttemptPeers

    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    root_spec, binding = executions.prepare(
        receipt["execution_id"], graph["tasks"]["learn"]
    )
    root = s.c.store.admit(root_spec, binding=binding)
    accepted = accept_documentary_result(s, root)
    child_spec, child_binding = executions.prepare(
        receipt["execution_id"], graph["tasks"]["change"]
    )
    child = s.c.store.admit(child_spec, binding=child_binding)
    with s.c.store._transaction() as conn:
        handoff = executions.input(conn, s.c.store._row(conn, 101, child.run_id))
    source = handoff["prerequisites"][0]
    assert (
        handoff["plan_context"]["original_material"]["owner_request"]
        == "Investigate the issue and propose a plan."
    )
    assert (
        handoff["plan_context"]["original_material"]["instruction_origin"]
        == "owner_message"
    )
    assert handoff["plan_context"]["accepted_plan"]["assumptions"] == [
        "The existing repository remains the target."
    ]
    assert source["run_id"] == root.run_id
    assert source["acceptance"]["subject_sha256"] == accepted["candidate_sha256"]
    assert source["snapshot"]["reports"][0]["content"].endswith("137 units.")
    assert source["snapshot"]["limitations"] == ["Measurement not repeated."]
    assert source["snapshot"]["scientific_confidence"] is None
    lease, _peers = AttemptPeers.claim(
        s.c.store, 101, child.run_id, "synthetic-consumer"
    )
    s.c.conn.execute(
        "UPDATE tasks SET description='The sample actually contains 138 units.' WHERE id=?",
        (root.task_id,),
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="manifest|context|premise|prerequisite"):
        s.c.store.heartbeat(lease)
    assert executions.state(101, plan.run_id)["execution"]["current"] is False


def test_execution_pause_and_resume_never_replay_an_attempted_delivery(service_setup):
    """A durable pause blocks admission; resuming can schedule only never-issued work and cannot manufacture a second author turn."""
    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    eid = receipt["execution_id"]
    manifest = receipt["manifest_sha256"]
    pause = {
        "operation_key": "pause-work",
        "manifest_sha256": manifest,
        "status": "paused",
    }
    original = executions.control(101, eid, **pause)
    assert executions.control(101, eid, **pause) == original
    assert executions.prepare(eid, graph["tasks"]["learn"]) is None
    executions.control(
        101, eid, operation_key="resume-work", manifest_sha256=manifest, status="active"
    )
    spec, binding = executions.prepare(eid, graph["tasks"]["learn"])
    run = s.c.store.admit(spec, binding=binding)
    lease = s.c.store.claim(101, run.run_id, "synthetic-owner")
    s.c.store.cancel(101, run.run_id)
    assert executions.prepare(eid, graph["tasks"]["learn"]) is None
    assert len(s.c.store.task_runs(101, run.task_id)) == 1
    assert lease.attempt_id


def test_changed_dependency_graph_cannot_reuse_owner_execution_manifest(service_setup):
    """Adding a prerequisite after authorization cannot make the old graph decision authorize new work."""
    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    s.c.conn.execute(
        "DELETE FROM task_dependencies WHERE task_id=?", (graph["tasks"]["change"],)
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="manifest|context|premise"):
        executions.prepare(receipt["execution_id"], graph["tasks"]["learn"])


class DeliveryInference:
    """Control generation only; the real coordinator/journal/grants produce and close each synthetic session."""

    supported_task_types = ("plan", "research", "code", "bug_fix")

    def __init__(self, setup):
        """Retain fixture scope and observable original inputs without requesting a provider turn."""
        import asyncio

        self.setup = setup
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.inputs = []
        self.model = "controlled-delivery-no-model"
        self.catalog = []
        self.developer_instructions = "Controlled delivery fixture."
        self.catalog_hash = __import__("hashlib").sha256(b"[]").hexdigest()

    def open(self, **kwargs):
        """Create one scoped session; closure here is a synthetic runtime observation, not an OS proof."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def session():
            """Expose only the configured fixture peer while real service authority remains in charge."""
            self.scope = self.setup.c.research.authorize(kwargs["tool_token"])
            self.thread_id = "delivery-thread-" + str(self.scope.task_id)
            self.peers_closed = False
            try:
                yield self
            finally:
                self.peers_closed = True

        return session()

    async def run(self, prompt, *, on_started, on_event):
        """Hold one original frozen input until the test releases or cancels its generation."""
        from backend.runtime.codex_session import NativeTurnResult

        self.inputs.append(prompt)
        await on_started(self.thread_id, "original-work-turn")
        self.started.set()
        await self.release.wait()
        return NativeTurnResult(
            self.thread_id,
            "original-work-turn",
            "completed",
            "Thank you; everything is done.",
            0,
            None,
            None,
        )

    async def cancel(self):
        """Unblock the controlled original generation without claiming any result was accepted."""
        self.release.set()


async def test_service_recovers_never_started_delivery_and_stop_prevents_refill(
    service_setup,
):
    """An authorized queued run survives owner restart once; Stop pauses its graph before cancellation and text completion never starts the child."""
    import asyncio
    import json

    from backend.tests.runtime.test_runtime_service import coordinator

    s, plan, graph = accepted_plan(service_setup)
    executions, receipt = authorize(s, plan)
    spec, binding = executions.prepare(receipt["execution_id"], graph["tasks"]["learn"])
    original = s.c.store.admit(spec, binding=binding)
    inference = DeliveryInference(s)
    async with coordinator(s, inference) as service:
        await asyncio.wait_for(inference.started.wait(), 3)
        frozen = json.loads(inference.inputs[0])
        assert frozen["work_delivery"]["target"]["task_id"] == original.task_id
        assert frozen["work_delivery"]["cause"]["plan_run_id"] == plan.run_id
        await service.stop_project(101)
        await service.wait(original.run_id)
        await service.dispatch_planned_work()
        assert len(inference.inputs) == 1
        assert executions.state(101, plan.run_id)["execution"]["status"] == "paused"
        assert not s.c.store.task_runs(101, graph["tasks"]["change"])
    async with coordinator(s, DeliveryInference(s)) as restarted:
        await restarted.dispatch_planned_work()
        assert s.c.store.get(101, original.run_id).status == "cancelled"
        assert not s.c.store.task_runs(101, graph["tasks"]["change"])


def test_changed_prerequisite_blocks_acceptance_of_already_delivered_consumer(
    service_setup,
):
    """Closing the consumer does not make a result based on obsolete predecessor evidence eligible for a new owner acceptance."""
    from backend.research.models import OperationConflict
    from backend.tests.runtime.test_result_acceptance import accept

    s, plan, graph = accepted_plan(service_setup, research_only=True)
    executions, receipt = authorize(s, plan)
    spec, binding = executions.prepare(receipt["execution_id"], graph["tasks"]["learn"])
    root = s.c.store.admit(spec, binding=binding)
    accept_documentary_result(s, root)
    spec, binding = executions.prepare(
        receipt["execution_id"], graph["tasks"]["change"]
    )
    child = s.c.store.admit(spec, binding=binding)
    lease, state = accept_documentary_result(s, child, accept_now=False)
    s.c.conn.execute(
        "UPDATE tasks SET description='Corrected premise: 138 units' WHERE id=?",
        (root.task_id,),
    )
    s.c.conn.commit()
    with pytest.raises((RunConflict, OperationConflict)):
        accept(s.c, lease, state)
    assert s.c.store.result_state(101, child.run_id)["acceptance"] is None


async def test_execution_http_requires_exact_owner_manifest_and_separate_pause_control(
    service_setup,
):
    """Strict paired-owner decisions authorize work, survive duplicate requests, and pause the durable graph before stopping its original peers."""
    import asyncio

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, plan, graph = accepted_plan(service_setup)
    inference = DeliveryInference(s)
    runtime = coordinator(s, inference)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    path = f"/api/projects/101/runs/{plan.run_id}/project-plan/execution"
    async with app.router.lifespan_context(app), owner_client(app) as client:
        preview = await client.get(path)
        assert preview.status_code == 200, preview.text
        command = {
            "operation_key": "owner-execute",
            "manifest_sha256": preview.json()["manifest_sha256"],
        }
        assert (
            await client.post(path, json={**command, "actor_id": "invented"})
        ).status_code == 422
        assert (
            await client.post(
                path, json=command, headers={"X-Researcher-CSRF": "invalid"}
            )
        ).status_code == 403
        assert (
            await client.post(path, json={**command, "manifest_sha256": "0" * 64})
        ).status_code == 409
        first = await client.post(path, json=command)
        assert first.status_code == 200, first.text
        assert (await client.post(path, json=command)).json() == first.json()
        await asyncio.wait_for(inference.started.wait(), 3)
        view = (await client.get(path)).json()["execution"]
        pause = {
            "operation_key": "pause-http",
            "manifest_sha256": command["manifest_sha256"],
            "status": "paused",
        }
        control = f"/api/projects/101/plan-executions/{view['execution_id']}/control"
        assert (await client.post(control, json=pause)).status_code == 200
        assert (
            await client.post(control.replace("/101/", "/202/"), json=pause)
        ).status_code == 404
        await runtime.wait(next(d["run_id"] for d in view["deliveries"] if d["run_id"]))
        assert (await client.get(path)).json()["execution"]["status"] == "paused"
        assert not s.c.store.task_runs(101, graph["tasks"]["change"])
