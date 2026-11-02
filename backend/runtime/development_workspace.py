"""Prepare an independent exact-base Git copy for one native development attempt.

This module owns Git preparation policy, not process authority. Its caller must
supply the owned isolated executor before exposing it through the product. No
ambient subprocess launcher, credentials, branch reset or cleanup fallback exists.
The original registered source remains unchanged; failed copies remain inspectable.
"""

import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend.runtime.contracts import RunConflict, WorkspaceBinding, WorkspaceChanged

MAX_OUTPUT_BYTES = 1024**2
_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_POLICY = (
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "core.attributesFile=/dev/null",
    "-c",
    "credential.helper=",
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.file.allow=always",
    "-c",
    "gc.auto=0",
    "-c",
    "maintenance.auto=false",
)


@dataclass(frozen=True)
class GitResult:
    """Owned executor evidence; a truncated output or unclosed process is not a usable Git result."""

    stdout: bytes
    exit_code: int
    output_complete: bool
    local_execution_closed: bool


class GitExecutor(Protocol):
    """Host-selected trusted Git asset and owned process execution port, never supplied by a model."""

    git_binary: Path

    def execution_path(self, host_path: Path) -> Path:
        """Map an admitted host source/allocation to the executor's explicit mount namespace."""
        ...

    async def run(self, command, *, cwd, env, timeout) -> GitResult:
        """Execute inside the caller's owned boundary with bounded complete output and proven closure."""
        ...


@dataclass(frozen=True)
class PreparedDevelopmentWorkspace:
    """Independent execution directory and pinned base, not acceptance or publication authority."""

    repository_id: int
    workspace: str
    device: int
    inode: int
    base_sha: str
    base_tree_sha: str


def git_environment(home):
    """Construct a clean environment; host OAuth, Git config, askpass and arbitrary helper paths are absent."""
    return {
        "PATH": os.defpath,
        "HOME": str(home),
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "GIT_SSH_COMMAND": "/bin/false",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }


def _source_identity(binding):
    """Reject a replaced or redirected registered directory before or after asynchronous preparation."""
    source = Path(binding.workspace)
    try:
        info = source.lstat()
        current = source.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceChanged("Registered development source is unavailable") from exc
    if (
        current != source
        or not stat.S_ISDIR(info.st_mode)
        or (info.st_dev, info.st_ino) != (binding.device, binding.inode)
    ):
        raise WorkspaceChanged("Registered development source changed")
    return source


