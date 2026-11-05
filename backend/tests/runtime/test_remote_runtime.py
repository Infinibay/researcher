"""Remote runtime ownership/stage records over explicit synthetic closure/accepted witnesses; real remote/network ownership has separate integration obligations."""

from dataclasses import replace

import pytest

from backend.tests.runtime.test_code_publications import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_publications import code_result as code_result  # noqa: PLC0414 -- original fixture dependencies.
from backend.tests.runtime.test_code_publications import (
    development_state as development_state,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_publications import (
    publication_request as publication_request,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_publications import (
    review_records as review_records,  # noqa: PLC0414 -- original fixture dependencies.
)
from backend.tests.runtime.test_code_publications import review_state as review_state  # noqa: PLC0414 -- original fixture dependencies.

pytestmark = pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)


@pytest.fixture
def remote_request(publication_request):
    """Retain a successful local publication with explicit synthetic original Git/closure proof and a registered exact HTTPS destination."""
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        PublicationRefObservation,
    )
    from backend.runtime.remote_publication import RemoteRepository
    from backend.runtime.remote_runtime import RemotePublications, RemotePushRequest

    s, candidate, local, intent = publication_request
    run, _ = local.admit_once(101, candidate["run_id"], intent)
    lease, peers = AttemptPeers.claim(
        s.c.store, 101, run.run_id, "synthetic-local-publisher"
    )
    command = peers.registry.prepare(lease, "command")
    peers.registry.close(command)
    request = local.request(101, run.run_id)
    view = request["view"]
    ref = PublicationRefIntent(run.run_id, intent.target_ref, None)
    local.complete(
        lease,
        PublicationRefObservation(
            "published",
            True,
            view["head_sha"],
            view["head_sha"],
            view["head_sha"],
            ref.receipt_ref,
        ),
        {
            "domain_closed": True,
            "grant_id": "synthetic-local-grant",
            "operations": [
                {
                    "execution_closed": True,
                    "exit_code": 0,
                    "manifest": {
                        "profile": "owned-git-publication-v1",
                        "launch": {"input_text": ref.transaction(view["head_sha"])},
                    },
                }
            ],
        },
    )
    remote = RemoteRepository(
        "https://forgejo.example/api/v1",
        71,
        "owner/repo",
        "https://forgejo.example/owner/repo.git",
    )
    s.c.conn.execute(
        "UPDATE repositories SET remote_url=? WHERE id=?",
        (remote.clone_url, view["source"]["repository_id"]),
    )
    s.c.conn.commit()
    request = RemotePushRequest(
        "owner-push", run.run_id, remote, "refs/heads/reviewed-change", None
    )
    return s, candidate, RemotePublications(s.c.store), request


def claim_remote(s, records, run):
    """Claim real storage authority and close a synthetic command peer only for stages that require Git process ownership."""
    from backend.runtime.peer_registry import AttemptPeers

    lease, peers = AttemptPeers.claim(
        s.c.store, 101, run.run_id, "synthetic-remote-owner"
    )
    if records.request(101, run.run_id)["stage"] != "pull":
        peer = peers.registry.prepare(lease, "command")
        peers.registry.close(peer)
    return lease, peers


def positive_push(records, run_id):
    """Construct a typed positive remote receipt from the exact stored host protocol, explicitly without claiming remote server execution."""
    from backend.runtime.remote_publication import RemotePushObservation

    protocol = records.protocol(101, run_id)
    if isinstance(protocol, dict):
        protocol = protocol["push"]
    return RemotePushObservation(
        "published",
        True,
        protocol.head_sha,
        protocol.head_sha,
        protocol.head_sha,
        protocol.receipt_ref,
        protocol.remote.repository_id,
    )


