"""SandboxExecutor — runs agent commands inside ephemeral containers."""

import logging
from dataclasses import dataclass
from uuid import uuid4

from backend.config.settings import settings
from backend.security.container_runtime import get_runtime, runtime_available
from backend.security.resource_limits import get_limits_for_role
from backend.security.workspace_manager import workspace_manager

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


class SandboxExecutor:
    """Execute commands inside ephemeral, resource-limited containers."""

    def __init__(self, ws_manager=None):
        self._ws_manager = ws_manager or workspace_manager

    def execute(
        self,
        command: list[str],
        agent_id: str,
        role: str = "default",
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        workspace_path: str | None = None,
    ) -> SandboxResult:
        """Run *command* in an ephemeral sandbox container.

        Parameters
        ----------
        command : list[str]
            The command to execute (already split).
        agent_id : str
            Identifies the calling agent (used for workspace + container name).
        role : str
            Agent role — determines resource limits.
        cwd : str | None
            Working directory *inside* the container.  Relative paths are
            resolved from ``/workspace``.
        env : dict | None
            Extra environment variables passed into the container.
        timeout : int | None
            Hard timeout in seconds (capped by role limits).
        workspace_path : str | None
            Host path to mount as ``/workspace`` inside the container.
            When provided, this overrides the default WorkspaceManager
            lookup — use this to mount the agent's git worktree.
        """
        if not runtime_available():
            raise RuntimeError("No container runtime available for sandbox execution")

        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
        if workspace_path is None:
            workspace_path = self._ws_manager.get_workspace(agent_id)
        limits = get_limits_for_role(role)

        effective_timeout = min(timeout, limits.timeout) if timeout else limits.timeout

        container_name = f"pabada-sandbox-{agent_id}-{uuid4().hex[:8]}"

        workdir = cwd if cwd else "/workspace"

        stdout, stderr, returncode = runtime.run_ephemeral(
            image=settings.SANDBOX_IMAGE,
            command=command,
            name=container_name,
            volumes=[f"{workspace_path}:/workspace:z"],
            env=env,
            network=settings.SANDBOX_NETWORK,
            memory=limits.memory,
            cpus=limits.cpus,
            pids_limit=limits.pids_limit,
            read_only=True,
            tmpfs=["/tmp:size=256m"],
            user="1000:1000",
            workdir=workdir,
            security_opts=["no-new-privileges", "seccomp=unconfined"],
            gpu=settings.SANDBOX_GPU_ENABLED,
            timeout=effective_timeout,
        )

        timed_out = returncode == -1 and "timed out" in stderr

        logger.debug(
            "Sandbox %s finished: exit=%d timed_out=%s cmd=%s",
            container_name, returncode, timed_out, command,
        )

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=returncode,
            timed_out=timed_out,
        )


# ── Module-level singleton ──────────────────────────────────────────────────

sandbox_executor = SandboxExecutor()
