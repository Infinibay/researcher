"""Exact Git publication policy with real local refs; executor authority/broker integration is a separate obligation."""

import asyncio
import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.runtime.development_workspace import GitResult
from backend.tests.runtime.test_development_workspace import fixture_git


class ActualPublicationGit:
    """Test-only real Git port; production must supply its freshly owned broker instead of this subprocess adapter."""

    git_binary = Path("/usr/bin/git")

    def __init__(self):
        """Retain actual transaction count and optional post-commit transport loss."""
        self.transactions = 0
        self.lose_response = False

    def execution_path(self, path):
        """Use fixture paths directly; no claim of a production mount or effect grant."""
        return Path(path)

    async def run(self, command, *, cwd, env, timeout):
        """Collect complete real local Git output within the policy deadline."""
        return await self._execute(command, cwd, env, timeout, None)

    async def transact(self, command, *, cwd, env, timeout, input_text):
        """Execute the actual ref transaction once and optionally lose its completed response."""
        self.transactions += 1
        result = await self._execute(
            command, cwd, env, timeout, input_text.encode("ascii")
        )
        if self.lose_response and result.exit_code == 0:
            raise TimeoutError("Controlled response loss after actual Git commit")
        return result

    async def _execute(self, command, cwd, env, timeout, data):
        """Own and drain this fixture process; uncertain test shutdown still kills and joins it."""
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE
            if data is not None
            else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            output, _error = await asyncio.wait_for(process.communicate(data), timeout)
            return GitResult(output, process.returncode, True, True)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.fixture
async def publication_git(tmp_path):
    """Capture an actual accepted-version-shaped fixture with independent source and clean candidate checkout; no acceptance authority is simulated."""
    from backend.runtime.contracts import WorkspaceBinding
    from backend.runtime.publication_git import PublicationDirectory, PublicationView

    source = tmp_path / "source"
    source.mkdir()
    await fixture_git(source, "init", "-q", "--initial-branch=main")
    await fixture_git(source, "config", "user.name", "Fixture")
    await fixture_git(source, "config", "user.email", "fixture@localhost")
    (source / "value.txt").write_text("137\n")
    await fixture_git(source, "add", "value.txt")
    await fixture_git(source, "commit", "-qm", "base")
    base = (await fixture_git(source, "rev-parse", "HEAD")).decode().strip()
    candidate = tmp_path / "candidate"
    await fixture_git(
        source, "clone", "-q", "--no-hardlinks", str(source), str(candidate)
    )
    await fixture_git(candidate, "config", "user.name", "Fixture")
    await fixture_git(candidate, "config", "user.email", "fixture@localhost")
    (candidate / "value.txt").write_text("200\n")
    await fixture_git(candidate, "commit", "-qam", "candidate")
    head = (await fixture_git(candidate, "rev-parse", "HEAD")).decode().strip()
    tree = (await fixture_git(candidate, "rev-parse", "HEAD^{tree}")).decode().strip()
    diff = await fixture_git(
        candidate,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-renames",
        base,
        head,
        "--",
    )
    info, original = candidate.stat(), source.stat()
    binding = WorkspaceBinding(
        11, "source", str(source), str(source), original.st_dev, original.st_ino, 11
    )
    view = PublicationView(
        binding,
        str(candidate),
        info.st_dev,
        info.st_ino,
        head,
        tree,
        "a" * 64,
        base,
        hashlib.sha256(diff).hexdigest(),
        PublicationDirectory.capture(source / ".git"),
        PublicationDirectory.capture(candidate / ".git"),
    )
    return SimpleNamespace(
        source=source,
        candidate=candidate,
        view=view,
        executor=ActualPublicationGit(),
        base=base,
        head=head,
    )


@pytest.mark.parametrize(
    "ref",
    [
        "main",
        "refs/tags/release",
        "refs/heads/../main",
        "refs/heads/a..b",
        "refs/heads/a.lock",
        "refs/heads/a\nb",
        "refs/heads/-x",
        "refs/heads/a@{b}",
    ],
)
def test_publication_ref_intent_rejects_ambiguous_or_non_branch_destinations(ref):
    """A ref command cannot smuggle another transaction, namespace or implicit destination."""
    from backend.runtime.publication_git import PublicationRefIntent

    with pytest.raises(ValueError):
        PublicationRefIntent("pub-1", ref, None)