def test_remote_admission_owns_new_host_identity_and_issued_effect_is_not_dispatched_twice(
    remote_request,
):
    """Original scoped owner retry preserves one new host run; its global receipt identity and stage reservation never reuse the closed local attempt."""
    from backend.runtime.contracts import RunConflict

    s, candidate, records, request = remote_request
    run, created = records.admit_once(101, request)
    assert created and run.execution_kind == "remote_publication"
    assert records.admit_once(101, request) == (run, False)
    assert records.protocol(101, run.run_id).operation_key == run.run_id
    assert records.protocol(101, run.run_id).operation_key != request.operation_key
    lease, peers = claim_remote(s, records, run)
    assert (
        peers.ids == {}
        and s.c.store.code_result_state(101, candidate["run_id"])["acceptance_current"]
    )
    first = records.issue(lease, "push")
    second = records.issue(lease, "push")
    assert (
        first["dispatch"]
        and not second["dispatch"]
        and first["operation_id"] == second["operation_id"]
    )
    with pytest.raises(RunConflict):
        peers.registry.prepare(lease, "native")
    records.observe(
        lease, "push", positive_push(records, run.run_id), client_closed=True
    )
    result = records.complete(
        lease, None, {"domain_closed": True, "grant_id": "synthetic-remote-grant"}
    )
    assert result["effects"]["push"]["state"] == "published"
    assert s.c.store.get(101, run.run_id).status == "accepted"
    assert s.c.store.context_snapshot(101, 1001)["task"]["status"] == "done"


def test_remote_unknown_effect_retains_original_issued_stage_and_context_withdraws_write_authority(
    remote_request,
):
    """Absent remote evidence is still unknown; a context correction fences new effects while the original intent/receipt remains recoverable."""
    from backend.runtime.contracts import StaleAttempt

    s, _candidate, records, request = remote_request
    run, _ = records.admit_once(101, request)
    lease, _peers = claim_remote(s, records, run)
    records.issue(lease, "push")
    unknown = replace(
        positive_push(records, run.run_id),
        state="uncertain",
        target_current=False,
        observed_marker_sha=None,
        observed_target_sha=None,
    )
    records.observe(lease, "push", unknown, client_closed=True)
    records.complete(
        lease, None, {"domain_closed": True, "grant_id": "synthetic-remote-grant"}
    )
    assert s.c.store.get(101, run.run_id).status == "reconciling"
    assert records.request(101, run.run_id)["result"] is None
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=run.context_version,
        operation_key="correct-remote",
        statement="Changed requirement",
        source_kind="user_message",
        source_reference="owner",
    )
    with pytest.raises(StaleAttempt):
        records.issue(lease, "push")
    historical, created = records.admit_once(101, request)
    assert historical.run_id == run.run_id and not created


