"""Capture a separate exact Git candidate without trusting an author's Git metadata.

The host must close all model and command writers before invoking this policy.
This module consumes an owned Git execution port; it neither grants authority
nor accepts or publishes changes. Durable attempt/context binding is a separate
controller responsibility. Interrupted allocations are retained, never reset.
"""

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.contracts import RunConflict, WorkspaceChanged
from backend.runtime.development_workspace import (
    _POLICY,
    _SHA,
    MAX_OUTPUT_BYTES,
    GitExecutor,
    GitResult,
    PreparedDevelopmentWorkspace,
    _source_identity,
    git_environment,
    prepare_workspace,
)
from backend.runtime.git_capsule import PrivateAllocation


@dataclass(frozen=True)
class CapturedCodeCandidate:
    """Private immutable Git identities and complete diff evidence, without approval or publication authority."""

    repository_id: int
    base_sha: str
    head_sha: str
    tree_sha: str
    workspace: str
    device: int
    inode: int
    diff: bytes
    diff_sha256: str


def _author_identity(prepared):
    """Require the exact private directory that the host prepared, without reading its mutable Git config/index."""
    if not isinstance(prepared, PreparedDevelopmentWorkspace):
        raise TypeError("Candidate requires a prepared development identity")
    try:
        current = PrivateAllocation.capture(prepared.workspace)
    except (OSError, ValueError) as exc:
        raise WorkspaceChanged("Prepared candidate source directory changed") from exc
    if (current.device, current.inode) != (prepared.device, prepared.inode):
        raise WorkspaceChanged("Prepared candidate source directory changed")
    return Path(current.path)


