"""Owner destination discovery uses bounded GETs and original accepted provenance; all upstream responses here are controlled, with no remote writes."""

from types import SimpleNamespace

import httpx
import pytest

from backend.tests.runtime.test_remote_runtime import (
    candidate_state as candidate_state,  # noqa: PLC0414
)
from backend.tests.runtime.test_remote_runtime import (
    code_result as code_result,  # noqa: PLC0414
)
from backend.tests.runtime.test_remote_runtime import (
    development_state as development_state,  # noqa: PLC0414
)
from backend.tests.runtime.test_remote_runtime import (
    publication_request as publication_request,  # noqa: PLC0414
)
from backend.tests.runtime.test_remote_runtime import (
    remote_request as remote_request,  # noqa: PLC0414
)
from backend.tests.runtime.test_remote_runtime import (
    review_records as review_records,  # noqa: PLC0414
)
from backend.tests.runtime.test_remote_runtime import (
    review_state as review_state,  # noqa: PLC0414
)

pytestmark = pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)


@pytest.mark.parametrize("change", [False, True])
async def test_destination_preview_derives_server_identity_without_effects_and_rejects_changed_acceptance(
    remote_request, change
):
    """Observed repo ID/branches come from the configured origin, and a context correction during a lookup invalidates its result before owner use."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.forgejo_publication import ForgejoPublicationClient
    from backend.runtime.remote_destinations import RemoteDestinations

    s, _, records, request = remote_request
    view = records.local.request(101, request.origin_run_id)["view"]
    calls = []

    def upstream(req):
        """Model fixed server GET results and one actual owner context correction during lookup."""
        calls.append((req.method, str(req.url)))
        if change and len(calls) == 1:
            s.c.store.correct_context(
                project_id=101,
                task_id=1001,
                expected_version=1,
                operation_key="during-preview",
                statement="New requirement",
                source_kind="user_message",
                source_reference="owner",
            )
        if "/branches/" in req.url.path:
            return (
                httpx.Response(404)
                if req.url.path.endswith("/new-change")
                else httpx.Response(200, json={"commit": {"id": view["base_sha"]}})
            )
        return httpx.Response(
            200,
            json={
                "id": 71,
                "full_name": "owner/repo",
                "clone_url": request.remote.clone_url,
            },
        )

    before = s.c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0]
    async with ForgejoPublicationClient(
        request.remote.api_base,
        "synthetic-token",
        transport=httpx.MockTransport(upstream),
    ) as client:
        if change:
            with pytest.raises(RunConflict):
                await RemoteDestinations(s.c.store).observe(
                    101,
                    request.origin_run_id,
                    "refs/heads/new-change",
                    "refs/heads/main",
                    client=client,
                )
        else:
            packet = await RemoteDestinations(s.c.store).observe(
                101,
                request.origin_run_id,
                "refs/heads/new-change",
                "refs/heads/main",
                client=client,
            )
            assert (
                packet["remote"]["repository_id"] == 71 and packet["target_sha"] is None
            )
            assert (
                packet["observed_base_sha"] == view["base_sha"]
                and packet["push_allowed"]
                and packet["pull_allowed"]
            )
            assert packet["head_sha"] == view["head_sha"] and packet["task_id"] == 1001
    assert all(
        method == "GET"
        and url.startswith(request.remote.api_base + "/repos/owner/repo")
        for method, url in calls
    )
    assert s.c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == before


async def test_destination_discovery_refuses_a_registered_foreign_origin_before_sending_credentials(
    remote_request,
):
    """A registered URL is still not permission to send the configured host token elsewhere."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.forgejo_publication import ForgejoPublicationClient
    from backend.runtime.remote_destinations import RemoteDestinations

    s, _, _, request = remote_request
    s.c.conn.execute(
        "UPDATE repositories SET remote_url='https://foreign.example/owner/repo.git'"
    )
    s.c.conn.commit()
    calls = []
    async with ForgejoPublicationClient(
        request.remote.api_base,
        "synthetic-token",
        transport=httpx.MockTransport(lambda req: calls.append(req)),
    ) as client:
        with pytest.raises((ValueError, RunConflict)):
            await RemoteDestinations(s.c.store).observe(
                101,
                request.origin_run_id,
                "refs/heads/new-change",
                "refs/heads/main",
                client=client,
            )
    assert calls == []


async def test_owner_remote_discovery_history_and_actual_capability_are_scoped(
    remote_request,
):
    """Strict owner preview and saved action history expose configured capability without scheduling inference or accepting client URL/credential input."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, _, records, request = remote_request
    native = SimpleNamespace(supported_task_types=("code", "bug_fix", "research"))
    runtime = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    path = f"/api/projects/101/code-publications/{request.origin_run_id}/remote-preview"
    body = {"target_ref": "refs/heads/new-change", "base_ref": "refs/heads/main"}
    async with app.router.lifespan_context(app), owner_client(app) as client:
        assert (await client.get("/api/projects/101/tasks/1001/workspace")).json()[
            "runtime"
        ]["remote_publication"] is False
        assert (await client.post(path, json=body)).status_code == 409
        calls = []

        async def preview(store, project_id, run_id, target_ref, base_ref):
            """Hold network discovery at the configured adapter boundary; this owner test concerns scope/strictness and dispatch."""
            calls.append((project_id, run_id, target_ref, base_ref))
            return {
                "project_id": project_id,
                "local_publication_run_id": run_id,
                "task_id": 1001,
            }

        native.supports_remote_publication = True
        native.preview_remote = preview
        assert (
            await client.post(path, json={**body, "token": "client-secret"})
        ).status_code == 422
        assert (
            await client.post(path, json=body, headers={"X-Researcher-CSRF": "bad"})
        ).status_code == 403
        assert (await client.post(path, json=body)).status_code == 200
        assert len(calls) == 1
        run, _ = records.admit_once(101, request)
        history = await client.get(
            f"/api/projects/101/code-publications/{request.origin_run_id}/remote-publications"
        )
        assert history.status_code == 200, history.text
        packet = history.json()
        assert (
            packet["task_id"] == 1001
            and packet["actions"][0]["run"]["run_id"] == run.run_id
        )
        assert (
            packet["actions"][0]["request"]["stage"] == "push"
            and not packet["truncated"]
        )
        assert (
            await client.get(
                f"/api/projects/999/code-publications/{request.origin_run_id}/remote-publications"
            )
        ).status_code == 404
