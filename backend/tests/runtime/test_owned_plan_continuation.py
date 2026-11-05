"""Owned kernel/broker execution with controlled native generation; no subscription call or user-source modification."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414 -- real owned runtime fixture.


@pytest.mark.timeout(180)
async def test_owned_failed_delivery_continues_once_and_releases_dependent(
    owned_config,
):
    """A real native startup failure closes its peers; a fresh owner decision after restart produces one research successor and one dependent private change."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.planning.execution import PlanExecutions
    from backend.tests.runtime.test_development_workspace import fixture_git
    from backend.tests.runtime.test_plan_execution import accepted_plan, authorize
    from backend.tests.runtime.test_result_acceptance import accept

    c = owned_config
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
    s, plan, graph = accepted_plan(c.s)
    executions, authorization = authorize(s, plan)
    eid = authorization["execution_id"]
    root_task = graph["tasks"]["learn"]
    spec, binding = executions.prepare(eid, root_task)
    original = s.c.store.admit(spec, binding=binding)
    binary = Path(c.settings["codex_binary"])
    native_source = binary.read_text()
    binary.write_text(
        native_source.replace(
            'elif method == "thread/start":\n',
            'elif method == "thread/start":\n        sys.exit(17)\n',
        )
    )

    async def terminal(runtime, task_id, *, excluding=None):
        """Observe the actual durable run until its worker terminates; never restart because polling has not yet found a run."""
        for _ in range(1200):
            runs = runtime.store.task_runs(101, task_id)
            run = next((r for r in runs if r.run_id != excluding), None)
            if run and run.status not in (
                "queued",
                "running",
                "cancelling",
                "reconciling",
            ):
                await runtime.wait(run.run_id)
                return runtime.store.get(101, run.run_id)
            await asyncio.sleep(0.05)
        raise AssertionError("Owned delivery did not reach a terminal state")

    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    async with runtime:
        failed = await terminal(runtime, root_task)
        assert failed.run_id == original.run_id and failed.status == "failed", failed
        preview = PlanExecutions(runtime.store).continuation_state(
            101,
            eid,
            next(
                d["delivery_id"]
                for d in executions.state(101, plan.run_id)["execution"]["deliveries"]
                if d["run_id"] == failed.run_id
            ),
        )
        assert preview["eligible"], preview
    binary.write_text(native_source)
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    async with runtime:
        executions = PlanExecutions(runtime.store)
        previous = next(
            d
            for d in executions.state(101, plan.run_id)["execution"]["deliveries"]
            if d["run_id"] == original.run_id
        )
        preview = executions.continuation_state(101, eid, previous["delivery_id"])
        command = {
            "operation_key": "owned-continuation",
            "snapshot_sha256": preview["snapshot_sha256"],
        }
        receipt = await runtime.continue_plan_delivery(
            101, eid, previous["delivery_id"], **command
        )
        successor = await terminal(runtime, root_task, excluding=original.run_id)
        assert successor.status == "needs_review", successor
        assert (
            await runtime.continue_plan_delivery(
                101, eid, previous["delivery_id"], **command
            )
            == receipt
        )
        state = runtime.store.result_state(101, successor.run_id)
        assert state["eligible"], state
        accept(
            SimpleNamespace(store=runtime.store),
            SimpleNamespace(
                run_id=successor.run_id, context_version=successor.context_version
            ),
            state,
        )
        await runtime.dispatch_planned_work()
        child = await terminal(runtime, graph["tasks"]["change"])
        assert (
            child.status == "needs_review" and child.execution_kind == "development"
        ), child
        assert runtime.store.code_result_state(101, child.run_id)["candidate_current"]
        with runtime.store._transaction() as conn:
            frozen = json.loads(
                conn.execute(
                    "SELECT i.input_text FROM runtime_input_snapshots i JOIN runtime_attempts a ON a.id=i.attempt_id WHERE a.run_id=?",
                    (successor.run_id,),
                ).fetchone()[0]
            )
            assert (
                frozen["work_delivery"]["continuation"]["previous_run"]["run_id"]
                == failed.run_id
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
            assert len(runtime.store.task_runs(101, root_task)) == 2
        assert (c.s.workspace / "fact.txt").read_text() == "137"
