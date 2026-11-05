"""Real temporary Git remotes exercise exact push/receipt semantics; trusted fixture subprocesses do not prove production ownership or HTTPS transport."""

from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_development_workspace import fixture_git
from backend.tests.runtime.test_publication_git import ActualPublicationGit
from backend.tests.runtime.test_publication_git import (
    publication_git as publication_git,  # noqa: PLC0414 -- actual independent source/candidate fixture.
)


class RemoteFixtureGit(ActualPublicationGit):
    """Translate only the fixture's exact pinned HTTPS clone URL to its actual bare remote, keeping the production protocol arguments intact."""

    def __init__(self, remote, repo):
        """Keep fixture routing and actual push count outside production code."""
        super().__init__()
        self.remote, self.url, self.pushes = remote, repo.clone_url, 0
        self.repo = repo
        self.lose_push_response = False

    async def verify_remote(self, remote):
        """Supply explicit fixture repository identity; actual HTTP identity validation is tested separately."""
        return self.repo

    async def run(self, command, *, cwd, env, timeout):
        """Own real test processes and inject response loss only after actual successful remote push."""
        command = tuple(str(self.remote) if arg == self.url else arg for arg in command)
        pushing = "push" in command
        if pushing:
            self.pushes += 1
        result = await super().run(command, cwd=cwd, env=env, timeout=timeout)
        if pushing and self.lose_push_response and result.exit_code == 0:
            raise TimeoutError("Fixture reply lost after actual atomic remote push")
        return result


@pytest.fixture
async def remote_git(publication_git, tmp_path):
    """Make the exact accepted commit available locally and an actual independent bare destination, without granting product authority."""
    from backend.runtime.remote_publication import RemotePushIntent, RemoteRepository

    view = publication_git.view
    remote = tmp_path / "remote.git"
    await fixture_git(Path(view.source.workspace), "init", "--bare", "-q", str(remote))
    await fixture_git(
        Path(view.source.workspace),
        "fetch",
        "-q",
        "--no-write-fetch-head",
        view.workspace,
        view.head_sha,
    )
    repo = RemoteRepository(
        "https://forgejo.example/api/v1",
        71,
        "owner/repo",
        "https://forgejo.example/owner/repo.git",
    )
    intent = RemotePushIntent(
        "remote-operation",
        repo,
        "refs/heads/reviewed-change",
        None,
        view.head_sha,
        view.base_sha,
    )
    return view, intent, RemoteFixtureGit(remote, repo)


async def test_exact_remote_push_and_receipt_are_atomic_and_source_stays_unchanged(
    remote_git,
):
    """A real remote receives the exact candidate and original receipt together while source main/files/index remain untouched."""
    from backend.runtime.remote_publication import push_candidate_remote

    view, intent, git = remote_git
    before = await fixture_git(Path(view.source.workspace), "rev-parse", "HEAD")
    result = await push_candidate_remote(view, intent, executor=git)
    assert result.state == "published" and result.target_current
    assert (
        await fixture_git(git.remote, "rev-parse", intent.target_ref)
    ).decode().strip() == view.head_sha
    assert (
        await fixture_git(git.remote, "rev-parse", intent.receipt_ref)
    ).decode().strip() == view.head_sha
    assert await fixture_git(Path(view.source.workspace), "rev-parse", "HEAD") == before
    assert (Path(view.source.workspace) / "value.txt").read_text() == "137\n"
    assert git.pushes == 1


async def test_lost_remote_push_response_reconciles_only_positive_receipt_without_another_push(
    remote_git,
):
    """Actual remote commit survives a lost reply and a subsequently moved destination; read-only recovery preserves applied history."""
    from backend.runtime.remote_publication import (
        RemoteEffectUncertain,
        push_candidate_remote,
        reconcile_remote_push,
    )

    view, intent, git = remote_git
    git.lose_push_response = True
    with pytest.raises(RemoteEffectUncertain):
        await push_candidate_remote(view, intent, executor=git)
    await fixture_git(git.remote, "update-ref", intent.target_ref, view.base_sha)
    result = await reconcile_remote_push(
        view, intent, executor=git, original_client_closed=True
    )
    assert result.state == "published" and not result.target_current
    assert result.observed_target_sha == view.base_sha and git.pushes == 1


async def test_remote_marker_absence_after_local_client_closure_is_still_uncertain(
    remote_git,
):
    """A remote server may still finish after client disconnect; an absent ref never proves that an issued remote write cannot apply later."""
    from backend.runtime.remote_publication import reconcile_remote_push

    view, intent, git = remote_git
    result = await reconcile_remote_push(
        view, intent, executor=git, original_client_closed=True
    )
    assert result.state == "uncertain" and not result.target_current and git.pushes == 0


