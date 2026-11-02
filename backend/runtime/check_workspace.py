"""Prepare exact disposable check copies with validation metadata outside writable project files.

This policy only uses the host's owned Git port. It does not grant process
permissions, record a check, run a recipe or accept work. The controller must
reserve its private allocation before calling it and retain interrupted copies.
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.contracts import RunConflict, WorkspaceChanged
from backend.runtime.development_workspace import (
    _POLICY,
    MAX_OUTPUT_BYTES,
    GitResult,
    PreparedDevelopmentWorkspace,
    git_environment,
    prepare_workspace,
)
from backend.runtime.git_capsule import PrivateAllocation


@dataclass(frozen=True)
class PreparedCheckWorkspace:
    """Exact candidate-derived execution directory and distinct protected Git metadata, not check approval."""

    view: PreparedDevelopmentWorkspace
    metadata: PrivateAllocation


def _identity(prepared):
    """Reject replaced execution/metadata directories before opening trusted validation commands."""
    if not isinstance(prepared, PreparedCheckWorkspace):
        raise TypeError("Prepared check workspace required")
    try:
        workspace = PrivateAllocation.capture(prepared.view.workspace)
        metadata = PrivateAllocation.capture(prepared.metadata.path)
    except (ValueError, OSError) as exc:
        raise WorkspaceChanged("Check workspace identity changed") from exc
    if (workspace.device, workspace.inode) != (
        prepared.view.device,
        prepared.view.inode,
    ) or metadata != prepared.metadata:
        raise WorkspaceChanged("Check workspace identity changed")


async def _git(executor, directory, *arguments, timeout):
    """Require complete successful output and physical closure from the fixed credential-free Git port."""
    try:
        result = await executor.run(
            (str(executor.git_binary), *_POLICY, *arguments),
            cwd=executor.execution_path(Path(directory)),
            env=git_environment(Path("/home/actor")),
            timeout=timeout,
        )
    except RunConflict:
        raise
    except (OSError, RuntimeError, TimeoutError) as exc:
        raise RunConflict(
            "Check Git evidence unavailable; inspect retained state"
        ) from exc
    if (
        not isinstance(result, GitResult)
        or result.exit_code != 0
        or not result.output_complete
        or not result.local_execution_closed
        or not isinstance(result.stdout, bytes)
        or len(result.stdout) > MAX_OUTPUT_BYTES
    ):
        raise RunConflict("Check requires complete successful Git evidence and closure")
    return result.stdout


async def prepare_check_workspace(
    binding, destination, *, head_sha, tree_sha, executor, timeout=60
):
    """Clone an exact candidate once, then relocate its trusted Git metadata before exposing writable project files."""
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError("Check preparation requires a bounded deadline")
    deadline = time.monotonic() + timeout
    prepared = await prepare_workspace(
        binding, destination, executor=executor, timeout=timeout
    )
    if (prepared.base_sha, prepared.base_tree_sha) != (head_sha, tree_sha):
        raise WorkspaceChanged("Check copy differs from its exact candidate head/tree")
    repository = Path(prepared.workspace)
    original = repository / ".git"
    metadata = repository.parent / "validation-git"
    if original.is_symlink() or not original.is_dir() or os.path.lexists(metadata):
        raise RunConflict(
            "Check validation metadata requires its fresh independent allocation"
        )
    original.chmod(0o700)
    original.rename(metadata)
    original.mkdir(mode=0o700)
    result = PreparedCheckWorkspace(prepared, PrivateAllocation.capture(metadata))
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not await check_workspace_matches(
        result, executor=executor, timeout=remaining
    ):
        raise WorkspaceChanged("Prepared check copy is not a clean exact candidate")
    return result


async def check_workspace_matches(prepared, *, executor, timeout=30):
    """Validate candidate bytes using protected metadata; never execute filters or read an index controlled by tests."""
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError("Check validation requires a bounded deadline")
    _identity(prepared)
    deadline = time.monotonic() + timeout
    workspace = Path(prepared.view.workspace)
    options = (
        "--git-dir=" + str(executor.execution_path(Path(prepared.metadata.path))),
        "--work-tree=" + str(executor.execution_path(workspace)),
    )

    async def git(*args):
        """Keep both identity and byte queries inside one total validation deadline."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunConflict("Check validation deadline expired")
        return await _git(executor, workspace, *options, *args, timeout=remaining)

    head = (await git("rev-parse", "--verify", "HEAD^{commit}")).decode("ascii").strip()
    tree = (await git("rev-parse", "--verify", "HEAD^{tree}")).decode("ascii").strip()
    if (head, tree) != (prepared.view.base_sha, prepared.view.base_tree_sha):
        return False
    status = await git(
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    _identity(prepared)
    return not status
