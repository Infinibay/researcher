"""Trusted Git invocation through original broker ownership, never a host subprocess fallback.

Each command has a witnessed launch and physically closed peer. Source and
allocation paths are explicit aliases; only the latter can be writable.
"""

import asyncio
import hashlib
from functools import partial
from pathlib import Path

from backend.runtime.development_workspace import MAX_OUTPUT_BYTES, GitResult
from backend.runtime.git_capsule import (
    PEER_ALLOCATION,
    GitAsset,
    GitLaunch,
    PrivateAllocation,
)
from backend.runtime.peer_process import PeerUncertain
from backend.runtime.workspaces import PEER_WORKSPACE


class OwnedGitExecutor:
    """Run fixed preparation Git under one original attempt's actual global process owner."""

    def __init__(self, *, owner, registry, lease, source, allocation, asset):
        """Bind host-selected source, allocation and executable before any Git operation is admitted."""
        if not isinstance(asset, GitAsset):
            raise TypeError("Git requires an inspected fixed Git asset")
        self.owner, self.registry, self.lease = owner, registry, lease
        self.source = Path(source).absolute()
        self.allocation = (
            Path(allocation).absolute() if allocation is not None else None
        )
        self.asset = asset
        self.git_binary = Path(asset.path)
        self.operations = []
        self.receipts = []
        self._sequence = 0

    def execution_path(self, host_path):
        """Map only this original source or this allocation, without assuming shared host paths."""
        path = Path(host_path).absolute()
        if path.is_relative_to(self.source):
            return PEER_WORKSPACE / path.relative_to(self.source)
        if self.allocation is not None and path.is_relative_to(self.allocation):
            return PEER_ALLOCATION / path.relative_to(self.allocation)
        raise ValueError("Path has no admitted Git execution mapping")

    async def run(self, command, *, cwd, env, timeout):
        """Collect bounded complete raw output and require actual broker closure before returning a result."""
        if not command or command[0] != self.asset.path:
            raise ValueError("Git command differs from the host-selected executable")
        run = await asyncio.to_thread(
            self.registry.runs.get, self.lease.project_id, self.lease.run_id
        )
        if run.execution_kind not in ("development", "code_review"):
            raise ValueError(
                "Git preparation requires an admitted development execution"
            )
        if run.execution_kind == "code_review" and self.allocation is not None:
            raise ValueError(
                "Review Git permits only its readonly candidate, without an allocation"
            )
        allocation = (
            PrivateAllocation.capture(self.allocation)
            if self.allocation is not None and self.allocation.exists()
            else None
        )
        launch = GitLaunch(
            self.asset,
            tuple(command[1:]),
            str(cwd),
            tuple(sorted(env.items())),
            allocation,
        )
        peer_id = await asyncio.to_thread(self.registry.prepare, self.lease, "command")
        self._sequence += 1
        endpoint = self.owner.git(
            self.registry,
            peer_id,
            operation_key=f"git-prepare-{self._sequence}",
            launch=launch,
        )
        output = error = b""
        closed = None
        try:
            async with asyncio.timeout(timeout):
                await endpoint.open(limit=65536)
                self.operations.append(endpoint._operation)

                async def capture(reader, bound):
                    """Drain a complete stream within its byte budget, never treating a truncated prefix as evidence."""
                    chunks = []
                    size = 0
                    while chunk := await reader.read(65536):
                        size += len(chunk)
                        if size > bound:
                            raise RuntimeError(
                                "Git output exceeded the complete capture budget"
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)

                output, error = await asyncio.gather(
                    capture(endpoint.stdout, MAX_OUTPUT_BYTES),
                    capture(endpoint.stderr, 65536),
                )
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    self.owner._peer_pool, partial(endpoint._raw.wait, timeout=timeout)
                )
        finally:
            # The original owner retains closure even if this caller is cancelled.
            finish = asyncio.create_task(endpoint.aclose(timeout=5))
            try:
                closed = await asyncio.shield(finish)
            except asyncio.CancelledError:
                await finish
                raise
        if not isinstance(closed, dict) or closed.get("execution_closed") is not True:
            raise PeerUncertain(
                "Git process closure was not confirmed by its original broker"
            )
        self.receipts.append(
            {
                "operation_id": endpoint._operation,
                "exit_code": closed["exit_code"],
                "stdout_sha256": hashlib.sha256(output).hexdigest(),
                "stdout_bytes": len(output),
                "stderr_preview": error[:2000].decode("utf-8", errors="replace"),
            }
        )
        return GitResult(output, closed["exit_code"], True, True)