async def test_remote_target_cas_refuses_a_moved_branch_without_creating_marker(
    remote_git,
):
    """The exact observed destination is a real receive-pack precondition, not a read-then-unconditional write."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.remote_publication import push_candidate_remote

    view, intent, git = remote_git
    await fixture_git(git.remote, "fetch", "-q", view.source.workspace, view.base_sha)
    await fixture_git(git.remote, "update-ref", intent.target_ref, view.base_sha)
    with pytest.raises(RunConflict):
        await push_candidate_remote(view, intent, executor=git)
    assert (await fixture_git(git.remote, "for-each-ref", intent.receipt_ref)) == b""
    assert git.pushes == 0


def test_remote_intent_binds_repository_id_and_complete_observed_target():
    """A recreated remote or different target observation must have a different immutable receipt namespace."""
    from backend.runtime.remote_publication import RemotePushIntent, RemoteRepository

    repo = RemoteRepository(
        "https://forgejo.example/api/v1",
        71,
        "owner/repo",
        "https://forgejo.example/owner/repo.git",
    )
    intent = RemotePushIntent(
        "operation", repo, "refs/heads/change", None, "a" * 40, "b" * 40
    )
    assert (
        replace(intent, remote=replace(repo, repository_id=72)).receipt_ref
        != intent.receipt_ref
    )
    assert (
        replace(intent, expected_target_sha="b" * 40).receipt_ref != intent.receipt_ref
    )
    with pytest.raises(ValueError):
        replace(repo, clone_url="https://another.example/owner/repo.git")


async def test_receive_pack_cas_rejects_a_race_after_preflight_without_partial_receipt(
    remote_git, monkeypatch
):
    """A destination created after preflight rejects the real atomic receive-pack transaction, leaving no orphan success marker."""
    from backend.runtime.remote_publication import (
        RemoteEffectUncertain,
        push_candidate_remote,
    )

    view, intent, git = remote_git
    await fixture_git(git.remote, "fetch", "-q", view.source.workspace, view.base_sha)
    actual = git.run

    async def race(command, **kwargs):
        """Move the actual destination only at the write boundary, after the policy already observed it absent."""
        if "push" in command:
            await fixture_git(
                git.remote, "update-ref", intent.target_ref, view.base_sha
            )
        return await actual(command, **kwargs)

    monkeypatch.setattr(git, "run", race)
    with pytest.raises(RemoteEffectUncertain):
        await push_candidate_remote(view, intent, executor=git)
    assert git.pushes == 1
    assert (
        await fixture_git(git.remote, "rev-parse", intent.target_ref)
    ).decode().strip() == view.base_sha
    assert await fixture_git(git.remote, "for-each-ref", intent.receipt_ref) == b""


async def test_fast_forward_merge_uses_exact_accepted_head_and_base_cas(remote_git):
    """The remote base advances only from its exact accepted base to the reviewed candidate, without manufacturing or accepting another merge commit."""
    from backend.runtime.remote_publication import push_candidate_remote

    view, intent, git = remote_git
    await fixture_git(git.remote, "fetch", "-q", view.source.workspace, view.base_sha)
    await fixture_git(git.remote, "update-ref", "refs/heads/main", view.base_sha)
    merge = replace(
        intent,
        operation_key="merge-exact-candidate",
        target_ref="refs/heads/main",
        expected_target_sha=view.base_sha,
    )
    result = await push_candidate_remote(view, merge, executor=git)
    assert result.state == "published" and result.target_current
    assert (
        await fixture_git(git.remote, "rev-parse", "refs/heads/main")
    ).decode().strip() == view.head_sha


async def test_exact_merge_refuses_an_unrelated_history_even_with_matching_files_and_base_lease(
    remote_git,
):
    """Exact ref leases must not turn a claimed fast-forward into a history rewrite; ancestry is a separate required Git fact."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.remote_publication import push_candidate_remote

    view, intent, git = remote_git
    candidate = Path(view.workspace)
    await fixture_git(candidate, "checkout", "--orphan", "unrelated")
    await fixture_git(
        candidate, "commit", "-qm", "Unrelated history with the same files"
    )
    unrelated = (await fixture_git(candidate, "rev-parse", "HEAD")).decode().strip()
    await fixture_git(
        Path(view.source.workspace),
        "fetch",
        "-q",
        "--no-write-fetch-head",
        str(candidate),
        unrelated,
    )
    await fixture_git(git.remote, "fetch", "-q", view.source.workspace, view.base_sha)
    await fixture_git(git.remote, "update-ref", "refs/heads/main", view.base_sha)
    view = replace(view, head_sha=unrelated)
    intent = replace(
        intent,
        head_sha=unrelated,
        target_ref="refs/heads/main",
        expected_target_sha=view.base_sha,
    )
    with pytest.raises(RunConflict):
        await push_candidate_remote(view, intent, executor=git)
    assert git.pushes == 0
