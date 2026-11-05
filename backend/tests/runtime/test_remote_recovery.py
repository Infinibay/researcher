"""Fresh remote recovery storage with explicitly synthetic physical witnesses; real HTTPS/broker coverage lives in the owned transport integration."""

import pytest

from backend.tests.runtime.test_remote_runtime import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_remote_runtime import (
    claim_remote,
    positive_push,
)
from backend.tests.runtime.test_remote_runtime import (
    code_result as code_result,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_remote_runtime import (
    development_state as development_state,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_remote_runtime import (
    publication_request as publication_request,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_remote_runtime import (
    remote_request as remote_request,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_remote_runtime import (
    review_records as review_records,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_remote_runtime import (
    review_state as review_state,  # noqa: PLC0414 -- register original fixture dependency.
)

pytestmark = pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)


def uncertain_original(remote_request):
    """Create original issued push and genuinely closed host HTTP scope, with synthetic Git peers for storage-only assertions."""
    from backend.runtime.remote_clients import RemoteHTTPClients

    s, _candidate, records, request = remote_request
    run, _ = records.admit_once(101, request)
    lease, peers = claim_remote(s, records, run)
    clients = RemoteHTTPClients(s.c.store)
    clients.open(lease)
    records.issue(lease, "push")
    clients.close(lease)
    records.interrupted(lease, physically_closed=True, reason="SyntheticReplyLost")
    proof = {
        "attempt_id": lease.attempt_id,
        "fence": lease.fence,
        "database_identity": peers.registry._database_identity(),
        "execution_closed": True,
        "http_client_closed": True,
        "grant_ids": ["synthetic-original-domain"],
        **clients.closure(101, run.run_id, lease.attempt_id),
    }
    return s, records, run, lease, proof


def test_remote_http_scope_cannot_be_inferred_closed_from_done_peers(remote_request):
    """A live host client blocks recovery until actual controller closure is durably recorded."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.remote_clients import RemoteHTTPClients

    s, _, records, request = remote_request
    run, _ = records.admit_once(101, request)
    lease, _ = claim_remote(s, records, run)
    clients = RemoteHTTPClients(s.c.store)
    clients.open(lease)
    with pytest.raises(RunConflict, match="HTTP"):
        clients.closure(101, run.run_id, lease.attempt_id)
    clients.close(lease)
    assert clients.closure(101, run.run_id, lease.attempt_id)["http_client_closed"]


@pytest.mark.parametrize("positive", [True, False])
def test_fresh_remote_observer_recovers_history_without_write_or_absence_claim(
    remote_request, positive
):
    """Readonly recovery works after correction, never issues another effect and retains absence as uncertain with an immutable original command receipt."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.remote_publication import RemotePushObservation
    from backend.runtime.remote_recovery import RemoteRecovery

    s, records, run, original, proof = uncertain_original(remote_request)
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=original.context_version,
        operation_key="correct-before-remote-observation",
        statement="Changed requirement",
        source_kind="user_message",
        source_reference="owner",
    )
    current = s.c.store.get(101, run.run_id)
    command = {
        "project_id": 101,
        "run_id": run.run_id,
        "attempt_id": original.attempt_id,
        "expected_fence": current.fence,
        "operation_key": "observe-remote-original",
    }
    recovery = RemoteRecovery(s.c.store)
    lease, peers = recovery.begin(**command, proof=proof, owner_id="readonly-host")
    assert lease.attempt_id != original.attempt_id
    assert s.c.store.heartbeat(lease).attempt_id == lease.attempt_id
    peer = peers.registry.prepare(lease, "command")
    admission = peers.registry.admission(peer)
    assert admission["remote_observation"] is True
    with pytest.raises(RunConflict):
        records.issue(lease, "push")
    with pytest.raises(RunConflict):
        peers.registry.prepare(lease, "native")
    peers.registry.close(peer)
    intent = records.protocol(101, run.run_id)
    observed = (
        positive_push(records, run.run_id)
        if positive
        else RemotePushObservation(
            "uncertain",
            False,
            None,
            None,
            intent.head_sha,
            intent.receipt_ref,
            intent.remote.repository_id,
        )
    )
    result = recovery.complete(
        lease,
        {"push": observed},
        {
            "domain_closed": True,
            "http_client_closed": True,
            "grant_id": "synthetic-observer",
        },
    )
    assert result["effects_confirmed"] is positive
    assert result["completed_after_withdrawal"] is True
    assert result["observations"]["push"]["state"] == (
        "published" if positive else "uncertain"
    )
    assert s.c.store.get(101, run.run_id).status == (
        "superseded" if positive else "reconciling"
    )
    assert recovery.receipt(**command) == result
    assert len(records.request(101, run.run_id)["effects"]) == 1
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_remote_observer_rejects_missing_http_closure(remote_request):
    """Matching SQLite peers and a Git proof cannot stand in for original HTTP closure."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.remote_recovery import RemoteRecovery

    s, _, run, original, proof = uncertain_original(remote_request)
    with pytest.raises(RunConflict):
        RemoteRecovery(s.c.store).begin(
            project_id=101,
            run_id=run.run_id,
            attempt_id=original.attempt_id,
            expected_fence=original.fence,
            operation_key="bad-http-proof",
            owner_id="observer",
            proof={**proof, "http_client_closed": False},
        )


def test_remote_observer_launch_cannot_be_constructed_for_the_original_push(
    remote_request,
):
    """Even a trusted caller holding the full original intent cannot place its push argv in the readonly Git capability."""
    from backend.runtime.code_publications import CodePublications
    from backend.runtime.development_workspace import _POLICY, git_environment
    from backend.runtime.git_capsule import GitAsset
    from backend.runtime.remote_capsule import _EXTRA, RemoteObservationLaunch
    from backend.runtime.workspaces import PEER_WORKSPACE

    _, records, run, _, _ = uncertain_original(remote_request)
    intent = records.protocol(101, run.run_id)
    packet = CodePublications(records.runs).request(
        101, records.request(101, run.run_id)["local_publication_run_id"]
    )
    view = CodePublications._view(packet["view"])
    with pytest.raises(ValueError, match="Readonly"):
        RemoteObservationLaunch(
            GitAsset.inspect("/usr/bin/git"),
            (*_POLICY, *_EXTRA, *intent.push_arguments),
            str(PEER_WORKSPACE),
            tuple(sorted(git_environment("/home/actor").items())),
            view,
            intent=intent,
            transport_identity="a" * 64,
        )


async def test_owner_http_remote_recovery_retains_command_and_never_reschedules(
    remote_request,
):
    """Paired/CSRF strict owner recovery returns the same durable receipt after response loss, with explicitly synthetic physical transport here."""
    from types import SimpleNamespace

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import coordinator
    from backend.tests.runtime.test_workspace_delivery import owner_client

    s, records, run, original, proof = uncertain_original(remote_request)
    calls = []

    async def observe(peers, *, active):
        """Supply original typed evidence under an explicitly synthetic observer closure, not network/Git provenance."""
        calls.append(peers.lease.attempt_id)
        peer = peers.registry.prepare(peers.lease, "command")
        peers.registry.close(peer)
        return {"push": positive_push(records, run.run_id)}, {
            "domain_closed": True,
            "http_client_closed": True,
            "grant_id": "synthetic-observer",
        }

    native = SimpleNamespace(
        supported_task_types=("code", "bug_fix", "research"),
        supports_remote_publication=True,
        close_remote_publication=lambda *args: proof,
        observe_remote_publication=observe,
        consume_closure=lambda lease: True,
    )
    runtime = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"),
        runtime_service=runtime,
    )
    body = {
        "attempt_id": original.attempt_id,
        "expected_fence": original.fence,
        "operation_key": "owner-readonly-remote",
    }
    path = f"/api/projects/101/remote-publications/{run.run_id}/recovery"
    async with app.router.lifespan_context(app), owner_client(app) as client:
        assert (
            await client.post(path, json=body, headers={"X-Researcher-CSRF": "invalid"})
        ).status_code == 403
        assert (
            await client.post(path, json={**body, "proof": proof})
        ).status_code == 422
        response = await client.post(path, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["effects_confirmed"]
        assert (await client.post(path, json=body)).json() == response.json()
        assert len(calls) == 1
