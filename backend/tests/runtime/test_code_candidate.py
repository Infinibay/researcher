"""Capture exact Git candidates from private edits without trusting the author's index or changing source."""

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_development_workspace import (
    RealGitExecutor,
    fixture_git,
)
from backend.tests.runtime.test_development_workspace import (
    source_repository as source_repository,  # noqa: PLC0414 -- register the shared pytest fixture.
)


@pytest.fixture
async def candidate_copy(source_repository, tmp_path):
    """Prepare the real independent source copy used by candidate capture policy tests."""
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    prepared = await prepare_workspace(
        binding, root / "author", executor=RealGitExecutor()
    )
    return source, binding, prepared, root


async def test_candidate_captures_shell_edits_binary_rename_and_deletion(
    candidate_copy,
):
    """Tree and full binary diff include actual edits even when the author supplies no tool change tracker."""
    from backend.runtime.code_candidate import capture_candidate

    source, binding, prepared, root = candidate_copy
    author = Path(prepared.workspace)
    (author / "value.py").rename(author / "renamed.py")
    (author / "renamed.py").write_text('"""Updated fixture."""\nVALUE = 200\n')
    binary = bytes(range(256)) * 3
    (author / "image.bin").write_bytes(binary)
    (author / ".ken").mkdir()
    (author / ".ken/cache.txt").write_text(
        "Host-owned index cache is not product code."
    )
    head_before = await fixture_git(author, "rev-parse", "HEAD")
    captured = await capture_candidate(
        binding, prepared, root / "candidate", executor=RealGitExecutor()
    )
    snapshot = Path(captured.workspace)
    assert captured.repository_id == binding.repository_id
    assert captured.base_sha == prepared.base_sha
    assert captured.head_sha != captured.base_sha
    assert (
        captured.tree_sha
        == (await fixture_git(snapshot, "rev-parse", "HEAD^{tree}")).decode().strip()
    )
    assert captured.diff_sha256 == hashlib.sha256(captured.diff).hexdigest()
    assert b"GIT binary patch" in captured.diff and b"VALUE = 200" in captured.diff
    assert not (snapshot / "value.py").exists()
    assert (snapshot / "renamed.py").read_bytes() == (
        author / "renamed.py"
    ).read_bytes()
    assert (snapshot / "image.bin").read_bytes() == binary
    assert not (snapshot / ".ken").exists()
    assert (await fixture_git(snapshot, "status", "--porcelain")) == b""
    assert await fixture_git(author, "rev-parse", "HEAD") == head_before
    assert "137" in (source / "value.py").read_text()
    assert await fixture_git(source, "status", "--porcelain") == b""
    # Later private edits cannot silently replace the captured revision.
    (author / "renamed.py").write_text("VALUE = 999\n")
    assert b"200" in (snapshot / "renamed.py").read_bytes()
    assert (
        await fixture_git(snapshot, "rev-parse", "HEAD")
    ).decode().strip() == captured.head_sha


