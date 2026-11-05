"""Native structured plan proposals and explicit owner expansion; process witnesses in storage tests are explicitly synthetic."""

import pytest


def draft():
    """Produce a small justified DAG with an explicit unknown premise, never runnable instructions disguised as chat."""
    return {
        "title": "Research then implement",
        "rationale": "Establish the behavior before changing it.",
        "assumptions": ["The existing repository remains the target."],
        "basis": [{"source": "owner_request", "quote": "Investigate the issue"}],
        "epics": [
            {
                "key": "work",
                "title": "Verified behavior",
                "description": "Understand and improve the behavior.",
            }
        ],
        "tasks": [
            {
                "key": "learn",
                "epic_key": "work",
                "type": "research",
                "title": "Investigate behavior",
                "description": "Read current behavior and cite evidence.",
                "acceptance_criteria": "A cited explanation with limits.",
                "priority": 2,
                "depends_on": [],
            },
            {
                "key": "change",
                "epic_key": "work",
                "type": "code",
                "title": "Implement improvement",
                "description": "Apply the supported change.",
                "acceptance_criteria": "The demonstrated case passes.",
                "priority": 2,
                "depends_on": ["learn"],
            },
        ],
    }


def test_plan_policy_refuses_cycles_missing_keys_and_fabricated_shared_context():
    """Graph and literal basis checks prevent a plausible plan from turning assumptions into demonstrated user evidence."""
    from copy import deepcopy

    from backend.planning.models import validate_plan

    source = {
        "owner_request": "Investigate the issue and propose a plan.",
        "project_description": "A local research workspace.",
    }
    assert validate_plan(draft(), source)["tasks"][1]["depends_on"] == ["learn"]
    for edit in ("cycle", "missing", "quote", "extra"):
        packet = deepcopy(draft())
        if edit == "cycle":
            packet["tasks"][0]["depends_on"] = ["change"]
        elif edit == "missing":
            packet["tasks"][1]["depends_on"] = ["unknown"]
        elif edit == "quote":
            packet["basis"][0]["quote"] = (
                "The user knows this because of their profession"
            )
        else:
            packet["tasks"][0]["actor_id"] = "invented-authority"
        with pytest.raises(ValueError):
            validate_plan(packet, source)


def planning_state(service_setup):
    """Admit an existing plan task through real store/binding without generation or physical-process claims."""
    from dataclasses import replace

    from backend.runtime.peer_registry import AttemptPeers

    s = service_setup
    s.c.conn.execute(
        "UPDATE tasks SET type='plan',description='Investigate the issue and propose a plan.' WHERE id=1001"
    )
    s.c.conn.commit()
    spec = replace(
        s.c.spec,
        context_version=s.c.store.context_snapshot(101, 1001)["context_version"],
        prompt="Investigate the issue and propose a plan.",
    )
    from backend.runtime.workspaces import WorkspaceRegistry

    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, None)
    run = s.c.store.admit(spec, binding=binding)
    lease, peers = AttemptPeers.claim(
        s.c.store, 101, run.run_id, "synthetic-planner-owner"
    )
    return s, run, lease, peers


