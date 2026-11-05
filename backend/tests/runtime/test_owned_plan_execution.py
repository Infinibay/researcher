"""Actual owned native planning/research/development coordination with controlled generation; no real subscription turn or user repository modification."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414 -- shared physical runtime fixture.


@pytest.mark.parametrize("root_type", ["research", "investigation"])
@pytest.mark.timeout(180)
async def test_owned_accepted_plan_dispatches_root_then_exact_evidence_to_private_development(
    owned_config,
    root_type,
):
    """One original owner execution sends three native turns total: planner, researcher and developer; only owner-accepted research wakes its dependent and no code is accepted or published."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.planning.execution import PlanExecutions
    from backend.planning.store import ProjectPlans
    from backend.tests.runtime.test_development_workspace import fixture_git
    from backend.tests.runtime.test_result_acceptance import accept

    c = owned_config
    if root_type == "investigation":
        from pathlib import Path

        fixture = Path(c.settings["codex_binary"])
        original = fixture.read_text()
        assert original.count('"type": "research",') == 1
        fixture.write_text(
            original.replace('"type": "research",', '"type": "investigation",')
        )
    await fixture_git(c.s.workspace, "init", "-q")
    await fixture_git(c.s.workspace, "add", "fact.txt")
    await fixture_git(
        c.s.workspace,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "base",
    )
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    async with runtime:
        plan = await runtime.start_project_plan(
            101,
            operation_key="physical-work-plan",
            prompt="Investigate the issue and propose a plan.",
            repository_id=11,
        )
        await runtime.wait(plan.run_id)
        plans = ProjectPlans(runtime.store)
        state = plans.state(101, plan.run_id)
        graph = plans.accept(
            101,
            plan.run_id,
            operation_key="physical-accept-graph",
            proposal_sha256=state["proposal"]["proposal_sha256"],
            context_version=state["context_version"],
        )
        executions = PlanExecutions(runtime.store)
        preview = executions.state(101, plan.run_id)
        command = {
            "operation_key": "physical-execute",
            "manifest_sha256": preview["manifest_sha256"],
        }
        receipt = await runtime.execute_plan(101, plan.run_id, **command)
        assert await runtime.execute_plan(101, plan.run_id, **command) == receipt

        async def issued(task):
            """Wait for the authoritative original delivery ID, without restarting on an observation timeout."""
            for _ in range(200):
                deliveries = executions.state(101, plan.run_id)["execution"][
                    "deliveries"
                ]
                run_id = next(d["run_id"] for d in deliveries if d["task_id"] == task)
                if run_id:
                    await runtime.wait(run_id)
                    return runtime.store.get(101, run_id)
                await asyncio.sleep(0.05)
            raise AssertionError("Original authorized delivery was not admitted")

        tasks = list(graph["tasks"].values())
        root = await issued(tasks[0])
        assert root.status == "needs_review", root
        assert not runtime.store.task_runs(101, tasks[1])
        research_state = runtime.store.result_state(101, root.run_id)
        assert research_state["eligible"], research_state
        if root_type == "investigation":
            with runtime.store._transaction() as conn:
                snapshot = json.loads(
                    conn.execute(
                        "SELECT snapshot_json FROM runtime_result_proposals WHERE run_id=?",
                        (root.run_id,),
                    ).fetchone()[0]
                )
                assert (
                    snapshot["reports"][0]["investigation"]["areas"][1]["finding_ids"]
                    == []
                )
                frozen = json.loads(
                    conn.execute(
                        "SELECT input_text FROM runtime_input_snapshots i JOIN runtime_attempts a ON a.id=i.attempt_id WHERE a.run_id=?",
                        (root.run_id,),
                    ).fetchone()[0]
                )
                assert frozen["execution"]["kind"] == "investigation"
                assert frozen["execution"]["workspace_access"] == "readonly"
                assert snapshot["scientific_confidence"] is None
            threads = [
                json.loads(p.read_text())
                for p in c.s.control.glob("native-state/*/home/fixture-thread.json")
            ]
            author = next(
                t
                for t in threads
                if any(
                    tool["name"] == "researcher_investigation_summary"
                    for tool in t["catalog"]
                )
            )
            names = {tool["name"] for tool in author["catalog"]}
            assert (
                "researcher_report_write" not in names
                and "researcher_review_decide" not in names
            )
            assert author["sandbox"] == "read-only"
        accept(
            SimpleNamespace(store=runtime.store),
            SimpleNamespace(run_id=root.run_id, context_version=root.context_version),
            research_state,
        )
        await runtime.dispatch_planned_work()
        child = await issued(tasks[1])
        assert (
            child.status == "needs_review" and child.execution_kind == "development"
        ), child
        result = runtime.store.code_result_state(101, child.run_id)
        assert result["candidate_current"] and result["acceptance"] is None, result
        assert (c.s.workspace / "fact.txt").read_text() == "137"
        with runtime.store._transaction() as conn:
            packet = json.loads(
                conn.execute(
                    "SELECT input_text FROM runtime_input_snapshots i JOIN runtime_attempts a ON a.id=i.attempt_id WHERE a.run_id=?",
                    (child.run_id,),
                ).fetchone()[0]
            )
            source = packet["work_delivery"]["prerequisites"][0]
            assert source["run_id"] == root.run_id
            assert "137" in json.dumps(source["snapshot"])
            if root_type == "investigation":
                assert source["snapshot"]["reports"][0]["investigation"][
                    "scope_excludes"
                ] == ["Repetir la medición original."]
            assert source["snapshot"]["limitations"] == [
                "La medición original no se repitió; el cálculo es evidencia separada."
            ]
            assert (
                conn.execute(
                    "SELECT count(*)FROM runtime_inference_dispatches"
                ).fetchone()[0]
                == 3
            )
            assert (
                conn.execute(
                    "SELECT count(*)FROM runtime_peers WHERE state!='closed'"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute("SELECT count(*)FROM runtime_code_acceptances").fetchone()[
                    0
                ]
                == 0
            )
