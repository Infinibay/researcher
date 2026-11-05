"""Host publication Git profile: original working files readonly, pinned Git metadata writable, accepted candidate readonly."""

import os
from dataclasses import dataclass
from pathlib import Path

from backend.runtime.broker_profile import AnalysisCapsule
from backend.runtime.contracts import WorkspaceChanged
from backend.runtime.development_workspace import git_environment
from backend.runtime.git_capsule import GitAsset, GitCapsule
from backend.runtime.publication_git import PublicationDirectory, PublicationView
from backend.runtime.workspaces import PEER_WORKSPACE

PEER_PUBLICATION_CANDIDATE = Path("/run/researcher-publication-candidate")


@dataclass(frozen=True)
class PublicationGitLaunch:
    """Immutable host Git invocation and full transaction input, bound to an acceptance-linked view by broker admission."""

    asset: GitAsset
    arguments: tuple[str, ...]
    cwd: str
    environment: tuple[tuple[str, str], ...]
    view: PublicationView
    input_text: str | None = None

    def __post_init__(self):
        """Require the fixed Git asset, two explicit views and bounded original command/input data; no ambient execution policy."""
        if (
            not isinstance(self.asset, GitAsset)
            or not Path(self.asset.path).is_relative_to("/usr")
            or not isinstance(self.view, PublicationView)
        ):
            raise ValueError(
                "Publication requires its inspected Git asset and exact accepted view"
            )
        if self.cwd not in (str(PEER_WORKSPACE), str(PEER_PUBLICATION_CANDIDATE)):
            raise ValueError("Publication Git cwd is outside its original views")
        if (
            not isinstance(self.arguments, tuple)
            or len(self.arguments) > 256
            or any(not isinstance(arg, str) or "\0" in arg for arg in self.arguments)
            or sum(len(arg.encode()) for arg in self.arguments) > 64000
        ):
            raise ValueError("Publication Git arguments must be bounded and immutable")
        if self.environment != tuple(
            sorted(git_environment(Path("/home/actor")).items())
        ):
            raise ValueError(
                "Publication requires the fixed credential-free Git environment"
            )
        if self.input_text is not None and (
            not isinstance(self.input_text, str)
            or len(self.input_text.encode()) > 64000
            or "\0" in self.input_text
        ):
            raise ValueError(
                "Publication transaction input must be complete and bounded"
            )


class PublicationGitCapsule(GitCapsule):
    """Reuse the fixed Git program while granting write access only to its original source metadata directory."""

    def __init__(self, binding, launch, info_fd):
        """Bind capsule policy to exactly the source registration and accepted candidate in the original launch."""
        if (
            not isinstance(launch, PublicationGitLaunch)
            or binding != launch.view.source
        ):
            raise ValueError(
                "Publication launch differs from its original source admission"
            )
        AnalysisCapsule.__init__(self, binding, None, info_fd)
        self.launch = launch
        self._asset_fd = self._allocation_fd = None
        self._publication_fds = []

    def _directory(self, identity):
        """Open and retain the exact original directory before namespace construction, rejecting replacements and redirects."""
        if PublicationDirectory.capture(identity.path) != identity:
            raise WorkspaceChanged("Publication metadata/candidate identity changed")
        fd = os.open(
            identity.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        self._stack.callback(os.close, fd)
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (identity.device, identity.inode):
            raise WorkspaceChanged("Publication directory changed while opening")
        self._publication_fds.append(fd)
        return fd

    def _mounts(self):
        """Expose only original pinned descriptors; candidate and source working files never become writable."""
        view = self.launch.view
        source, candidate = Path(view.source.workspace), Path(view.workspace)
        if source.is_relative_to(candidate) or candidate.is_relative_to(source):
            raise ValueError(
                "Publication source and candidate must be independent views"
            )
        metadata = self._directory(view.source_metadata)
        candidate_fd = self._directory(
            PublicationDirectory(view.workspace, view.device, view.inode)
        )
        candidate_metadata = self._directory(view.candidate_metadata)
        return [
            "--ro-bind-fd",
            str(self._asset_fd),
            self.launch.asset.path,
            "--bind-fd",
            str(metadata),
            str(PEER_WORKSPACE / ".git"),
            "--ro-bind-fd",
            str(candidate_fd),
            str(PEER_PUBLICATION_CANDIDATE),
            "--ro-bind-fd",
            str(candidate_metadata),
            str(PEER_PUBLICATION_CANDIDATE / ".git"),
        ]

    def __enter__(self):
        """Keep all metadata/candidate descriptors live until the original gated spawn consumes them."""
        super().__enter__()
        self.pass_fds += tuple(self._publication_fds)
        return self
