"""Owned publication Git port with complete transaction stdin in the original broker manifest; never a host subprocess fallback."""

from pathlib import Path

from backend.runtime.broker_git import OwnedGitExecutor
from backend.runtime.contracts import RunConflict
from backend.runtime.publication_capsule import (
    PEER_PUBLICATION_CANDIDATE,
    PublicationGitLaunch,
    PublicationObservationLaunch,
)
from backend.runtime.workspaces import PEER_WORKSPACE


class OwnedPublicationGitExecutor(OwnedGitExecutor):
    """Execute a fixed accepted-code publication through its fresh original command-only owner."""

    launch_type = PublicationGitLaunch

    def __init__(self, *, owner, registry, lease, view, asset):
        """Keep the exact admission view and reuse the established command observation/closure machinery."""
        super().__init__(
            owner=owner,
            registry=registry,
            lease=lease,
            source=Path(view.source.workspace),
            allocation=None,
            asset=asset,
        )
        self.view = view
        self._operation_prefix = "git-publication"

    def execution_path(self, host_path):
        """Map only original source and accepted candidate paths to their distinct publication aliases."""
        path = Path(host_path).absolute()
        for host, peer in (
            (Path(self.view.source.workspace), PEER_WORKSPACE),
            (Path(self.view.workspace), PEER_PUBLICATION_CANDIDATE),
        ):
            if path.is_relative_to(host):
                return peer / path.relative_to(host)
        raise ValueError("Path has no admitted publication mapping")

    async def run(self, command, *, cwd, env, timeout):
        """Run a fixed Git observation/import under the same fresh publication attempt."""
        return await self._publication_run(command, cwd=cwd, env=env, timeout=timeout)

    async def transact(self, command, *, cwd, env, timeout, input_text):
        """Bind and deliver the complete original ref transaction through its owned endpoint."""
        return await self._publication_run(
            command, cwd=cwd, env=env, timeout=timeout, input_text=input_text
        )

    async def _publication_run(self, command, *, cwd, env, timeout, input_text=None):
        """Construct only the typed publication launch; actual source/acceptance authority is rechecked by broker admission."""
        if not command or command[0] != self.asset.path:
            raise RunConflict(
                "Publication command differs from the inspected Git asset"
            )
        launch = self.launch_type(
            self.asset,
            tuple(command[1:]),
            str(cwd),
            tuple(sorted(env.items())),
            self.view,
            input_text,
        )
        return await self._invoke(launch, timeout=timeout, input_text=input_text)


class OwnedPublicationObserver(OwnedPublicationGitExecutor):
    """Use the same owned stream/closure transport with a strictly readonly manifested Git capability."""

    launch_type = PublicationObservationLaunch

    def execution_path(self, host_path):
        """Expose only the original source, allowing historical ref inspection even when the candidate directory is gone."""
        path = Path(host_path).absolute()
        source = Path(self.view.source.workspace)
        if not path.is_relative_to(source):
            raise ValueError("Readonly observation has no candidate or writable view")
        return PEER_WORKSPACE / path.relative_to(source)
