"""Owner receipt inspection is bounded, scoped and independent of agent authority."""

import base64
from dataclasses import replace

import httpx
import pytest

from backend.tests.runtime.test_workspace_delivery import owner_client


@pytest.fixture
def owner_app(coordination):
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    return create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )


def prepare(c, *, spec=None):
    run = c.store.admit(spec or c.spec)
    lease = c.store.claim(run.project_id, run.run_id, "fixture-owner")
    return run, lease


def record(
    c,
    lease,
    *,
    key="command",
    stdout=b"result\n",
    stderr=b"",
    exit_code=0,
    limited=False,
):
    reserved = c.store.reserve_job(
        lease,
        operation_key=key,
        spec=c.contracts.CommandSpec(
            ("/usr/bin/python3", "-c", "print('fixture')"), output_bytes=4194304
        ),
        workspace="/fixture",
        executor_id="fixture-executor",
    )
    return c.store.finish_job(
        lease,
        reserved.job.job_id,
        executor_id="fixture-executor",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        output_limited=limited,
        error="LostReceipt" if exit_code is None else None,
    )


async def test_owner_reads_binary_windows_after_authority_ends_without_mutation(
    coordination, owner_app
):
    c = coordination
    run, lease = prepare(c)
    job = record(c, lease, stdout=b"\xffA\xc3\xb1Z", stderr=b"error")
    c.store.cancel(101, run.run_id)
    assert not c.store.attempt_active(lease)
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        # Startup reconciles unowned history; the following reads must preserve it.
        before = c.store.get(101, run.run_id)
        path = f"/api/projects/101/runs/{run.run_id}/jobs/{job.job_id}"
        response = await owner.get(path, params={"max_bytes": 2})
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["exit_code"] == 0 and not data["local_execution_closed"]
        assert data["argv"] == ["/usr/bin/python3", "-c", "print('fixture')"]
        assert base64.b64decode(data["stdout"]["base64"]) == b"\xffA"
        assert data["stdout"]["utf8_lossy"] and data["stdout"]["next_offset"] == 2
        tail = await owner.get(
            path, params={"stdout_offset": 2, "stderr_offset": 5, "max_bytes": 3}
        )
        assert tail.status_code == 200
        assert (
            tail.json()["stdout"]["text"] == "ñZ"
            and not tail.json()["stdout"]["has_more"]
        )
        assert (
            tail.json()["stderr"]["total_bytes"] == 5
            and tail.json()["stderr"]["base64"] == ""
        )
    assert c.store.get(101, run.run_id) == before
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )


async def test_listing_paginates_all_jobs_without_loading_output_into_the_response(
    coordination, owner_app
):
    c = coordination
    run, lease = prepare(c)
    jobs = [
        record(c, lease, key=f"job-{number}", stdout=b"PRIVATE_BODY" * 400)
        for number in range(27)
    ]
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        path = f"/api/projects/101/runs/{run.run_id}/jobs"
        first = await owner.get(path)
        assert first.status_code == 200, first.text
        data = first.json()
        assert (
            data["total"] == 27 and len(data["items"]) == 25 and data["next_after_seq"]
        )
        assert "PRIVATE_BODY" not in first.text and "base64" not in first.text
        assert data["items"][0]["stdout_bytes"] == 4800
        second = await owner.get(path, params={"after_seq": data["next_after_seq"]})
        assert second.status_code == 200
        assert [item["job_id"] for item in data["items"] + second.json()["items"]] == [
            job.job_id for job in jobs
        ]
        assert second.json()["next_after_seq"] is None


async def test_pagination_cursor_preserves_sqlite_ids_larger_than_javascript_integers(
    coordination, owner_app
):
    c = coordination
    run, lease = prepare(c)
    first = record(c, lease, key="first")
    second = record(c, lease, key="second")
    c.conn.execute(
        "UPDATE runtime_jobs SET rowid=? WHERE id=?", (9007199254740993, first.job_id)
    )
    c.conn.execute(
        "UPDATE runtime_jobs SET rowid=? WHERE id=?", (9007199254740995, second.job_id)
    )
    c.conn.commit()
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        path = f"/api/projects/101/runs/{run.run_id}/jobs"
        page = (await owner.get(path, params={"limit": 1})).json()
        assert page["next_after_seq"] == "9007199254740993"
        assert page["items"][0]["seq"] == "9007199254740993"
        following = await owner.get(
            path, params={"limit": 1, "after_seq": page["next_after_seq"]}
        )
        assert following.status_code == 200
        assert following.json()["items"][0]["job_id"] == second.job_id
        assert following.json()["next_after_seq"] is None