async def test_actual_ref_publication_is_exact_atomic_and_leaves_checkout_unchanged(
    publication_git,
):
    """Only the accepted candidate head and stable marker enter the source; its checked-out branch/files remain at the original base."""
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        publish_candidate_ref,
    )

    s = publication_git
    intent = PublicationRefIntent("pub-1", "refs/heads/reviewed-change", None)
    result = await publish_candidate_ref(s.view, intent, executor=s.executor)
    assert result.state == "published" and result.target_current
    assert s.executor.transactions == 1
    assert (
        await fixture_git(s.source, "rev-parse", intent.target_ref)
    ).decode().strip() == s.head
    assert (
        await fixture_git(s.source, "rev-parse", intent.receipt_ref)
    ).decode().strip() == s.head
    assert (await fixture_git(s.source, "rev-parse", "HEAD")).decode().strip() == s.base
    assert (s.source / "value.txt").read_text() == "137\n"
    assert await fixture_git(s.source, "status", "--porcelain") == b""


async def test_lost_transaction_response_reconciles_without_replaying_effect(
    publication_git,
):
    """A physically closed original transaction is recovered by its atomic marker, even after the branch subsequently moves."""
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        PublicationUncertain,
        publish_candidate_ref,
        reconcile_candidate_ref,
    )

    s = publication_git
    intent = PublicationRefIntent("pub-lost", "refs/heads/reviewed-change", None)
    s.executor.lose_response = True
    with pytest.raises(PublicationUncertain):
        await publish_candidate_ref(s.view, intent, executor=s.executor)
    with pytest.raises(ValueError, match="closure"):
        await reconcile_candidate_ref(
            s.view, intent, executor=s.executor, original_execution_closed=False
        )
    observed = await reconcile_candidate_ref(
        s.view, intent, executor=s.executor, original_execution_closed=True
    )
    assert observed.state == "published" and observed.target_current
    await fixture_git(s.source, "update-ref", intent.target_ref, s.base, s.head)
    historical = await reconcile_candidate_ref(
        s.view, intent, executor=s.executor, original_execution_closed=True
    )
    assert historical.state == "published" and not historical.target_current
    assert historical.observed_target_sha == s.base
    assert s.executor.transactions == 1


async def test_checked_out_or_stale_target_cannot_be_published(publication_git):
    """Publishing cannot update a checked-out branch or silently replace a different observed destination."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        publish_candidate_ref,
    )

    s = publication_git
    with pytest.raises(RunConflict, match="checked out"):
        await publish_candidate_ref(
            s.view,
            PublicationRefIntent("pub-main", "refs/heads/main", s.base),
            executor=s.executor,
        )
    with pytest.raises(RunConflict, match="destination"):
        await publish_candidate_ref(
            s.view,
            PublicationRefIntent("pub-stale", "refs/heads/absent", s.base),
            executor=s.executor,
        )
    assert s.executor.transactions == 0


async def test_changed_candidate_bytes_prevent_any_ref_transaction(publication_git):
    """A matching commit name does not excuse modified captured source."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        publish_candidate_ref,
    )

    s = publication_git
    (s.candidate / "value.txt").write_text("999\n")
    with pytest.raises(RunConflict, match="working bytes"):
        await publish_candidate_ref(
            s.view,
            PublicationRefIntent("pub-changed", "refs/heads/change", None),
            executor=s.executor,
        )
    assert s.executor.transactions == 0