async def capture_candidate(
    binding, prepared, destination, *, executor: GitExecutor, timeout=60
):
    """Freeze tracked/nonignored private edits in fresh metadata with one exact admitted parent.

    Only the host's credential-free Git policy and owned process executor are
    used. Author config, index flags, refs and commits cannot select the candidate
    tree or parent. Root .ken metadata is excluded; a base tracking that reserved
    path and gitlink candidates require explicit policy and are refused. Reserved
    legacy .worktrees storage cannot be published as authored code. Complete
    binary diff output is bounded at one MiB; overflow fails without truncating
    evidence. The caller must fence/close writers before capture and bind the
    returned identities to its durable attempt/context before delivery.
    """
    author = _author_identity(prepared)
    _source_identity(binding)
    if prepared.repository_id != binding.repository_id:
        raise RunConflict("Prepared candidate belongs to another repository")
    if not _SHA.fullmatch(prepared.base_sha) or not _SHA.fullmatch(
        prepared.base_tree_sha
    ):
        raise RunConflict("Prepared candidate base identity is incomplete")
    destination = Path(destination).absolute()
    if destination.is_relative_to(author) or author.is_relative_to(destination):
        raise RunConflict("Candidate allocation overlaps the author's copy")
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError(
            "Candidate capture requires a total deadline of at most 300 seconds"
        )
    if not Path(executor.git_binary).is_absolute():
        raise ValueError("Candidate capture requires a fixed absolute Git asset")
    deadline = time.monotonic() + timeout
    environment = git_environment(Path("/home/actor"))

    async def git(directory, *arguments):
        """Require bounded complete Git output and original process closure under the one capture deadline."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunConflict(
                "Candidate capture deadline expired; inspect retained state"
            )
        try:
            result = await executor.run(
                (str(executor.git_binary), *_POLICY, *arguments),
                cwd=executor.execution_path(directory),
                env=dict(environment),
                timeout=remaining,
            )
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise RunConflict(
                "Candidate Git command failed; inspect retained state"
            ) from exc
        if (
            not isinstance(result, GitResult)
            or not result.output_complete
            or not result.local_execution_closed
            or result.exit_code != 0
            or not isinstance(result.stdout, bytes)
            or len(result.stdout) > MAX_OUTPUT_BYTES
        ):
            raise RunConflict(
                "Candidate requires complete successful Git evidence and physical closure"
            )
        return result.stdout

    async def sha(directory, *arguments):
        """Read one canonical full Git object identity rather than a mutable ref or abbreviated display."""
        try:
            value = (await git(directory, *arguments)).decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise RunConflict("Candidate Git identity is invalid") from exc
        if not _SHA.fullmatch(value):
            raise RunConflict("Candidate Git identity is incomplete")
        return value

    source = Path(binding.workspace)
    if await sha(source, "rev-parse", "--verify", "HEAD^{commit}") != prepared.base_sha:
        raise WorkspaceChanged("Original source base changed before candidate capture")
    if await git(source, "ls-tree", "-z", prepared.base_sha, "--", ".ken"):
        raise RunConflict(
            "The base tracks reserved .ken metadata; explicit candidate policy is required"
        )
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RunConflict("Candidate capture deadline expired before allocation")
    snapshot = await prepare_workspace(
        binding, destination, executor=executor, timeout=remaining
    )
    if (snapshot.base_sha, snapshot.base_tree_sha) != (
        prepared.base_sha,
        prepared.base_tree_sha,
    ):
        raise WorkspaceChanged(
            "Original source base changed during candidate allocation"
        )
    working = Path(snapshot.workspace)
    metadata = str(executor.execution_path(working / ".git"))
    author_alias = str(executor.execution_path(author))

    async def stage():
        """Stage author bytes into fresh host-owned metadata; do not use or mutate the author's index."""
        _author_identity(prepared)
        await git(
            working,
            "--git-dir=" + metadata,
            "--work-tree=" + author_alias,
            "add",
            "--all",
            "--",
            ".",
            ":(top,exclude).ken",
        )
        return await sha(working, "write-tree")

    tree = await stage()
    entries = await git(working, "ls-tree", "-r", "-z", tree)
    if any(
        entry.partition(b"\t")[2] == b".worktrees"
        or entry.partition(b"\t")[2].startswith(b".worktrees/")
        for entry in entries.split(b"\0")
        if entry
    ):
        raise RunConflict("Candidate cannot publish reserved legacy .worktrees storage")
    if any(entry.startswith(b"160000 ") for entry in entries.split(b"\0")):
        raise RunConflict("Candidate gitlinks require explicit multi-repository policy")
    if await stage() != tree:
        raise WorkspaceChanged(
            "Private copy changed during candidate capture; close its writers"
        )
    head = await sha(
        working,
        "-c",
        "user.name=Researcher",
        "-c",
        "user.email=researcher@localhost",
        "commit-tree",
        tree,
        "-p",
        prepared.base_sha,
        "-m",
        "Private development candidate",
    )
    # Pin only in the independent allocation. No author/original refs are changed.
    await git(working, "update-ref", "refs/researcher/candidate", head)
    # The worktree still contains the base, while staging changed this new
    # index. Restore its base identity so checkout also removes deleted paths.
    # Both operations touch only the exclusively allocated snapshot.
    await git(working, "read-tree", prepared.base_sha)
    await git(working, "checkout", "--force", "--detach", head)
    if await sha(working, "rev-parse", "HEAD^{tree}") != tree:
        raise WorkspaceChanged("Candidate checkout differs from its captured tree")
    diff = await git(
        working,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--binary",
        "--full-index",
        "--no-color",
        "--no-renames",
        prepared.base_sha,
        head,
        "--",
    )
    if await git(working, "status", "--porcelain=v1", "--untracked-files=all"):
        raise WorkspaceChanged("Captured candidate working tree changed")
    _author_identity(prepared)
    _source_identity(binding)
    if await sha(source, "rev-parse", "--verify", "HEAD^{commit}") != prepared.base_sha:
        raise WorkspaceChanged("Original source base changed during candidate capture")
    info = working.stat()
    return CapturedCodeCandidate(
        binding.repository_id,
        prepared.base_sha,
        head,
        tree,
        str(working),
        info.st_dev,
        info.st_ino,
        diff,
        hashlib.sha256(diff).hexdigest(),
    )