async def test_job_and_list_are_scoped_to_both_project_and_run(coordination, owner_app):
    c = coordination
    run, lease = prepare(c)
    first = record(c, lease, stdout=b"ALPHA")
    other, other_lease = prepare(
        c, spec=replace(c.spec, task_id=1002, operation_key="other")
    )
    second = record(c, other_lease, stdout=b"OTHER_TASK_PRIVATE")
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        for path in (
            f"/api/projects/202/runs/{run.run_id}/jobs",
            f"/api/projects/202/runs/{run.run_id}/jobs/{first.job_id}",
            f"/api/projects/101/runs/{run.run_id}/jobs/{second.job_id}",
            f"/api/projects/101/runs/{other.run_id}/jobs/{first.job_id}",
        ):
            response = await owner.get(path)
            assert response.status_code == 404, response.text
            assert "OTHER_TASK_PRIVATE" not in response.text


async def test_agent_bearer_and_anonymous_clients_cannot_read_owner_jobs(
    coordination, owner_app
):
    c = coordination
    run, lease = prepare(c)
    job = record(c, lease)
    token = c.research.issue_grant(
        project_id=101, task_id=1001, agent_id="agent", permissions={"sources.read"}
    )
    async with (
        owner_app.router.lifespan_context(owner_app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=owner_app), base_url="http://localhost"
        ) as client,
    ):
        for suffix in ("jobs", "jobs/" + job.job_id):
            path = f"/api/projects/101/runs/{run.run_id}/{suffix}"
            assert (await client.get(path)).status_code == 401
            assert (
                await client.get(path, headers={"Authorization": "Bearer " + token})
            ).status_code == 401


async def test_unknown_result_stays_null_and_partial_bytes_remain_inspectable(
    coordination, owner_app
):
    c = coordination
    run, lease = prepare(c)
    job = record(c, lease, stdout=b"observed prefix", exit_code=None, limited=True)
    assert not c.store.attempt_active(lease)
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        response = await owner.get(
            f"/api/projects/101/runs/{run.run_id}/jobs/{job.job_id}"
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "unknown" and data["exit_code"] is None
        assert data["stdout"]["text"] == "observed prefix" and data["output_limited"]
        assert not data["local_execution_closed"]


async def test_large_output_is_recoverable_in_windows_without_silent_tail_loss(
    coordination, owner_app
):
    c = coordination
    run, lease = prepare(c)
    body = b"x" * (4194304 - 22) + b"COUNTEREVIDENCE_AT_END"
    job = record(c, lease, stdout=body)
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        path = f"/api/projects/101/runs/{run.run_id}/jobs/{job.job_id}"
        first = await owner.get(path, params={"max_bytes": 16384})
        assert first.status_code == 200, first.text
        assert len(first.content) < 50000 and first.json()["stdout"]["has_more"]
        tail = await owner.get(
            path, params={"stdout_offset": 4194304 - 22, "max_bytes": 22}
        )
        assert tail.json()["stdout"]["text"] == "COUNTEREVIDENCE_AT_END"
        assert not tail.json()["stdout"]["has_more"]


@pytest.mark.parametrize(
    "suffix",
    [
        "jobs?limit=0",
        "jobs?limit=101",
        "jobs?after_seq=-1",
        "jobs/JOB?max_bytes=16385",
        "jobs/JOB?stdout_offset=-1",
        "jobs/JOB?stderr_offset=2147483648",
    ],
)
async def test_invalid_read_windows_are_rejected(coordination, owner_app, suffix):
    c = coordination
    run, lease = prepare(c)
    job = record(c, lease)
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        path = f"/api/projects/101/runs/{run.run_id}/" + suffix.replace(
            "JOB", job.job_id
        )
        assert (await owner.get(path)).status_code == 422


async def test_invalid_owner_command_identity_is_a_validation_error(
    coordination, owner_app
):
    c = coordination
    run, _ = prepare(c)
    async with (
        owner_app.router.lifespan_context(owner_app),
        owner_client(owner_app) as owner,
    ):
        for path in (
            f"/api/projects/0/runs/{run.run_id}/jobs",
            "/api/projects/101/runs/" + "r" * 129 + "/jobs",
            f"/api/projects/101/runs/{run.run_id}/jobs/" + "j" * 129,
        ):
            assert (await owner.get(path)).status_code == 422