async def test_post_commit_read_failure_remains_uncertain_instead_of_ordinary_failure(
    publication_git, monkeypatch
):
    """Losing observation after successful Git mutation must retain effect uncertainty just like a lost transaction response."""
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        PublicationUncertain,
        publish_candidate_ref,
        reconcile_candidate_ref,
    )

    s = publication_git
    original = s.executor.run

    async def lose_observation(*args, **kwargs):
        """Interrupt post-commit reads once while preserving the actual committed transaction."""
        if s.executor.transactions:
            raise OSError("Controlled post-commit read failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(s.executor, "run", lose_observation)
    intent = PublicationRefIntent("pub-observation", "refs/heads/reviewed-change", None)
    with pytest.raises(PublicationUncertain):
        await publish_candidate_ref(s.view, intent, executor=s.executor)
    monkeypatch.setattr(s.executor, "run", original)
    observed = await reconcile_candidate_ref(
        s.view, intent, executor=s.executor, original_execution_closed=True
    )
    assert observed.state == "published" and s.executor.transactions == 1


async def test_linked_checked_out_branch_is_rejected(publication_git, tmp_path):
    """Another checkout also forbids a local branch ref update, even when the primary source has another branch open."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        publish_candidate_ref,
    )

    s = publication_git
    await fixture_git(
        s.source,
        "worktree",
        "add",
        "-qb",
        "other-checkout",
        str(tmp_path / "other-checkout"),
        s.base,
    )
    with pytest.raises(RunConflict, match="checked out"):
        await publish_candidate_ref(
            s.view,
            PublicationRefIntent(
                "pub-other-checkout", "refs/heads/other-checkout", s.base
            ),
            executor=s.executor,
        )
    assert s.executor.transactions == 0


async def test_destination_race_cannot_commit_marker_or_wrong_target(
    publication_git, monkeypatch
):
    """Actual ref CAS fails atomically if another writer creates the branch after preflight; no partial publication marker appears."""
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        PublicationUncertain,
        publish_candidate_ref,
        reconcile_candidate_ref,
    )

    s = publication_git
    intent = PublicationRefIntent("pub-race", "refs/heads/reviewed-change", None)
    original = s.executor.transact

    async def move_destination(*args, **kwargs):
        """Create the actual conflicting ref immediately before Git processes the original transaction."""
        await fixture_git(s.source, "update-ref", intent.target_ref, s.base)
        return await original(*args, **kwargs)

    monkeypatch.setattr(s.executor, "transact", move_destination)
    with pytest.raises(PublicationUncertain):
        await publish_candidate_ref(s.view, intent, executor=s.executor)
    observed = await reconcile_candidate_ref(
        s.view, intent, executor=s.executor, original_execution_closed=True
    )
    assert observed.state == "uncertain" and observed.observed_marker_sha is None
    assert observed.observed_target_sha == s.base and s.executor.transactions == 1


async def test_replaced_metadata_cannot_supply_a_copied_publication_marker(
    publication_git,
):
    """A copied Git directory with identical refs has a different origin; it cannot impersonate the original effect receipt."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        publish_candidate_ref,
        reconcile_candidate_ref,
    )

    s = publication_git
    intent = PublicationRefIntent("pub-metadata", "refs/heads/reviewed-change", None)
    await publish_candidate_ref(s.view, intent, executor=s.executor)
    original = s.source / ".git.original"
    (s.source / ".git").rename(original)
    shutil.copytree(original, s.source / ".git")
    with pytest.raises(RunConflict, match="metadata.*identity"):
        await reconcile_candidate_ref(
            s.view, intent, executor=s.executor, original_execution_closed=True
        )


async def test_a_receipt_for_another_destination_cannot_be_adopted(publication_git):
    """Reusing a request label with a different destination is not evidence that the changed request published."""
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        publish_candidate_ref,
        reconcile_candidate_ref,
    )

    s = publication_git
    original = PublicationRefIntent("same-label", "refs/heads/original", None)
    await publish_candidate_ref(s.view, original, executor=s.executor)
    await fixture_git(s.source, "update-ref", "refs/heads/other", s.head)
    changed = PublicationRefIntent("same-label", "refs/heads/other", None)
    result = await reconcile_candidate_ref(
        s.view, changed, executor=s.executor, original_execution_closed=True
    )
    assert result.state == "uncertain" and not result.target_current
    assert original.receipt_ref != changed.receipt_ref


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_sha", "--output=elsewhere"),
        ("head_sha", "abc123"),
        ("diff_sha256", "not-a-digest"),
    ],
)
async def test_incomplete_candidate_identity_is_rejected_before_git(
    publication_git, field, value
):
    """Stored Git expressions and abbreviated names cannot enter fixed Git invocations as candidate identities."""
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(publication_git.view, **{field: value})


async def test_new_candidate_commit_cannot_reuse_the_previously_observed_publication_view(publication_git):
    """Reviewing commit A cannot publish clean committed B, even in the same unchanged directory identity."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_git import PublicationRefIntent, publish_candidate_ref

    s = publication_git
    (s.candidate/'value.txt').write_text('999\n')
    await fixture_git(s.candidate,'commit','-qam','Different committed B')
    new_head = (await fixture_git(s.candidate,'rev-parse','HEAD')).decode().strip()
    assert new_head != s.head and (await fixture_git(s.candidate,'status','--porcelain')) == b''
    intent = PublicationRefIntent('stale-A-approval','refs/heads/should-not-publish-B',None)
    with pytest.raises(RunConflict):
        await publish_candidate_ref(s.view,intent,executor=s.executor)
    assert s.executor.transactions == 0
    assert (await fixture_git(s.source,'for-each-ref','--format=%(objectname)',intent.target_ref,intent.receipt_ref)) == b''
    assert (await fixture_git(s.source,'rev-parse','HEAD')).decode().strip() == s.base
