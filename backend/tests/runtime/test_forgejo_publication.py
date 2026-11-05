"""Controlled Forgejo HTTP contract tests; no user server, token or real external effect is used."""

import json

import httpx
import pytest


def repository():
    """Return one exact configured remote identity with synthetic fixture credentials kept out of URLs and process arguments."""
    from backend.runtime.remote_publication import RemoteRepository

    return RemoteRepository(
        "https://forgejo.example/api/v1",
        71,
        "owner/repo",
        "https://forgejo.example/owner/repo.git",
    )


def pull_intent():
    """Freeze one original request independently of mutable remote branch names."""
    from backend.runtime.forgejo_publication import RemotePullIntent

    return RemotePullIntent(
        "create-pr",
        repository(),
        "refs/heads/reviewed-change",
        "refs/heads/main",
        "a" * 40,
        "b" * 40,
        "Reviewed change",
        "Original owner description",
    )


def pull(intent, *, head=None, base=None):
    """Build a controlled server PR response with complete repository/ref identity and an original body receipt."""
    return {
        "number": 8,
        "body": intent.marked_body,
        "head": {
            "ref": "reviewed-change",
            "sha": head or intent.head_sha,
            "repo": {"id": 71},
        },
        "base": {"ref": "main", "sha": base or intent.base_sha, "repo": {"id": 71}},
    }


