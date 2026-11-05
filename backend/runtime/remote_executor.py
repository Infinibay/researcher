"""Trusted remote Git executor through the original broker, reserving writes at their actual transport boundary."""

import asyncio

from backend.runtime.contracts import RunConflict
from backend.runtime.publication_executor import OwnedPublicationGitExecutor
from backend.runtime.remote_capsule import RemoteGitLaunch
from backend.runtime.remote_publication import RemoteEffectUncertain
from backend.runtime.remote_runtime import RemotePublications


class OwnedRemoteGitExecutor(OwnedPublicationGitExecutor):
    """Reuse complete owned Git transport/closure without a subprocess fallback or model-visible PAT."""

    def __init__(self, *, intent, config, client, effect_name, **kwargs):
        """Pin original remote protocol and actual operator credential configuration before creating any endpoint."""
        super().__init__(**kwargs)
        self.intent, self.config, self.client, self.effect_name = (
            intent,
            config,
            client,
            effect_name,
        )
        self._operation_prefix = "git-remote"

    async def verify_remote(self, remote):
        """Check numeric server identity through the same owned attempt's bounded authenticated HTTP client."""
        return await self.client.verify_remote(remote)

    async def _publication_run(self, command, *, cwd, env, timeout, input_text=None):
        """Authorize only exact remote/profile commands and reserve the original write once after all readonly preflight work."""
        if not command or command[0] != self.asset.path:
            raise RunConflict("Remote Git asset differs from its inspected program")
        launch = RemoteGitLaunch(
            self.asset,
            tuple(command[1:]),
            str(cwd),
            tuple(sorted(env.items())),
            self.view,
            input_text,
            intent=self.intent,
            transport_identity=self.config.identity,
        )
        if launch.is_write:
            reservation = await asyncio.to_thread(
                RemotePublications(self.registry.runs).issue,
                self.lease,
                self.effect_name,
            )
            if not reservation["dispatch"]:
                raise RemoteEffectUncertain(
                    "Original remote write was already issued; observe it without another push"
                )
        return await self._invoke(launch, timeout=timeout)