def test_pr_and_merge_have_separate_original_effect_stages_and_no_dummy_http_command(
    remote_request,
):
    """Push→PR→merge records preserve exact provenance; an HTTP-only PR needs no fictitious model/process peers, and merge bookkeeping waits for Git CAS evidence."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.forgejo_publication import (
        RemoteMergeObservation,
        RemotePullObservation,
    )
    from backend.runtime.remote_runtime import RemoteMergeRequest, RemotePullRequest

    s, _candidate, records, request = remote_request
    push, _ = records.admit_once(101, request)
    lease, _ = claim_remote(s, records, push)
    records.issue(lease, "push")
    records.observe(
        lease, "push", positive_push(records, push.run_id), client_closed=True
    )
    records.complete(lease, None, {"domain_closed": True, "grant_id": "synthetic-push"})
    push_protocol = records.protocol(101, push.run_id)
    pull, _ = records.admit_once(
        101,
        RemotePullRequest(
            "owner-pr",
            push.run_id,
            "refs/heads/main",
            push_protocol.base_sha,
            "Original title",
            "Original description",
        ),
    )
    lease, peers = claim_remote(s, records, pull)
    assert peers.ids == {} and peers._rows() == []
    records.issue(lease, "pull")
    protocol = records.protocol(101, pull.run_id)
    records.observe(
        lease,
        "pull",
        RemotePullObservation(
            "created",
            8,
            True,
            protocol.head_sha,
            protocol.base_sha,
            protocol.marker,
            71,
        ),
        client_closed=True,
    )
    records.complete(lease, None, {"http_client_closed": True})
    merge, _ = records.admit_once(101, RemoteMergeRequest("owner-merge", pull.run_id))
    lease, _ = claim_remote(s, records, merge)
    with pytest.raises(RunConflict):
        records.issue(lease, "merge_record")
    records.issue(lease, "merge_git")
    records.observe(
        lease, "merge_git", positive_push(records, merge.run_id), client_closed=True
    )
    records.issue(lease, "merge_record")
    merge_protocol = records.protocol(101, merge.run_id)
    records.observe(
        lease,
        "merge_record",
        RemoteMergeObservation(
            "merged", 8, protocol.head_sha, True, merge_protocol["push"].receipt_ref, 71
        ),
        client_closed=True,
    )
    result = records.complete(
        lease,
        None,
        {
            "domain_closed": True,
            "http_client_closed": True,
            "grant_id": "synthetic-merge",
        },
    )
    assert result["effects"]["merge_record"]["state"] == "merged"
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


async def test_owner_http_remote_action_requires_capability_and_retains_original_queued_request(
    remote_request,
):
    """Actual owner/CSRF/strict HTTP only admits a configured remote capability; held scheduling proves durable identity without claiming remote execution."""
    from dataclasses import asdict
    from types import SimpleNamespace

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, _candidate, _records, request = remote_request
    runtime = coordinator(
        s, SimpleNamespace(supported_task_types=("research", "code", "bug_fix"))
    )

    async def held(run):
        """Hold actual owner admission queued; synthetic fixture Git cannot become a production transport."""
        return run

    runtime._schedule = held
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    body = {"stage": "push", **asdict(request)}
    body.pop("origin_run_id")
    path = f"/api/projects/101/runs/{request.origin_run_id}/remote-publications"
    async with app.router.lifespan_context(app), owner_client(app) as client:
        assert (await client.post(path, json=body)).status_code == 409
        runtime.runtime.publish_remote = True
        assert (
            await client.post(path, json={**body, "actor_id": "client"})
        ).status_code == 422
        assert (
            await client.post(path, json=body, headers={"X-Researcher-CSRF": "invalid"})
        ).status_code == 403
        response = await client.post(path, json=body)
        assert response.status_code == 202, response.text
        packet = response.json()
        repeated = await client.post(path, json=body)
        assert (
            repeated.status_code == 202
            and repeated.json()["run"]["run_id"] == packet["run"]["run_id"]
        )
        assert packet["request"]["effects"] == []
        detail = await client.get(
            "/api/projects/101/remote-publications/" + packet["run"]["run_id"]
        )
        assert (
            detail.status_code == 200
            and detail.json()["protocol"]["operation_key"] == packet["run"]["run_id"]
        )
        assert (
            s.c.conn.execute(
                "SELECT count(*)FROM runtime_remote_publications"
            ).fetchone()[0]
            == 1
        )


async def test_runtime_scheduler_routes_remote_work_without_model_dispatch(
    remote_request,
):
    """Actual RuntimeService claims and journals remote stages; its controlled transport supplies explicitly synthetic closure, not physical Git/network evidence."""
    from types import SimpleNamespace

    from backend.runtime.remote_runtime import RemotePublications
    from backend.tests.runtime.test_runtime_service import coordinator

    s, _candidate, records, request = remote_request
    calls = []

    async def publish(peers, *, active):
        """Exercise real original stage transitions over a controlled host transport, with no subprocess or network fallback."""
        store = RemotePublications(peers.registry.runs)
        lease = peers.lease
        assert active() and peers.ids == {}
        peer = peers.registry.prepare(lease, "command")
        peers.registry.close(peer)
        reservation = store.issue(lease, "push")
        assert reservation["dispatch"]
        calls.append(reservation["operation_id"])
        store.observe(
            lease, "push", positive_push(store, lease.run_id), client_closed=True
        )
        return None, {
            "domain_closed": True,
            "grant_id": "synthetic-scheduler-transport",
        }

    transport = SimpleNamespace(
        supported_task_types=("research", "code", "bug_fix"),
        publish_remote=publish,
        consume_closure=lambda _lease: True,
    )
    runtime = coordinator(s, transport)
    before = s.c.conn.execute(
        "SELECT count(*)FROM runtime_inference_dispatches"
    ).fetchone()[0]
    async with runtime:
        run = await runtime.publish_remote(101, request)
        await runtime.wait(run.run_id)
        assert s.c.store.get(101, run.run_id).status == "accepted"
        assert (await runtime.publish_remote(101, request)).run_id == run.run_id
    assert (
        len(calls) == 1
        and records.request(101, run.run_id)["result"]["effects"]["push"]["state"]
        == "published"
    )
    assert (
        s.c.conn.execute("SELECT count(*)FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == before
    )
