"""Native project planning with actual configured host/Ken/broker/SQLite lifecycle and controlled generation, never a real subscription turn."""

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414 -- original physical runtime fixture.


@pytest.mark.timeout(180)
async def test_owned_project_start_proposes_then_owner_accepts_without_executing_children(
    owned_config,
):
    """The migrated project entry uses a readonly native turn, structured proposal tools and physical closure; owner expansion remains a separate transaction."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.planning.store import ProjectPlans

    c = owned_config
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    before = c.s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0]
    project_before = c.s.c.conn.execute("SELECT count(*)FROM tasks WHERE project_id=101").fetchone()[0]
    import json

    c.s.c.conn.execute("INSERT INTO flow_snapshots(project_id,flow_name,current_step,state_json) VALUES(101,'main_project_flow','planning',?)", (json.dumps({"requirements":"The old request mentions137units.","plan":"Inspect first; old approval is not current permission.","thread_id":"old-session-must-not-resume"}),))
    c.s.c.conn.commit()
    async with runtime:
        run = await runtime.start_project_plan(
            101,
            operation_key="owned-plan-start",
            prompt="Investigate the issue and propose a plan.",
            repository_id=11,
        )
        await runtime.wait(run.run_id)
        saved = runtime.store.get(101, run.run_id)
        assert saved.status == "needs_review", saved
        state = ProjectPlans(runtime.store).state(101, run.run_id)
        assert state["eligible"] and state["proposal"], state
        historic_basis = [item for item in state["proposal"]["draft"]["basis"] if item["source"].endswith(":requirements")]
        assert historic_basis and "137units" in historic_basis[0]["quote"]
        assert state["snapshot"]["source_origins"][historic_basis[0]["source"]] == "legacy_snapshot"
        assert state["snapshot"]["project_history"]["task_inventory"]["total"] == project_before
        assert (
            c.s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0] == before + 1
        )
        decision = {
            "operation_key": "accept-owned-plan",
            "proposal_sha256": state["proposal"]["proposal_sha256"],
            "context_version": state["context_version"],
        }
        accepted = ProjectPlans(runtime.store).accept(101, run.run_id, **decision)
        assert accepted["execution_started"] is False and len(accepted["tasks"]) == 2
        assert (
            ProjectPlans(runtime.store).accept(101, run.run_id, **decision) == accepted
        )
        assert (
            await runtime.start_project_plan(
                101,
                operation_key="owned-plan-start",
                prompt="Investigate the issue and propose a plan.",
                repository_id=11,
            )
        ).run_id == run.run_id
        with runtime.store._transaction() as conn:
            dispatches = conn.execute(
                "SELECT count(*)FROM runtime_inference_dispatches d JOIN runtime_attempts a ON a.id=d.attempt_id WHERE a.run_id=?",
                (run.run_id,),
            ).fetchone()[0]
            assert dispatches == 1
            import json

            frozen = conn.execute(
                "SELECT business_catalog_json,developer_instructions FROM runtime_input_snapshots i JOIN runtime_attempts a ON a.id=i.attempt_id WHERE a.run_id=?",
                (run.run_id,),
            ).fetchone()
            names = {
                tool["name"] for tool in json.loads(frozen["business_catalog_json"])
            }
            assert {"researcher_plan_context", "researcher_plan_propose"} <= names
            assert "researcher_result_propose" not in names
            assert (
                "host_default is not direct user testimony"
                in frozen["developer_instructions"]
            )
            assert (
                conn.execute(
                    "SELECT count(*)FROM runtime_peers WHERE state!='closed'"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT count(*)FROM runtime_runs WHERE task_id IN (?,?)",
                    tuple(accepted["tasks"].values()),
                ).fetchone()[0]
                == 0
            )
        assert (c.s.workspace / "fact.txt").read_text() == "137"