async def prepare_workspace(
    binding: WorkspaceBinding, destination, *, executor: GitExecutor, timeout=30
):
    """Clone an exact committed source into a fresh private attempt directory without sharing metadata.

    Dirty/hidden-index sources, linked/shared metadata and submodules need explicit
    policy before admission; they are refused without editing or deleting anything.
    The returned copy is only a preparation dependency. Runtime lease binding,
    writable capsule admission, durable recovery and candidate publication belong
    to the native controller and must be wired before enabling development tasks.
    """
    source = _source_identity(binding)
    destination = Path(destination).absolute()
    parent = destination.parent.resolve(strict=True)
    if parent != destination.parent or os.path.lexists(destination):
        raise FileExistsError(
            "Attempt directory exists or its parent is redirected; reconcile it instead of resetting"
        )
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise RunConflict("Development copy must be separate from its original source")
    parent_info = parent.stat()
    if parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o077:
        raise RunConflict(
            "Development destination requires a private operator-owned parent"
        )
    metadata = source / ".git"
    if (
        metadata.is_symlink()
        or not metadata.is_dir()
        or (metadata / "objects").is_symlink()
        or (metadata / "commondir").exists()
        or (metadata / "objects/info/alternates").exists()
    ):
        raise RunConflict(
            "Linked/shared Git metadata requires explicit workspace preparation policy"
        )
    binary = Path(executor.git_binary)
    if not binary.is_absolute():
        raise ValueError("Git executor requires an explicit absolute trusted asset")
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError("Git preparation timeout must be between 0 and 300 seconds")
    deadline = time.monotonic() + timeout
    environment = git_environment(Path("/home/actor"))

    async def git(cwd, *arguments):
        """Consume complete closed Git evidence under one total deadline; never infer success from a partial result."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunConflict(
                "Git preparation deadline expired; retained state requires inspection"
            )
        try:
            result = await executor.run(
                (str(binary), *_POLICY, *arguments),
                cwd=executor.execution_path(cwd),
                env=dict(environment),
                timeout=remaining,
            )
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise RunConflict(
                "Git preparation failed; inspect the owned command receipt before retrying"
            ) from exc
        if (
            not isinstance(result, GitResult)
            or not result.local_execution_closed
            or not result.output_complete
        ):
            raise RunConflict(
                "Git preparation output or physical closure is unconfirmed"
            )
        if result.exit_code != 0:
            raise RunConflict(
                "Git preparation command failed; retained state requires inspection"
            )
        if (
            not isinstance(result.stdout, bytes)
            or len(result.stdout) > MAX_OUTPUT_BYTES
        ):
            raise RunConflict(
                "Git preparation output exceeded its complete evidence budget"
            )
        return result.stdout

    async def sha(cwd, expression):
        """Read one full canonical Git identity, not an abbreviated branch name or human output."""
        value = (
            (await git(cwd, "rev-parse", "--verify", expression))
            .decode("ascii")
            .strip()
        )
        if not _SHA.fullmatch(value):
            raise RunConflict("Git did not return a complete commit/tree identity")
        return value

    config_names = await git(
        source, "config", "--local", "--includes", "--name-only", "--list", "-z"
    )
    if any(name.lower().startswith(b"filter.") for name in config_names.split(b"\0")):
        raise RunConflict(
            "Repository Git filters require an explicit isolated preparation policy"
        )
    top_level = await git(source, "rev-parse", "--show-toplevel")
    if Path(os.fsdecode(top_level.removesuffix(b"\n"))) != executor.execution_path(
        source
    ):
        raise RunConflict(
            "Git working tree differs from the registered development source"
        )
    base = await sha(source, "HEAD^{commit}")
    tree = await sha(source, "HEAD^{tree}")
    if await git(
        source,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignore-submodules=none",
    ):
        raise RunConflict(
            "Source has uncommitted work; preserve it before starting a separate development attempt"
        )
    flags = await git(source, "ls-files", "-v", "-z")
    if any(not entry.startswith(b"H ") for entry in flags.split(b"\0") if entry):
        raise RunConflict(
            "Source index hides working changes; an explicit normal-index policy is required"
        )
    entries = await git(source, "ls-tree", "-r", "-z", base)
    if any(entry.startswith(b"160000 ") for entry in entries.split(b"\0")):
        raise RunConflict(
            "Submodule development requires an explicit multi-repository candidate policy"
        )
    _source_identity(binding)
    if await sha(source, "HEAD^{commit}") != base:
        raise WorkspaceChanged("Source commit changed during development admission")
    # Exclusive allocation is never reused, even after a partial failed clone.
    destination.mkdir(mode=0o700)
    template = destination / ".empty-template"
    template.mkdir(mode=0o700)
    repository = destination / "repository"
    repository.mkdir(mode=0o700)
    await git(
        destination,
        "clone",
        "--no-local",
        "--no-hardlinks",
        "--no-checkout",
        "--no-tags",
        "--depth=1",
        f"--revision={base}",
        f"--template={executor.execution_path(template)}",
        "--",
        executor.execution_path(source).as_uri(),
        str(executor.execution_path(repository)),
    )
    await git(repository, "remote", "remove", "origin")
    await git(repository, "config", "--local", "core.hooksPath", "/dev/null")
    await git(repository, "config", "--local", "credential.helper", "")
    await git(repository, "checkout", "--detach", base)
    if (
        await sha(repository, "HEAD^{commit}") != base
        or await sha(repository, "HEAD^{tree}") != tree
    ):
        raise WorkspaceChanged(
            "Prepared development copy differs from the admitted base"
        )
    _source_identity(binding)
    info = repository.stat()
    return PreparedDevelopmentWorkspace(
        binding.repository_id, str(repository), info.st_dev, info.st_ino, base, tree
    )
