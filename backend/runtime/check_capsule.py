"""Fixed isolated check profile: one private execution copy writable, validation metadata/dependencies readonly."""

import json
import os
import stat
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import UUID

from backend.runtime.broker_profile import AnalysisCapsule, CodexAsset, _syscall_filter
from backend.runtime.check_contracts import CheckSpec
from backend.runtime.check_registry import CheckExecutionView
from backend.runtime.contracts import WorkspaceChanged, text
from backend.runtime.git_capsule import PrivateAllocation
from backend.runtime.workspaces import PEER_WORKSPACE


@dataclass(frozen=True)
class CheckEnvironment:
    """Explicit host-selected dependency directory identity; no ambient home/config or automatic dependency fallback."""

    identity: str
    packages: str | None = None
    device: int | None = None
    inode: int | None = None

    def __post_init__(self):
        """Reject incomplete named environments and broad roots even when constructed without the capture helper."""
        text(self.identity, "Check environment", 128)
        if self.packages is None:
            if (
                self.identity != "system"
                or self.device is not None
                or self.inode is not None
            ):
                raise ValueError(
                    "Named dependency environment requires its explicit package view"
                )
        elif (
            self.identity == "system"
            or not isinstance(self.packages, str)
            or not Path(self.packages).is_absolute()
            or Path(self.packages).name not in ("site-packages", "dist-packages")
            or type(self.device) is not int
            or self.device < 0
            or type(self.inode) is not int
            or self.inode <= 0
        ):
            raise ValueError("Check dependency view identity is incomplete")

    @classmethod
    def system(cls):
        """Select only the common readonly system/runtime mounts, without extra package roots."""
        return cls("system")

    @classmethod
    def capture(cls, identity, path):
        """Capture a normal installed package root, rejecting redirected, writable or overly broad host directories."""
        text(identity, "Check environment", 128)
        path = Path(path).absolute()
        info = path.lstat()
        if (
            path.resolve(strict=True) != path
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in (0, os.getuid())
            or info.st_mode & 0o022
            or path.name not in ("site-packages", "dist-packages")
        ):
            raise ValueError(
                "Check dependencies require an explicit trusted package directory"
            )
        return cls(identity, str(path), info.st_dev, info.st_ino)


@dataclass(frozen=True)
class CheckLaunch:
    """Immutable host recipe and pinned executable; this manifest alone cannot authorize a workspace or process."""

    check_id: str
    spec: CheckSpec
    metadata: PrivateAllocation
    environment: CheckEnvironment
    asset: CodexAsset = field(init=False)

    def __post_init__(self):
        """Require a bounded recipe, matching explicit environment and readonly system/runtime executable."""
        if (
            str(UUID(self.check_id)) != self.check_id
            or not isinstance(self.spec, CheckSpec)
            or not isinstance(self.metadata, PrivateAllocation)
            or not isinstance(self.environment, CheckEnvironment)
        ):
            raise ValueError("Check requires original host-selected typed identities")
        if self.environment.identity != self.spec.environment_id:
            raise ValueError("Check environment differs from recipe")
        asset = CodexAsset.inspect(self.spec.argv[0])
        path = Path(asset.path)
        if not (
            path.is_relative_to("/usr")
            or path.is_relative_to(Path(sys.base_prefix).resolve(strict=True))
        ):
            raise ValueError(
                "Check program must belong to the readonly system/runtime asset views"
            )
        object.__setattr__(self, "asset", asset)


class CheckCapsule(AnalysisCapsule):
    """Keep the candidate/source absent while the original gate runs one manifest-bound check copy."""

    def __init__(self, binding, launch, info_fd):
        """Accept only the check registry's exact view and matching protected recipe/metadata identities."""
        if (
            not isinstance(binding, CheckExecutionView)
            or not isinstance(launch, CheckLaunch)
            or (binding.check_id, binding.spec_sha256, binding.metadata)
            != (launch.check_id, launch.spec.sha256, launch.metadata)
        ):
            raise ValueError(
                "Check launch differs from its admitted exact execution view"
            )
        super().__init__(binding, None, info_fd)
        self.launch = launch
        self._fds = []

    def _open(self, path, *, directory=False):
        """Pin a no-follow host asset until the gated spawn consumes its explicit mount."""
        fd = os.open(
            path,
            os.O_RDONLY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
            | (os.O_DIRECTORY if directory else 0),
        )
        self._stack.callback(os.close, fd)
        self._fds.append(fd)
        return fd

    def _program(self):
        """Pin program bytes and invoke only the packaged trusted collector with JSON data arguments."""
        self._program_fd = self._open(self.launch.asset.path)
        if (
            CodexAsset._read(self._program_fd, Path(self.launch.asset.path))
            != self.launch.asset
        ):
            raise WorkspaceChanged("Check executable asset changed")
        settings = json.dumps(
            {
                "spec": asdict(self.launch.spec),
                "packages": self.launch.environment.packages is not None,
            }
        )
        return [
            str(Path(sys.executable).resolve(strict=True)),
            "-I",
            "-S",
            "-c",
            Path(__file__).with_name("check_worker.py").read_text(),
            settings,
        ]

    def _workspace_mount(self, source):
        """Grant write access only to the check registry's prepared independent copy."""
        return "--bind-fd"

    def _filter(self):
        """Allow private local test sockets while denying Internet families and kernel/peer-control operations."""
        return _syscall_filter(
            network=False, protected_peers=True, private_pairs=True, local_sockets=True
        )

    def _mounts(self):
        """Mount protected validation Git and explicit dependencies readonly; neither host home nor broker control is exposed."""
        metadata = self.launch.metadata
        fd = self._open(metadata.path, directory=True)
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (metadata.device, metadata.inode):
            raise WorkspaceChanged("Check metadata changed")
        mounts = [
            "--ro-bind-fd",
            str(self._program_fd),
            self.launch.asset.path,
            "--ro-bind-fd",
            str(fd),
            str(PEER_WORKSPACE / ".git"),
        ]
        environment = self.launch.environment
        if environment.packages is not None:
            packages = Path(environment.packages)
            if packages.is_relative_to(self.binding.workspace):
                raise ValueError("Check dependencies overlap its writable copy")
            fd = self._open(packages, directory=True)
            info = os.fstat(fd)
            if (
                (info.st_dev, info.st_ino) != (environment.device, environment.inode)
                or info.st_uid not in (0, os.getuid())
                or info.st_mode & 0o022
                or packages.resolve(strict=True) != packages
            ):
                raise WorkspaceChanged("Check dependency directory changed")
            mounts += [
                "--dir",
                "/run/researcher-check",
                "--ro-bind-fd",
                str(fd),
                "/run/researcher-check/packages",
            ]
        return mounts

    def __enter__(self):
        """Retain all pinned mounts through the original broker's gated spawn."""
        super().__enter__()
        self.pass_fds += tuple(self._fds)
        return self
