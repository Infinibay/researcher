"""PodManager — manages persistent per-agent containers (pods).

Each agent gets a long-lived container where file, git, and shell
operations execute via `podman/docker exec`. This replaces the
ephemeral container-per-command model with a persistent pod that
starts once and stays alive for the agent's session.
"""

import json
import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

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
        userns = None

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
            gpu=settings.SANDBOX_GPU_ENABLED,
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

        # Set up Claude Code CLI if agent engine requires it
        if settings.AGENT_ENGINE == "claude_code":
            self._setup_claude_code(container_name, runtime)

        return info

    def _setup_claude_code(
        self, container_name: str, runtime: object,
    ) -> None:
        """Copy Claude Code credentials and settings into a pod.

        Called automatically when ``AGENT_ENGINE=claude_code``.
        """
        # Resolve credentials path
        creds_path = Path(settings.CLAUDE_CODE_CREDENTIALS_PATH).expanduser()
        if not creds_path.exists():
            logger.warning(
                "Claude Code credentials not found at %s — "
                "agent may fail to authenticate", creds_path,
            )
            return

        # Copy credentials into the pod
        try:
            subprocess.run(
                [runtime.cmd, "cp", str(creds_path),
                 f"{container_name}:/root/.claude/.credentials.json"],
                capture_output=True, text=True, timeout=15, check=True,
            )
        except Exception:
            logger.warning("Failed to copy credentials to %s", container_name, exc_info=True)
            return

        # Also copy the parent .claude directory files if they exist
        claude_dir = creds_path.parent
        for fname in ("settings.json", "statsig.json"):
            fpath = claude_dir / fname
            if fpath.exists():
                try:
                    subprocess.run(
                        [runtime.cmd, "cp", str(fpath),
                         f"{container_name}:/root/.claude/{fname}"],
                        capture_output=True, text=True, timeout=15, check=True,
                    )
                except Exception:
                    pass

        # Generate minimal settings.json with context7 + pabada MCP servers
        claude_settings = {
            "model": settings.CLAUDE_CODE_MODEL,
            "permissions": {
                "allow": [
                    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
                    "WebSearch", "WebFetch",
                    "mcp__plugin_context7_context7__resolve-library-id",
                    "mcp__plugin_context7_context7__get-library-docs",
                    "mcp__pabada__task-get",
                    "mcp__pabada__task-list",
                    "mcp__pabada__task-create",
                    "mcp__pabada__task-update-status",
                    "mcp__pabada__task-take",
                    "mcp__pabada__task-add-comment",
                    "mcp__pabada__task-set-dependencies",
                    "mcp__pabada__task-approve",
                    "mcp__pabada__task-reject",
                    "mcp__pabada__epic-create",
                    "mcp__pabada__milestone-create",
                    "mcp__pabada__chat-send",
                    "mcp__pabada__chat-read",
                    "mcp__pabada__chat-ask-team-lead",
                    "mcp__pabada__chat-ask-project-lead",
                    "mcp__pabada__finding-record",
                    "mcp__pabada__finding-read",
                    "mcp__pabada__finding-validate",
                    "mcp__pabada__finding-reject",
                    "mcp__pabada__wiki-read",
                    "mcp__pabada__wiki-write",
                    "mcp__pabada__query-database",
                    "mcp__pabada__create-pr",
                    "mcp__pabada__session-save",
                    "mcp__pabada__session-load",
                ],
                "deny": [],
            },
            "mcpServers": {
                "context7": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@upstash/context7-mcp"],
                },
                "pabada": {
                    "type": "stdio",
                    "command": "python3",
                    "args": ["/usr/local/bin/pabada-mcp"],
                },
            },
        }
        settings_json = json.dumps(claude_settings, indent=2)

        # Write via exec (avoids temp file on host)
        try:
            runtime.exec_command(
                container_name,
                ["sh", "-c", f"cat > /root/.claude/settings.json << 'PABADA_EOF'\n{settings_json}\nPABADA_EOF"],
                cwd="/root",
                timeout=10,
            )
        except Exception:
            logger.warning("Failed to write Claude settings to %s", container_name, exc_info=True)

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
