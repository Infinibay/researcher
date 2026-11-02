"""Fixed Git preparation profile: admitted source readonly, one private allocation writable.

The global broker owns every process and gate. These values are host-selected
manifests, not credentials or parameters admitted from a model tool call.
"""

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend.runtime.broker_profile import AnalysisCapsule, CodexAsset
from backend.runtime.contracts import WorkspaceChanged, text
from backend.runtime.development_workspace import git_environment
from backend.runtime.workspaces import PEER_WORKSPACE

PEER_ALLOCATION = Path("/run/researcher-development")


class GitAsset(CodexAsset):
    """Pinned trusted system Git executable; its installed /usr helper layout stays readonly."""


@dataclass(frozen=True)
class PrivateAllocation:
    """Original private directory identity; it cannot authorize a source or another allocation."""

    path: str
    device: int
    inode: int

    @classmethod
    def capture(cls, path):
        """Capture a real operator-owned directory without following a replacement symlink."""
        path = Path(path).absolute()
        info = path.lstat()
        if (
            path.resolve(strict=True) != path
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise ValueError(
                "Git allocation must be a private operator-owned directory"
            )
        return cls(str(path), info.st_dev, info.st_ino)


@dataclass(frozen=True)
class GitLaunch:
    """Immutable fixed-program invocation and allocation manifest supplied only by the owner."""

    asset: GitAsset
    arguments: tuple[str, ...]
    cwd: str
    environment: tuple[tuple[str, str], ...]
    allocation: PrivateAllocation | None

    def __post_init__(self):
        """Reject mixed environment, arbitrary programs and directories outside the two explicit views."""
        if not isinstance(self.asset, GitAsset) or not Path(
            self.asset.path
        ).is_relative_to("/usr"):
            raise ValueError("Git preparation requires a pinned /usr system Git asset")
        if not isinstance(self.arguments, tuple) or len(self.arguments) > 256:
            raise ValueError("Bounded immutable Git arguments are required")
        for argument in self.arguments:
            if (
                not isinstance(argument, str)
                or "\0" in argument
                or len(argument.encode()) > 64000
            ):
                raise ValueError("Git arguments must be bounded strings without NUL")
        if sum(len(value.encode()) for value in self.arguments) > 64000:
            raise ValueError("Git arguments exceed their complete input budget")
        path = PurePosixPath(self.cwd)
        text(self.cwd, "Git working directory", 4096)
        if ".." in path.parts or not any(
            path.is_relative_to(root) for root in (PEER_WORKSPACE, PEER_ALLOCATION)
        ):
            raise ValueError("Git cwd is outside its admitted execution views")
        if path.is_relative_to(PEER_ALLOCATION) and self.allocation is None:
            raise ValueError("Git allocation is not available in this invocation")
        expected = tuple(sorted(git_environment(Path("/home/actor")).items()))
        if self.environment != expected:
            raise ValueError(
                "Git preparation environment differs from the fixed credential-free policy"
            )


class GitCapsule(AnalysisCapsule):
    """Execute only pinned Git under the original gate with a separate private allocation mount."""

    def __init__(self, binding, launch, info_fd):
        """Keep the source admission separate from the optional writable private copy."""
        if not isinstance(launch, GitLaunch):
            raise TypeError("A fixed owner Git launch is required")
        super().__init__(binding, None, info_fd)
        self.launch = launch
        self._asset_fd = None
        self._allocation_fd = None

    def _program(self):
        """Pin Git bytes before spawn and avoid shell interpolation of any argument."""
        asset = self.launch.asset
        self._asset_fd = os.open(asset.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self._stack.callback(os.close, self._asset_fd)
        if GitAsset._read(self._asset_fd, Path(asset.path)) != asset:
            raise ValueError("Git executable no longer matches its original manifest")
        code = (
            "import os;os.chdir("
            + repr(self.launch.cwd)
            + ");os.execve("
            + repr(asset.path)
            + ","
            + repr([asset.path, *self.launch.arguments])
            + ","
            + repr(dict(self.launch.environment))
            + ")"
        )
        return [str(Path(sys.executable).resolve(strict=True)), "-I", "-S", "-c", code]

    def _mounts(self):
        """Expose the exact opened allocation; common readonly system aliases belong to the base capsule."""
        mounts = ["--ro-bind-fd", str(self._asset_fd), self.launch.asset.path]
        if self.launch.allocation is not None:
            allocation = self.launch.allocation
            path = Path(allocation.path)
            source = Path(self.binding.workspace)
            if path.is_relative_to(source) or source.is_relative_to(path):
                raise ValueError("Git allocation overlaps the original source")
            self._allocation_fd = os.open(
                path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            self._stack.callback(os.close, self._allocation_fd)
            info = os.fstat(self._allocation_fd)
            if (
                (info.st_dev, info.st_ino) != (allocation.device, allocation.inode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
            ):
                raise WorkspaceChanged("Private Git allocation identity changed")
            mounts += ["--bind-fd", str(self._allocation_fd), str(PEER_ALLOCATION)]
        return mounts

    def __enter__(self):
        """Retain pinned asset/allocation descriptors until the owner's gated spawn has consumed them."""
        super().__enter__()
        self.pass_fds += (self._asset_fd,)
        if self._allocation_fd is not None:
            self.pass_fds += (self._allocation_fd,)
        return self
