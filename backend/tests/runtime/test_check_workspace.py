"""Per-check copies derive from exact candidates and keep host validation metadata outside writable project files."""

from pathlib import Path

import pytest

from backend.tests.runtime.test_code_candidate import candidate_copy as candidate_copy  # noqa: PLC0414 -- register the real Git fixture.
from backend.tests.runtime.test_development_workspace import (
    RealGitExecutor,
)
from backend.tests.runtime.test_development_workspace import (
    source_repository as source_repository,  # noqa: PLC0414 -- register the source fixture used by candidate_copy.
)


@pytest.fixture
async def check_candidate(candidate_copy):
    """Capture one real independent candidate with no model or ambient project changes."""
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.contracts import WorkspaceBinding

    source, binding, prepared, root = candidate_copy
    (Path(prepared.workspace) / "value.py").write_text("VALUE = 200\n")
    captured = await capture_candidate(
        binding, prepared, root / "candidate", executor=RealGitExecutor()
    )
    snapshot = WorkspaceBinding(
        binding.repository_id,
        binding.repository_name,
        binding.registration_path,
        captured.workspace,
        captured.device,
        captured.inode,
    )
    return source, captured, snapshot, root


async def test_check_copy_has_exact_candidate_head_and_protected_metadata(
    check_candidate,
):
    """Only the independent execution copy is writable; its validation Git metadata is a separate private directory."""
    from backend.runtime.check_workspace import (
        check_workspace_matches,
        prepare_check_workspace,
    )

    source, candidate, binding, root = check_candidate
    prepared = await prepare_check_workspace(
        binding,
        root / "check",
        head_sha=candidate.head_sha,
        tree_sha=candidate.tree_sha,
        executor=RealGitExecutor(),
    )
    workspace = Path(prepared.view.workspace)
    assert (workspace / "value.py").read_text() == "VALUE = 200\n"
    assert Path(prepared.metadata.path).parent == root / "check"
    assert Path(prepared.metadata.path) != workspace / ".git"
    assert list((workspace / ".git").iterdir()) == []
    assert await check_workspace_matches(prepared, executor=RealGitExecutor())
    (workspace / "value.py").write_text("VALUE = 999\n")
    assert not await check_workspace_matches(prepared, executor=RealGitExecutor())
    assert (Path(candidate.workspace) / "value.py").read_text() == "VALUE = 200\n"
    assert "137" in (source / "value.py").read_text()


async def test_project_git_config_cannot_hide_mutation_or_execute_a_host_filter(
    check_candidate,
):
    """A writable placeholder .git cannot become the host validator's config/index, even without a mounted profile."""
    from backend.runtime.check_workspace import (
        check_workspace_matches,
        prepare_check_workspace,
    )

    _source, candidate, binding, root = check_candidate
    prepared = await prepare_check_workspace(
        binding,
        root / "check",
        head_sha=candidate.head_sha,
        tree_sha=candidate.tree_sha,
        executor=RealGitExecutor(),
    )
    workspace = Path(prepared.view.workspace)
    (workspace / ".git/config").write_text(
        '[filter "hostile"]\n clean = touch FILTER-EXECUTED\n'
    )
    (workspace / ".gitattributes").write_text("*.py filter=hostile\n")
    (workspace / "value.py").write_text("VALUE = 999\n")
    assert not await check_workspace_matches(prepared, executor=RealGitExecutor())
    assert not (workspace / "FILTER-EXECUTED").exists()


async def test_check_refuses_a_different_candidate_before_exposing_copy(
    check_candidate,
):
    """The same repo name does not authorize running tests against another head or tree."""
    from backend.runtime.check_workspace import prepare_check_workspace
    from backend.runtime.contracts import WorkspaceChanged

    _source, candidate, binding, root = check_candidate
    with pytest.raises(WorkspaceChanged):
        await prepare_check_workspace(
            binding,
            root / "check",
            head_sha="e" * 40,
            tree_sha=candidate.tree_sha,
            executor=RealGitExecutor(),
        )