async def test_candidate_cannot_publish_files_in_reserved_legacy_worktree_storage(
    candidate_copy,
):
    """An authored candidate must not turn preserved legacy storage into tracked product code or hide it in a later base."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import RunConflict

    _source, binding, prepared, root = candidate_copy
    metadata = Path(prepared.workspace) / ".worktrees"
    metadata.mkdir()
    (metadata / "old-data").write_text("Preserved metadata is not authored code.")
    with pytest.raises(RunConflict, match="worktrees"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=RealGitExecutor()
        )
    assert (
        metadata / "old-data"
    ).read_text() == "Preserved metadata is not authored code."


async def test_candidate_ignores_author_git_config_index_and_model_commit(
    candidate_copy,
):
    """Author metadata cannot hide tracked edits, redirect the captured parent or execute a clean filter."""
    from backend.runtime.code_candidate import capture_candidate

    _, binding, prepared, root = candidate_copy
    author = Path(prepared.workspace)
    (author / "author-only.txt").write_text("Authored before capture.\n")
    await fixture_git(author, "add", "author-only.txt")
    await fixture_git(
        author,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "author commit",
    )
    await fixture_git(author, "update-index", "--assume-unchanged", "value.py")
    await fixture_git(author, "config", "filter.hostile.clean", "touch FILTER-EXECUTED")
    (author / ".gitattributes").write_text("*.py filter=hostile\n")
    (author / "value.py").write_text("VALUE = 200\n")
    assert not (author / "FILTER-EXECUTED").exists()
    captured = await capture_candidate(
        binding, prepared, root / "candidate", executor=RealGitExecutor()
    )
    snapshot = Path(captured.workspace)
    assert (snapshot / "value.py").read_text() == "VALUE = 200\n"
    assert (snapshot / "author-only.txt").read_text() == "Authored before capture.\n"
    assert (
        not (author / "FILTER-EXECUTED").exists()
        and not (snapshot / "FILTER-EXECUTED").exists()
    )
    assert (
        await fixture_git(snapshot, "rev-parse", "HEAD^")
    ).decode().strip() == prepared.base_sha
    assert b"filter.hostile" not in (
        await fixture_git(snapshot, "config", "--local", "--list")
    )
    assert b"h value.py" in (await fixture_git(author, "ls-files", "-v"))


async def test_candidate_keeps_ordinary_ignore_rules_and_all_tracked_edits(
    candidate_copy,
):
    """Generated ignored files are absent while tracked edits remain part of the snapshot."""
    from backend.runtime.code_candidate import capture_candidate

    _, binding, prepared, root = candidate_copy
    author = Path(prepared.workspace)
    (author / ".gitignore").write_text("build/\nvalue.py\n")
    (author / "build").mkdir()
    (author / "build/cache").write_text("generated")
    (author / "value.py").write_text("VALUE = 200\n")
    captured = await capture_candidate(
        binding, prepared, root / "candidate", executor=RealGitExecutor()
    )
    snapshot = Path(captured.workspace)
    assert (snapshot / "value.py").read_text() == "VALUE = 200\n"
    assert not (snapshot / "build").exists()


@pytest.mark.parametrize(
    "failure", ["wrong_base", "wrong_repository", "replaced_copy", "overlap"]
)
async def test_candidate_refuses_mismatched_or_redirected_identity(
    candidate_copy, failure
):
    """A candidate cannot be attributed to another prepared base, repository or physical execution directory."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import RunConflict, WorkspaceChanged

    _, binding, prepared, root = candidate_copy
    destination = root / "candidate"
    if failure == "wrong_base":
        prepared = replace(prepared, base_sha="a" * 40)
    elif failure == "wrong_repository":
        prepared = replace(prepared, repository_id=22)
    elif failure == "replaced_copy":
        Path(prepared.workspace).rename(root / "old-author")
        Path(prepared.workspace).mkdir(mode=0o700)
    else:
        destination = Path(prepared.workspace) / "candidate"
    with pytest.raises((RunConflict, WorkspaceChanged)):
        await capture_candidate(
            binding, prepared, destination, executor=RealGitExecutor()
        )
    assert not destination.exists()


async def test_candidate_allocation_is_never_reused_or_deleted(candidate_copy):
    """Repeated capture must preserve the original tree and require explicit recovery rather than resetting it."""
    from backend.runtime.code_candidate import capture_candidate

    _, binding, prepared, root = candidate_copy
    first = await capture_candidate(
        binding, prepared, root / "candidate", executor=RealGitExecutor()
    )
    with pytest.raises(FileExistsError):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=RealGitExecutor()
        )
    assert (
        await fixture_git(Path(first.workspace), "rev-parse", "HEAD")
    ).decode().strip() == first.head_sha


