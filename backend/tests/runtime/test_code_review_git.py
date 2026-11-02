"""Actual Git validation of readonly review candidates; original ownership is exercised by separate broker tests."""

from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_code_candidate import (
    candidate_copy as candidate_copy,  # noqa: PLC0414 -- register actual capture fixture.
)
from backend.tests.runtime.test_code_candidate_state import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- review_state dependency.
)
from backend.tests.runtime.test_code_review_state import (
    readonly_review_broker as readonly_review_broker,  # noqa: PLC0414 -- actual readonly review gate fixture.
)
from backend.tests.runtime.test_code_review_state import (
    review_state as review_state,  # noqa: PLC0414 -- readonly_review_broker dependency.
)
from backend.tests.runtime.test_development_state import (
    development_state as development_state,  # noqa: PLC0414 -- candidate_state dependency.
)
from backend.tests.runtime.test_development_workspace import (
    RealGitExecutor,
)
from backend.tests.runtime.test_development_workspace import (
    source_repository as source_repository,  # noqa: PLC0414 -- candidate_copy dependency.
)


@pytest.fixture
async def review_git(candidate_copy):
    """Capture actual edited bytes and retain their full base/head/tree/diff identity for validation."""
    from backend.runtime.code_candidate import capture_candidate

    _source, binding, prepared, root = candidate_copy
    (Path(prepared.workspace) / "value.py").write_text("VALUE = 200\n")
    captured = await capture_candidate(
        binding, prepared, root / "candidate", executor=RealGitExecutor()
    )
    return captured


async def test_review_git_witness_matches_full_captured_identity(review_git):
    """The witness comes from complete closed Git observations and includes actual normalized binary diff identity."""
    from backend.runtime.code_review_git import validate_review_candidate

    observed = await validate_review_candidate(review_git, executor=RealGitExecutor())
    assert (observed.head_sha, observed.tree_sha, observed.diff_sha256) == (
        review_git.head_sha,
        review_git.tree_sha,
        review_git.diff_sha256,
    )


async def test_review_git_allows_only_reserved_root_ken_index(review_git):
    """Published Ken creates its reserved root index after preflight; those host-managed bytes are outside the captured code tree."""
    from backend.runtime.code_review_git import validate_review_candidate

    state = Path(review_git.workspace) / ".ken"
    state.mkdir()
    (state / "ken.db").write_bytes(b"synthetic published-index shape")
    (state / "search-context").write_text("reviewer observation")
    observed = await validate_review_candidate(review_git, executor=RealGitExecutor())
    assert observed.tree_sha == review_git.tree_sha


@pytest.mark.parametrize("path", ["nested/.ken/source.py", ".ken-extra/source.py"])
async def test_review_git_metadata_exception_never_hides_other_source(review_git, path):
    """Only the reserved root index is metadata; similar names elsewhere remain real untracked changes."""
    from backend.runtime.code_review_git import validate_review_candidate
    from backend.runtime.contracts import RunConflict

    changed = Path(review_git.workspace) / path
    changed.parent.mkdir(parents=True)
    changed.write_text("UNREVIEWED = True\n")
    with pytest.raises(RunConflict):
        await validate_review_candidate(review_git, executor=RealGitExecutor())


async def test_review_git_rejects_indexed_reserved_ken_state(review_git):
    """A root metadata exception must not conceal a tracked or staged Ken path in candidate Git metadata."""
    from backend.runtime.code_review_git import validate_review_candidate
    from backend.runtime.contracts import RunConflict
    from backend.tests.runtime.test_development_workspace import fixture_git

    state = Path(review_git.workspace) / ".ken"
    state.mkdir()
    (state / "ken.db").write_bytes(b"not a valid captured source tree")
    await fixture_git(Path(review_git.workspace), "add", ".ken")
    with pytest.raises(RunConflict):
        await validate_review_candidate(review_git, executor=RealGitExecutor())


@pytest.mark.parametrize(
    "fault", ["head", "tree", "diff", "tracked_edit", "untracked_edit"]
)
async def test_review_git_rejects_another_version_or_changed_working_bytes(
    review_git, fault
):
    """A readonly subject name cannot disguise different actual Git metadata or working files."""
    from backend.runtime.code_review_git import validate_review_candidate
    from backend.runtime.contracts import RunConflict

    candidate = review_git
    if fault in ("head", "tree"):
        candidate = replace(candidate, **{fault + "_sha": "e" * 40})
    elif fault == "diff":
        candidate = replace(candidate, diff_sha256="e" * 64)
    elif fault == "tracked_edit":
        (Path(candidate.workspace) / "value.py").write_text("VALUE = 999\n")
    else:
        (Path(candidate.workspace) / "untracked.py").write_text("VALUE = 999\n")
    with pytest.raises(RunConflict):
        await validate_review_candidate(candidate, executor=RealGitExecutor())


async def test_owned_review_git_uses_readonly_candidate_not_original_source(
    readonly_review_broker,
):
    """The actual original broker executes pinned Git over candidate bytes and retains physically closed operation receipts."""
    import hashlib

    from backend.runtime.broker_git import OwnedGitExecutor
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.development_workspace import git_environment
    from backend.runtime.git_capsule import GitAsset
    from backend.runtime.workspaces import PEER_WORKSPACE

    state, lease, registry, broker, storage = readonly_review_broker
    _s, _author, candidate, _reviews = state
    asset = GitAsset.inspect(Path("/usr/bin/git"))
    async with AsyncPeerBroker(broker) as owner:
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=candidate["workspace"],
            allocation=None,
            asset=asset,
        )
        path = executor.execution_path(Path(candidate["workspace"]) / "fact.txt")
        assert path == PEER_WORKSPACE / "fact.txt"
        result = await executor.run(
            (asset.path, "hash-object", "--", str(path)),
            cwd=PEER_WORKSPACE,
            env=git_environment(Path("/home/actor")),
            timeout=5,
        )
        expected = hashlib.sha1(b"blob 13\0candidate-200").hexdigest()
        assert result.stdout.decode().strip() == expected
        assert result.local_execution_closed and executor.receipts
        for operation in executor.operations:
            assert (
                storage.load().records["broker:op:" + operation]["execution_closed"]
                is True
            )


def test_review_git_profile_never_grants_a_writable_allocation(readonly_review_broker):
    """Admitting readonly review Git must preserve rejection of an extra writable host view, even through the raw broker API."""
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.development_workspace import git_environment
    from backend.runtime.git_capsule import GitAsset, GitLaunch, PrivateAllocation
    from backend.runtime.workspaces import PEER_WORKSPACE

    state, lease, registry, broker, _storage = readonly_review_broker
    _s, _author, candidate, _reviews = state
    extra = Path(candidate["workspace"]).parent / "extra-write"
    extra.mkdir(mode=0o700)
    launch = GitLaunch(
        GitAsset.inspect(Path("/usr/bin/git")),
        ("--version",),
        str(PEER_WORKSPACE),
        tuple(sorted(git_environment(Path("/home/actor")).items())),
        PrivateAllocation.capture(extra),
    )
    peer = registry.prepare(lease, "command")
    with pytest.raises(AuthorityConflict):
        broker.run_git(
            registry, peer, operation_key="review-extra-write", launch=launch
        )
    registry.close(peer)
