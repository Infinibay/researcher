"""PodManager — manages persistent per-agent containers (pods).

Each agent gets a long-lived container where file, git, and shell
operations execute via `podman/docker exec`. This replaces the
ephemeral container-per-command model with a persistent pod that
starts once and stays alive for the agent's session.
"""

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.config.settings import settings
from backend.security.container_runtime import get_runtime, runtime_available
from backend.security.resource_limits import get_limits_for_role
from backend.tools.base.db import get_db_path

logger = logging.getLogger(__name__)


@dataclass
class PodInfo:
    """Metadata about a running agent pod."""

    agent_id: str
    container_name: str
    container_id: str
    workspace_path: str
    started_at: datetime
    role: str
    workdir: str = "/workspace"  # CWD inside the container for this agent


@dataclass
class SandboxResult:
    """Result of executing a command inside a pod."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


class PodManager:
    """Manages the lifecycle of persistent agent containers.

    Thread-safe. The singleton ``pod_manager`` at module level is the
    canonical instance used by tools and agents.
    """

    def __init__(self) -> None:
        self._pods: dict[str, PodInfo] = {}
        self._lock = threading.Lock()

    def start_pod(
        self,
        agent_id: str,
        role: str,
        workspace_path: str,
        env: dict[str, str] | None = None,
        workdir: str = "/workspace",
    ) -> PodInfo:
        """Start a persistent pod for the agent (idempotent).

        If a pod already exists and is running, returns the existing PodInfo.
        If the pod exists but is stopped, removes it and creates a new one.

        *workspace_path* is the host directory mounted at ``/workspace``.
        *workdir* is the default CWD inside the container (e.g.
        ``/workspace/.worktrees/developer_1_p1`` for worktree agents).
        """
        with self._lock:
            # Reuse if already running
            if agent_id in self._pods:
                existing = self._pods[agent_id]
                runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
                if runtime.is_container_running(existing.container_name):
                    logger.debug("Pod already running for %s", agent_id)
                    return existing
                # Pod died — clean up and recreate
                logger.warning("Pod for %s is not running, recreating", agent_id)
                runtime.remove_container(existing.container_name)
                del self._pods[agent_id]

            return self._create_pod(agent_id, role, workspace_path, env, workdir)

    def _create_pod(
        self,
        agent_id: str,
        role: str,
        workspace_path: str,
        env: dict[str, str] | None,
        workdir: str = "/workspace",
    ) -> PodInfo:
        """Create and start a new pod. Caller must hold self._lock."""
        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
        limits = get_limits_for_role(role)

        container_name = f"pabada-pod-{agent_id}"

        # Clean up any leftover container with the same name
        if runtime.is_container_running(container_name):
            runtime.stop_container(container_name)
        else:
            runtime.remove_container(container_name)

        # Shared artifacts volume — visible to all pods and the host
        artifacts_host_dir = os.path.join(
            os.path.dirname(os.path.abspath(get_db_path())), "artifacts"
        )
        os.makedirs(artifacts_host_dir, exist_ok=True)

        volumes = [
            f"{workspace_path}:/workspace:z",
            f"{artifacts_host_dir}:/artifacts:z",
        ]
        userns = "keep-id" if runtime.is_podman else None

        pod_env = env.copy() if env else {}

        container_id = runtime.run_detached(
            image=settings.SANDBOX_IMAGE,
            name=container_name,
            volumes=volumes,
            env=pod_env,
            network=settings.SANDBOX_NETWORK,
            memory=limits.memory,
            cpus=limits.cpus,
            pids_limit=limits.pids_limit,
            tmpfs=["/tmp:size=512m"],
            workdir="/workspace",
            security_opts=["no-new-privileges"],
            userns=userns,
            command=["sleep", "infinity"],
        )

        info = PodInfo(
            agent_id=agent_id,
            container_name=container_name,
            container_id=container_id.strip(),
            workspace_path=workspace_path,
            started_at=datetime.now(timezone.utc),
            role=role,
            workdir=workdir,
        )
        self._pods[agent_id] = info
        logger.info(
            "Started pod %s for agent %s (role=%s, workspace=%s)",
            container_name, agent_id, role, workspace_path,
        )
        return info

    def exec_in_pod(
        self,
        agent_id: str,
        command: list[str],
        cwd: str = "/workspace",
        env: dict[str, str] | None = None,
        timeout: int = 300,
        stdin_data: str | None = None,
    ) -> SandboxResult:
        """Execute a command inside the agent's pod.

        Auto-restarts the pod if it's not running (using cached PodInfo).
        """
        with self._lock:
            info = self._pods.get(agent_id)
            if info is None:
                raise RuntimeError(
                    f"No pod registered for agent '{agent_id}'. "
                    "Call start_pod() first."
                )

            runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)

            # Auto-restart if pod died
            if not runtime.is_container_running(info.container_name):
                logger.warning("Pod for %s died, restarting", agent_id)
                runtime.remove_container(info.container_name)
                del self._pods[agent_id]
                info = self._create_pod(
                    agent_id, info.role, info.workspace_path, env, info.workdir,
                )

        # Execute outside the lock to avoid blocking other pods
        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
        stdout, stderr, returncode = runtime.exec_command(
            info.container_name,
            command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            stdin_data=stdin_data,
        )

        timed_out = returncode == -1 and "timed out" in stderr

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=returncode,
            timed_out=timed_out,
        )

    def stop_pod(self, agent_id: str) -> bool:
        """Stop and remove the pod for an agent. Returns True if stopped."""
        with self._lock:
            info = self._pods.pop(agent_id, None)
        if info is None:
            return False

        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
        stopped = runtime.stop_container(info.container_name)
        if stopped:
            logger.info("Stopped pod %s for agent %s", info.container_name, agent_id)
        else:
            logger.warning("Failed to stop pod %s for agent %s", info.container_name, agent_id)
        return stopped

    def get_workdir(self, agent_id: str) -> str:
        """Return the default working directory inside the pod."""
        with self._lock:
            info = self._pods.get(agent_id)
        return info.workdir if info else "/workspace"

    def is_pod_running(self, agent_id: str) -> bool:
        """Check if the pod for an agent is running."""
        with self._lock:
            info = self._pods.get(agent_id)
        if info is None:
            return False

        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
        return runtime.is_container_running(info.container_name)

    def list_pods(self) -> list[PodInfo]:
        """Return a snapshot of all tracked pods."""
        with self._lock:
            return list(self._pods.values())

    def stop_all(self) -> int:
        """Stop all tracked pods. Returns count stopped."""
        with self._lock:
            pods = list(self._pods.items())

        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)
        stopped = 0
        for agent_id, info in pods:
            if runtime.stop_container(info.container_name):
                stopped += 1

        with self._lock:
            self._pods.clear()

        logger.info("Stopped %d pods", stopped)
        return stopped


# Module-level singleton
pod_manager = PodManager()