def test_owner_acceptance_creates_original_tasks_and_dependencies_once_after_closed_proposal(
    service_setup,
):
    """Proposing work creates no task; owner acceptance over a closed exact proposal commits a graph and same-command receipt atomically."""
    from backend.planning.store import ProjectPlans
    from backend.runtime.contracts import RunConflict

    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    before = s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0]
    proposal = plans.propose(lease, "proposal-a", draft())
    assert s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0] == before
    decision = {
        "operation_key": "owner-plan-a",
        "proposal_sha256": proposal["proposal_sha256"],
        "context_version": lease.context_version,
    }
    with pytest.raises(RunConflict):
        plans.accept(101, run.run_id, **decision)
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.finish(
        lease,
        native_status="completed",
        summary="Proposed plan, awaiting owner decision.",
    )
    result = plans.accept(101, run.run_id, **decision)
    assert plans.accept(101, run.run_id, **decision) == result
    assert len(result["tasks"]) == 2
    assert s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0] == before + 2
    a, b = result["tasks"]["learn"], result["tasks"]["change"]
    assert (
        s.c.conn.execute(
            "SELECT depends_on_task_id FROM task_dependencies WHERE task_id=?", (b,)
        ).fetchone()[0]
        == a
    )
    assert s.c.store.get(101, run.run_id).status == "accepted"
    assert (
        s.c.conn.execute("SELECT status FROM tasks WHERE id=?", (a,)).fetchone()[0]
        == "pending"
    )
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_project_change_versions_the_planner_and_preserves_historical_proposal(
    service_setup,
):
    """A changed project premise invalidates tool/acceptance authority instead of silently treating a previous plan as current."""
    from backend.planning.store import ProjectPlans
    from backend.runtime.contracts import RunConflict

    s, run, lease, _ = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    proposal = plans.propose(lease, "proposal-b", draft())
    s.c.conn.execute("UPDATE projects SET description='Different goal' WHERE id=101")
    s.c.conn.commit()
    assert (
        s.c.store.context_snapshot(101, 1001)["context_version"] > lease.context_version
    )
    with pytest.raises(RunConflict):
        plans.propose(lease, "new-proposal", draft())
    with pytest.raises(RunConflict):
        plans.accept(
            101,
            run.run_id,
            operation_key="stale-owner",
            proposal_sha256=proposal["proposal_sha256"],
            context_version=lease.context_version,
        )
    assert (
        plans.state(101, run.run_id)["proposal"]["proposal_sha256"]
        == proposal["proposal_sha256"]
    )


async def test_project_start_uses_one_native_request_and_never_launches_legacy_threads(
    service_setup, monkeypatch
):
    """Owner start retries preserve one planning task/run and its binding; old CrewAI startup cannot be used as fallback."""
    from types import SimpleNamespace

    from backend.api.flow_manager import flow_manager
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s = service_setup
    native = SimpleNamespace(
        supported_task_types=("research", "code", "bug_fix", "plan")
    )
    runtime = coordinator(s, native)

    async def held(run):
        """Retain real admission queued without claiming physical/model execution in this API test."""
        return run

    runtime._schedule = held

    def forbidden(*args):
        """Fail the test if the migrated public entry starts old flow threads."""
        raise AssertionError("Legacy flow startup must not be called")

    monkeypatch.setattr(flow_manager, "start_project_flow", forbidden)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        body = {
            "operation_key": "project-start-a",
            "prompt": "Investigate the issue and propose a plan.",
            "repository_id": 11,
        }
        response = await client.post("/api/projects/101/start", json=body)
        assert response.status_code == 200, response.text
        packet = response.json()
        assert packet["run"]["execution_kind"] == "research"
        repeated = await client.post("/api/projects/101/start", json=body)
        assert repeated.json()["run"]["run_id"] == packet["run"]["run_id"]
        assert packet["planning_task_id"] == packet["run"]["task_id"]
        assert (
            s.c.conn.execute(
                "SELECT count(*)FROM runtime_project_plan_starts"
            ).fetchone()[0]
            == 1
        )
        assert (
            await client.post(
                "/api/projects/101/start", json={**body, "actor_id": "forged"}
            )
        ).status_code == 422
        assert (
            await client.post(
                "/api/projects/101/start",
                json=body,
                headers={"X-Researcher-CSRF": "bad"},
            )
        ).status_code == 403


async def test_host_planner_tools_bind_scope_and_cannot_create_work_or_auto_accept(
    service_setup,
):
    """Native tool envelope rejects actor/acceptance fields, retains a typed original proposal, and seals further calls before closure."""
    from backend.planning.store import ProjectPlans
    from backend.planning.tools import PlanningTools
    from backend.runtime.owned_runtime import _settled

    s, _run, lease, _ = planning_state(service_setup)
    tools = PlanningTools(
        ProjectPlans(s.c.store), lease, active=lambda: True, settled=_settled
    )
    bad = await tools.call(
        {
            "tool": "researcher_plan_propose",
            "arguments": {
                "operation_key": "tool-plan",
                "plan": draft(),
                "actor_id": "forged",
            },
        }
    )
    assert not bad["success"]
    before = s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0]
    result = await tools.call(
        {
            "tool": "researcher_plan_propose",
            "arguments": {"operation_key": "tool-plan", "plan": draft()},
        }
    )
    assert result["success"]
    assert s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0] == before
    await tools.aclose()
    assert not (await tools.call({"tool": "researcher_plan_context", "arguments": {}}))[
        "success"
    ]