async def test_source_commit_advance_blocks_capture_without_overwriting_private_work(
    candidate_copy,
):
    """A changed original base must not silently redefine the candidate's parent."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import WorkspaceChanged

    source, binding, prepared, root = candidate_copy
    (source / "value.py").write_text("VALUE = 300\n")
    await fixture_git(source, "add", "value.py")
    await fixture_git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "advance",
    )
    (Path(prepared.workspace) / "value.py").write_text("VALUE = 200\n")
    with pytest.raises(WorkspaceChanged, match="base"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=RealGitExecutor()
        )
    assert (Path(prepared.workspace) / "value.py").read_text() == "VALUE = 200\n"


async def test_candidate_refuses_incomplete_diff_instead_of_recording_a_preview(
    candidate_copy,
):
    """A diff beyond the declared evidence budget retains files and cannot become a truncated candidate."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import RunConflict

    source, binding, prepared, root = candidate_copy
    (Path(prepared.workspace) / "large.txt").write_text("changed line\n" * 100000)
    with pytest.raises(RunConflict, match="complete"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=RealGitExecutor()
        )
    assert (root / "candidate/repository/large.txt").exists()
    assert not (source / "large.txt").exists()


async def test_tracked_ken_metadata_requires_explicit_candidate_policy(
    source_repository, tmp_path
):
    """A host cache exclusion must not silently omit a path already tracked by the admitted base."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import RunConflict
    from backend.runtime.development_workspace import prepare_workspace

    source, binding = source_repository
    (source / ".ken").mkdir()
    (source / ".ken/tracked.txt").write_text("Previously tracked project data.\n")
    await fixture_git(source, "add", ".ken")
    await fixture_git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "tracked ken",
    )
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    prepared = await prepare_workspace(
        binding, root / "author", executor=RealGitExecutor()
    )
    with pytest.raises(RunConflict, match="reserved .ken"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=RealGitExecutor()
        )
    assert not (root / "candidate").exists()


async def test_candidate_rejects_embedded_gitlink_instead_of_omitting_its_content(
    candidate_copy,
):
    """An embedded repository is not a complete single-repository code candidate."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import RunConflict

    _, binding, prepared, root = candidate_copy
    nested = Path(prepared.workspace) / "nested"
    nested.mkdir()
    await fixture_git(nested, "init", "-q")
    (nested / "value.py").write_text("VALUE = 200\n")
    await fixture_git(nested, "add", "value.py")
    await fixture_git(
        nested,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "nested",
    )
    with pytest.raises(RunConflict, match="gitlinks"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=RealGitExecutor()
        )


async def test_source_advancing_during_capture_cannot_be_returned_as_current(
    candidate_copy,
):
    """An external source commit after allocation invalidates the candidate's current-base precondition."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import WorkspaceChanged

    source, binding, prepared, root = candidate_copy

    class SourceAdvances(RealGitExecutor):
        """Model one independent user edit after the candidate commit has been constructed."""

        async def run(self, command, *, cwd, env, timeout):
            """Complete the real Git invocation, then advance only the registered source once."""
            result = await super().run(command, cwd=cwd, env=env, timeout=timeout)
            if "commit-tree" in command:
                (source / "user-note.txt").write_text("Independent user change.\n")
                await fixture_git(source, "add", "user-note.txt")
                await fixture_git(
                    source,
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@localhost",
                    "commit",
                    "-qm",
                    "user advance",
                )
            return result

    with pytest.raises(WorkspaceChanged, match="base"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=SourceAdvances()
        )
    assert (root / "candidate/repository").exists()
    assert (source / "user-note.txt").exists()


async def test_candidate_rejects_unconfirmed_process_closure(candidate_copy):
    """Even a complete successful diff cannot certify a candidate when its producing process may still be active."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import RunConflict

    _, binding, prepared, root = candidate_copy

    class UnclosedDiff(RealGitExecutor):
        """Keep actual Git bytes while withholding the required process-closure evidence."""

        async def run(self, command, *, cwd, env, timeout):
            """Return uncertain ownership only for the final real diff invocation."""
            result = await super().run(command, cwd=cwd, env=env, timeout=timeout)
            return (
                replace(result, local_execution_closed=False)
                if "diff" in command
                else result
            )

    with pytest.raises(RunConflict, match="closure"):
        await capture_candidate(
            binding, prepared, root / "candidate", executor=UnclosedDiff()
        )
