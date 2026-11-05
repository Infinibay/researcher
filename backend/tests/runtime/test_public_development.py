"""Owner entry to development, exact checks and independent review with controlled generation and real persistence/kernel/Git."""

import json

import pytest

from backend.tests.runtime.test_development_session import (
    development_config as development_config,  # noqa: PLC0414 -- actual owned configuration fixture.
)
from backend.tests.runtime.test_owned_factory import (
    owned_config as owned_config,  # noqa: PLC0414 -- dependency of development_config.
)


@pytest.mark.timeout(150)
async def test_owner_http_develops_checks_reviews_and_accepts_exact_candidate(
    development_config,
):
    """Public requests share the original owned coordinator; duplicate admission never edits, checks or reviews twice."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_development_workspace import fixture_git
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = development_config
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
    recipe = {
        "argv": [
            "/usr/bin/python3",
            "-c",
            "from pathlib import Path; assert Path('fact.txt').read_text() == '200'; print('exact value checked')",
        ],
        "framework": "command",
        "timeout_seconds": 5,
        "environment_id": "system",
    }
    c.settings["development_checks"] = [recipe]
    c.settings["limits"]["wall_seconds"] = 90
    c.path.write_text(json.dumps(c.settings))
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        workspace_path = "/api/projects/101/tasks/1001/workspace"
        workspace = (await owner.get(workspace_path)).json()
        assert workspace["runtime"]["supported_task_types"] == [
            "research",
            "code",
            "bug_fix",
            "plan",
        ]
        version = workspace["context"]["context_version"]
        body = {
            "operation_key": "public-author",
            "context_version": version,
            "request": "Change fact.txt from 137 to 200; preserve original source and state actual checks.",
            "repository_id": 11,
        }
        path = "/api/projects/101/tasks/1001/runs"
        response = await owner.post(path, json=body)
        assert response.status_code == 202, response.text
        run = response.json()
        runtime = app.state.runtime_service
        await runtime.wait(run["run_id"])
        replay = await owner.post(path, json=body)
        assert replay.status_code == 202 and replay.json()["run_id"] == run["run_id"]
        assert replay.json()["execution_kind"] == "development"
        assert replay.json()["status"] == "needs_review"
        state_path = f"/api/projects/101/runs/{run['run_id']}/code-result"
        state = (await owner.get(state_path)).json()
        assert state["candidate_current"] and not state["eligible"]
        assert len(state["packet"]["checks"]) == 1
        check = state["packet"]["checks"][0]
        assert check["spec"]["argv"] == recipe["argv"]
        assert check["result"]["status"] == "passed"
        record = runtime.store.input_record(101, run["run_id"])
        assert "exact value checked" in record["developer_instructions"]
        assert (c.s.workspace / "fact.txt").read_text() == "137"
        review_body = {
            "operation_key": "public-review",
            "context_version": version,
            "attempt_id": state["candidate"]["attempt_id"],
            "subject_sha256": state["subject_sha256"],
            "request": "Review the exact candidate against the original request; cite source and state the limits of checks.",
        }
        review_path = "/api/projects/101/tasks/1001/code-reviews"
        for forbidden in ("actor_id", "repository_id", "publication"):
            invalid = await owner.post(
                review_path, json={**review_body, forbidden: "caller-selected"}
            )
            assert invalid.status_code == 422
        stale = await owner.post(
            review_path, json={**review_body, "subject_sha256": "0" * 64}
        )
        assert stale.status_code == 409
        foreign = await owner.post(
            review_path.replace("projects/101", "projects/202"), json=review_body
        )
        assert foreign.status_code in (404, 409)
        wrong_task = await owner.post(
            review_path.replace("tasks/1001", "tasks/1002"), json=review_body
        )
        assert wrong_task.status_code == 409
        review_response = await owner.post(review_path, json=review_body)
        assert review_response.status_code == 202, review_response.text
        reviewer = review_response.json()
        assert reviewer["actor_id"] != run["actor_id"]
        await runtime.wait(reviewer["run_id"])
        review_replay = await owner.post(review_path, json=review_body)
        assert (
            review_replay.status_code == 202
            and review_replay.json()["run_id"] == reviewer["run_id"]
        )
        conflict = await owner.post(
            review_path,
            json={
                **review_body,
                "request": "Different instructions under the same operation",
            },
        )
        assert conflict.status_code == 409
        state = (await owner.get(state_path)).json()
        assert state["review"]["state"] == "confirmed" and state["eligible"]
        acceptance = await owner.post(
            state_path + "/accept",
            json={
                "operation_key": "public-owner-acceptance",
                "context_version": version,
                "attempt_id": state["candidate"]["attempt_id"],
                "subject_sha256": state["subject_sha256"],
                "review_sha256": state["review_sha256"],
                "acknowledge_limits": True,
                "note": "Accept the exact independently reviewed candidate; publication remains separate.",
            },
        )
        assert acceptance.status_code == 200, acceptance.text
        assert (
            acceptance.json()["task_accepted"]
            and not acceptance.json()["publication_performed"]
        )
        assert (c.s.workspace / "fact.txt").read_text() == "137"
        with runtime.store._transaction() as conn:
            assert (
                conn.execute("SELECT COUNT(*) FROM runtime_code_candidates").fetchone()[
                    0
                ]
                == 1
            )
            assert (
                conn.execute("SELECT COUNT(*) FROM runtime_code_checks").fetchone()[0]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM runtime_code_review_requests"
                ).fetchone()[0]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM runtime_code_acceptances"
                ).fetchone()[0]
                == 1
            )


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        [{"argv": ["python", "-m", "pytest"], "framework": "pytest"}],
        [{"argv": ["/bin/true"], "framework": "command", "extra": True}],
        [{"argv": ["/bin/true"], "framework": "command"}] * 9,
    ],
)
def test_development_recipe_configuration_rejects_ambiguous_policy(settings):
    """Bad host recipes cannot enable authoring with guessed executables, ignored fields or an unbounded check list."""
    from backend.runtime.development_policy import parse_development_checks

    with pytest.raises((TypeError, ValueError)):
        parse_development_checks(settings)


def test_development_recipe_policy_freezes_complete_explicit_host_plan():
    """Copy mutable configuration into immutable recipes and disclose every command in frozen host instructions."""
    from backend.runtime.development_policy import (
        development_instructions,
        parse_development_checks,
    )

    original = [{"argv": ["/bin/true"], "framework": "command"}]
    checks = parse_development_checks(original)
    original[0]["argv"][0] = "/bin/false"
    assert checks[0].argv == ("/bin/true",)
    assert checks[0].sha256 in development_instructions(checks)
    assert "No host checks" in development_instructions(())


async def test_older_adapter_does_not_admit_development_or_claim_its_capabilities(
    service_setup,
):
    """The public service rejects unsupported authoring before persistence or tool authority instead of falling back to research."""
    from dataclasses import replace

    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type='bug_fix' WHERE id=1001")
    s.c.conn.commit()
    runtime = coordinator(s, ControlledInference(s))
    assert runtime.supported_task_types == ("research",)
    version = runtime.store.context_snapshot(101, 1001)["context_version"]
    async with runtime:
        with pytest.raises(RunConflict, match="does not support"):
            await runtime.submit(replace(s.c.spec, context_version=version))
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0
    assert s.c.conn.execute("SELECT COUNT(*) FROM tool_grants").fetchone()[0] == 0


@pytest.mark.timeout(100)
@pytest.mark.parametrize("stage", ["capture", "check"])
async def test_completed_turn_does_not_hide_failed_candidate_pipeline(
    development_config, monkeypatch, stage
):
    """A completed native turn cannot conceal missing capture/check closure or mark the public development task done."""
    from dataclasses import replace

    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.contracts import RunConflict
    from backend.runtime.owned_runtime import OwnedInferenceSession
    from backend.tests.runtime.test_development_workspace import fixture_git

    c = development_config
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
    c.settings["development_checks"] = [{"argv": ["/bin/true"], "framework": "command"}]
    c.path.write_text(json.dumps(c.settings))

    async def unavailable(*args):
        """Inject a host pipeline failure after the actual native turn, preserving real finalization and physical closure."""
        raise RunConflict("Controlled host pipeline failure")

    monkeypatch.setattr(
        OwnedInferenceSession,
        "capture_candidate" if stage == "capture" else "run_check",
        unavailable,
    )
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    version = runtime.store.context_snapshot(101, 1001)["context_version"]
    async with runtime:
        run = await runtime.submit(
            replace(c.s.c.spec, context_version=version), repository_id=11
        )
        await runtime.wait(run.run_id)
        result = runtime.store.get(101, run.run_id)
        assert (
            result.status == "failed"
            and result.issue["code"] == "code_candidate_unconfirmed"
        )
        assert runtime.store.context_snapshot(101, 1001)["task"]["status"] != "done"
        with runtime.store._transaction() as conn:
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM runtime_code_acceptances"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'"
                ).fetchone()[0]
                == 0
            )
    assert (c.s.workspace / "fact.txt").read_text() == "137"