async def test_plan_owner_http_refuses_proof_fields_and_created_children_require_prerequisites(
    service_setup,
):
    """Only an exact paired owner decision expands a closed plan; pending child dependencies and text-only DONE are never accepted execution evidence."""
    import sqlite3
    from dataclasses import replace
    from types import SimpleNamespace

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.planning.store import ProjectPlans
    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    proposal = plans.propose(lease, "http-proposal", draft())
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.finish(
        lease, native_status="completed", summary="A proposal, not accepted work."
    )
    runtime = coordinator(s, SimpleNamespace(supported_task_types=("research", "plan")))
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    path = f"/api/projects/101/runs/{run.run_id}/project-plan"
    body = {
        "operation_key": "http-owner-plan",
        "proposal_sha256": proposal["proposal_sha256"],
        "context_version": lease.context_version,
    }
    async with app.router.lifespan_context(app), owner_client(app) as client:
        assert (await client.get(path)).json()["eligible"]
        assert (
            await client.post(path + "/accept", json={**body, "proof": True})
        ).status_code == 422
        assert (
            await client.post(
                path + "/accept", json=body, headers={"X-Researcher-CSRF": "invalid"}
            )
        ).status_code == 403
        response = await client.post(path + "/accept", json=body)
        assert response.status_code == 200, response.text
        result = response.json()
        assert (await client.post(path + "/accept", json=body)).json() == result
        child = result["tasks"]["change"]
        with pytest.raises(RunConflict, match="prerequisite"):
            s.c.store.admit(
                replace(
                    s.c.spec,
                    task_id=child,
                    operation_key="premature-child",
                    context_version=1,
                )
            )
        with pytest.raises(sqlite3.IntegrityError, match="acceptance"):
            s.c.conn.execute(
                "UPDATE tasks SET status='done'WHERE id=?", (result["tasks"]["learn"],)
            )
        s.c.conn.rollback()


def test_project_entry_recognizes_legacy_autonomy_after_the_flow_thread_exits():
    """A missing flow object does not prove its listeners/autonomy stopped; native start must still see those competing registered owners."""
    from backend.api.flow_manager import FlowManager

    manager = FlowManager()
    manager._autonomy[101] = object()
    assert manager.is_project_running(101)


def test_changed_accepted_plan_invalidates_its_children_before_any_new_execution(
    service_setup,
):
    """An accepted graph cannot keep authorizing child work after its planning premise changes, including a child with no task prerequisites."""
    from dataclasses import replace

    from backend.planning.store import ProjectPlans
    from backend.runtime.contracts import RunConflict

    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    proposal = plans.propose(lease, "root-proposal", draft())
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.finish(lease, native_status="completed", summary="Plan proposal only.")
    accepted = plans.accept(
        101,
        run.run_id,
        operation_key="root-accept",
        proposal_sha256=proposal["proposal_sha256"],
        context_version=lease.context_version,
    )
    child = accepted["tasks"]["learn"]
    before = s.c.store.context_snapshot(101, child)["context_version"]
    s.c.conn.execute(
        "UPDATE projects SET description='A changed project goal'WHERE id=101"
    )
    s.c.conn.commit()
    assert s.c.store.context_snapshot(101, child)["context_version"] > before
    assert plans.state(101, run.run_id)["acceptance_current"] is False
    with pytest.raises(RunConflict, match="plan"):
        s.c.store.admit(
            replace(
                s.c.spec,
                task_id=child,
                operation_key="obsolete-plan-child",
                context_version=before + 1,
            )
        )