async def test_remote_identity_uses_numeric_repo_id_and_never_follows_a_redirect():
    """A same-name recreated repo and redirect cannot silently adopt the accepted remote or forward its configured credential."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.forgejo_publication import (
        ForgejoPublicationClient,
        RemoteAPIError,
    )

    repo = repository()
    seen = []

    def server(request):
        """Expose only controlled identity responses while recording the actual authorization destination."""
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(
                200,
                json={
                    "id": 72,
                    "full_name": repo.full_name,
                    "clone_url": repo.clone_url,
                },
            )
        return httpx.Response(302, headers={"Location": "https://other.example/leak"})

    async with ForgejoPublicationClient(
        repo.api_base, "synthetic-fixture-token", transport=httpx.MockTransport(server)
    ) as client:
        with pytest.raises(RunConflict):
            await client.verify_remote(repo)
        with pytest.raises(RemoteAPIError):
            await client.verify_remote(repo)
    assert len(seen) == 2 and all(
        request.url.host == "forgejo.example" for request in seen
    )
    assert all(
        request.headers["Authorization"] == "token synthetic-fixture-token"
        for request in seen
    )


async def test_lost_pr_creation_response_recovers_original_marker_without_another_post():
    """A POST applies then loses its response; explicit readonly reconciliation finds the same PR and does not repeat the effect."""
    from backend.runtime.forgejo_publication import ForgejoPublicationClient
    from backend.runtime.remote_publication import RemoteEffectUncertain

    intent = pull_intent()
    created = []
    requests = []

    def server(request):
        """Use real HTTPX request/response framing with a controlled lost response after the simulated commit."""
        requests.append(request)
        path = request.url.path
        if path.endswith("/owner/repo"):
            return httpx.Response(
                200,
                json={
                    "id": 71,
                    "full_name": intent.remote.full_name,
                    "clone_url": intent.remote.clone_url,
                },
            )
        if "/branches/" in path:
            return httpx.Response(
                200,
                json={
                    "commit": {
                        "id": intent.base_sha
                        if path.endswith("/main")
                        else intent.head_sha
                    }
                },
            )
        if request.method == "GET":
            return httpx.Response(200, json=created)
        assert json.loads(request.content)["body"] == intent.marked_body
        created.append(pull(intent))
        raise httpx.ReadTimeout("Fixture response lost", request=request)

    async with ForgejoPublicationClient(
        intent.remote.api_base,
        "synthetic-fixture-token",
        transport=httpx.MockTransport(server),
    ) as client:
        with pytest.raises(RemoteEffectUncertain):
            await client.create_pull(intent)
        result = await client.reconcile_pull(intent, original_client_closed=True)
    assert result.state == "created" and result.number == 8 and result.candidate_current
    assert sum(request.method == "POST" for request in requests) == 1


async def test_absent_pr_after_closed_client_is_not_proof_that_server_did_not_create_it():
    """No returned object after timeout cannot justify another POST while the original server operation may still finish."""
    from backend.runtime.forgejo_publication import ForgejoPublicationClient

    intent = pull_intent()

    def server(request):
        """Return only identity and an empty list; a write would fail this readonly contract test."""
        assert request.method == "GET"
        if request.url.path.endswith("/owner/repo"):
            return httpx.Response(
                200,
                json={
                    "id": 71,
                    "full_name": intent.remote.full_name,
                    "clone_url": intent.remote.clone_url,
                },
            )
        return httpx.Response(200, json=[])

    async with ForgejoPublicationClient(
        intent.remote.api_base,
        "synthetic-fixture-token",
        transport=httpx.MockTransport(server),
    ) as client:
        result = await client.reconcile_pull(intent, original_client_closed=True)
    assert result.state == "uncertain" and result.number is None


async def test_existing_original_pr_remains_history_after_head_or_base_moves():
    """Original marker proves creation, while changed candidate/base remains visibly ineligible for exact-version acceptance."""
    from backend.runtime.forgejo_publication import ForgejoPublicationClient

    intent = pull_intent()

    def server(request):
        """Return an original PR whose current remote base no longer matches the owner-observed version."""
        assert request.method == "GET"
        if request.url.path.endswith("/owner/repo"):
            return httpx.Response(
                200,
                json={
                    "id": 71,
                    "full_name": intent.remote.full_name,
                    "clone_url": intent.remote.clone_url,
                },
            )
        return httpx.Response(200, json=[pull(intent, base="c" * 40)])

    async with ForgejoPublicationClient(
        intent.remote.api_base,
        "synthetic-fixture-token",
        transport=httpx.MockTransport(server),
    ) as client:
        result = await client.create_pull(intent)
    assert (
        result.state == "created"
        and not result.candidate_current
        and result.observed_base_sha == "c" * 40
    )


async def test_merge_receipt_records_only_an_exact_git_cas_and_recovers_lost_api_response():
    """Merge bookkeeping follows an already-proven exact Git ref CAS; losing the API reply never causes another Git push or merge POST."""
    from backend.runtime.forgejo_publication import ForgejoPublicationClient
    from backend.runtime.remote_publication import (
        RemoteEffectUncertain,
        RemotePushIntent,
        RemotePushObservation,
    )

    intent = pull_intent()
    target = RemotePushIntent(
        "merge-cas",
        intent.remote,
        intent.base_ref,
        intent.base_sha,
        intent.head_sha,
        intent.base_sha,
    )
    proof = RemotePushObservation(
        "published",
        True,
        intent.head_sha,
        intent.head_sha,
        intent.head_sha,
        target.receipt_ref,
        71,
    )
    record = pull(intent, base=intent.head_sha)
    record["merged"] = False
    posts = []

    def server(request):
        """Simulate an original successful manual-merge record whose response is lost after the server commit."""
        if request.url.path.endswith("/owner/repo"):
            return httpx.Response(
                200,
                json={
                    "id": 71,
                    "full_name": intent.remote.full_name,
                    "clone_url": intent.remote.clone_url,
                },
            )
        if "/branches/" in request.url.path:
            return httpx.Response(200, json={"commit": {"id": intent.head_sha}})
        if request.method == "GET":
            return httpx.Response(200, json=record)
        payload = json.loads(request.content)
        posts.append(payload)
        assert (
            payload["Do"] == "manually-merged"
            and payload["MergeCommitID"] == intent.head_sha
            and payload["head_commit_id"] == intent.head_sha
        )
        assert payload["force_merge"] is False
        record.update(merged=True, merge_commit_sha=intent.head_sha)
        raise httpx.ReadTimeout(
            "Fixture reply lost after merge bookkeeping", request=request
        )

    async with ForgejoPublicationClient(
        intent.remote.api_base,
        "synthetic-fixture-token",
        transport=httpx.MockTransport(server),
    ) as client:
        with pytest.raises(RemoteEffectUncertain):
            await client.record_exact_merge(intent, 8, target, proof)
        result = await client.reconcile_exact_merge(
            intent, 8, target, proof, original_client_closed=True
        )
    assert (
        result.state == "merged"
        and result.merge_sha == intent.head_sha
        and len(posts) == 1
    )


async def test_merge_recording_rejects_missing_original_ref_receipt_before_http_write():
    """A matching moving branch or PR label is insufficient: bookkeeping requires the original exact atomic target-update receipt."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.forgejo_publication import ForgejoPublicationClient
    from backend.runtime.remote_publication import (
        RemotePushIntent,
        RemotePushObservation,
    )

    intent = pull_intent()
    target = RemotePushIntent(
        "merge-cas",
        intent.remote,
        intent.base_ref,
        intent.base_sha,
        intent.head_sha,
        intent.base_sha,
    )
    proof = RemotePushObservation(
        "uncertain", False, None, None, intent.head_sha, target.receipt_ref, 71
    )

    def server(request):
        """Any HTTP request means the missing ref proof was not rejected at its capability boundary."""
        raise AssertionError("No request allowed for unproved original merge effect")

    async with ForgejoPublicationClient(
        intent.remote.api_base,
        "synthetic-fixture-token",
        transport=httpx.MockTransport(server),
    ) as client:
        with pytest.raises(RunConflict):
            await client.record_exact_merge(intent, 8, target, proof)
