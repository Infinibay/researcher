"""Container runtime abstraction — supports Podman and Docker."""

import logging
import platform
import shlex
import shutil
import subprocess

logger = logging.getLogger(__name__)


class ContainerRuntime:
    """Abstracts differences between Podman and Docker for ephemeral sandbox containers."""

    def __init__(self, engine: str | None = None):
        if engine:
            self.cmd = engine
        else:
            self.cmd = _detect_engine()

        self.name = "podman" if "podman" in self.cmd else "docker"
        self.is_podman = self.name == "podman"
        self.host_dns = (
            "host.containers.internal" if self.is_podman else "host.docker.internal"
        )

    def run_ephemeral(
        self,
        image: str,
        command: list[str],
        *,
        name: str | None = None,
        volumes: list[str] | None = None,
        env: dict[str, str] | None = None,
        network: str = "none",
        memory: str | None = None,
        cpus: float | None = None,
        pids_limit: int | None = None,
        read_only: bool = True,
        tmpfs: list[str] | None = None,
        user: str | None = None,
        workdir: str | None = None,
        security_opts: list[str] | None = None,
        timeout: int = 300,
    ) -> tuple[str, str, int]:
        """Run an ephemeral container with --rm and return (stdout, stderr, returncode)."""
        args = [self.cmd, "run", "--rm"]

        if name:
            args.extend(["--name", name])

        args.extend(["--network", network])

        if memory:
            args.extend(["--memory", memory])
        if cpus is not None:
            args.extend(["--cpus", str(cpus)])
        if pids_limit is not None:
            args.extend(["--pids-limit", str(pids_limit)])

        if read_only:
            args.append("--read-only")
        if tmpfs:
            for t in tmpfs:
                args.extend(["--tmpfs", t])

        if user:
            args.extend(["--user", user])
        if workdir:
            args.extend(["-w", workdir])

        if security_opts:
            for opt in security_opts:
                args.extend(["--security-opt", opt])

        if volumes:
            for v in volumes:
                args.extend(["-v", v])

        if env:
            for k, val in env.items():
                args.extend(["-e", f"{k}={val}"])

        args.append(image)
        args.extend(command)

        logger.debug("Running ephemeral container: %s", shlex.join(args))

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            # Try to kill the container if it has a name
            if name:
                try:
                    subprocess.run(
                        [self.cmd, "rm", "-f", name],
                        capture_output=True,
                        timeout=10,
                    )
                except Exception:
                    pass
            return "", f"Container timed out after {timeout}s", -1

    def list_stale_containers(self, prefix: str) -> list[dict[str, str]]:
        """List exited containers whose names start with prefix."""
        args = [
            self.cmd, "ps", "-a",
            "--filter", "status=exited",
            "--format", "{{.ID}} {{.Names}}",
        ]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return []
        except Exception:
            return []

        containers = []
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                cid, cname = parts
                if cname.startswith(prefix):
                    containers.append({"id": cid, "name": cname})
        return containers

    def run_detached(
        self,
        image: str,
        *,
        name: str,
        volumes: list[str] | None = None,
        env: dict[str, str] | None = None,
        network: str = "none",
        memory: str | None = None,
        cpus: float | None = None,
        pids_limit: int | None = None,
        tmpfs: list[str] | None = None,
        workdir: str | None = None,
        security_opts: list[str] | None = None,
        userns: str | None = None,
        command: list[str] | None = None,
    ) -> str:
        """Start a container in background (-d). Returns container ID."""
        args = [self.cmd, "run", "-d", "--name", name, "--network", network]

        if memory:
            args.extend(["--memory", memory])
        if cpus is not None:
            args.extend(["--cpus", str(cpus)])
        if pids_limit is not None:
            args.extend(["--pids-limit", str(pids_limit)])
        if tmpfs:
            for t in tmpfs:
                args.extend(["--tmpfs", t])
        if workdir:
            args.extend(["-w", workdir])
        if security_opts:
            for opt in security_opts:
                args.extend(["--security-opt", opt])
        if userns:
            args.extend(["--userns", userns])
        if volumes:
            for v in volumes:
                args.extend(["-v", v])
        if env:
            for k, val in env.items():
                args.extend(["-e", f"{k}={val}"])

        args.append(image)
        if command:
            args.extend(command)

        logger.debug("Starting detached container: %s", shlex.join(args))

        result = subprocess.run(
            args, capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start container '{name}': {result.stderr.strip()}"
            )
        return result.stdout.strip()  # container ID

    def exec_command(
        self,
        container_name: str,
        command: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 300,
        stdin_data: str | None = None,
    ) -> tuple[str, str, int]:
        """Execute a command in a running container. Returns (stdout, stderr, returncode)."""
        args = [self.cmd, "exec"]

        if cwd:
            args.extend(["-w", cwd])
        if env:
            for k, val in env.items():
                args.extend(["-e", f"{k}={val}"])
        if stdin_data is not None:
            args.append("-i")

        args.append(container_name)
        args.extend(command)

        logger.debug("Exec in container %s: %s", container_name, shlex.join(command))

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin_data,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {timeout}s", -1

    def stop_container(self, name_or_id: str, timeout: int = 10) -> bool:
        """Stop a container. Returns True on success."""
        try:
            result = subprocess.run(
                [self.cmd, "stop", "-t", str(timeout), name_or_id],
                capture_output=True, timeout=timeout + 15,
            )
            if result.returncode == 0:
                # Remove after stop
                subprocess.run(
                    [self.cmd, "rm", "-f", name_or_id],
                    capture_output=True, timeout=15,
                )
                return True
            return False
        except Exception:
            return False

    def is_container_running(self, name_or_id: str) -> bool:
        """Check if a container is running."""
        try:
            result = subprocess.run(
                [self.cmd, "inspect", "--format", "{{.State.Running}}", name_or_id],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0 and result.stdout.strip().lower() == "true"
        except Exception:
            return False

    def remove_container(self, name_or_id: str) -> bool:
        """Remove a container by name or ID. Returns True on success."""
        try:
            result = subprocess.run(
                [self.cmd, "rm", "-f", name_or_id],
                capture_output=True,
                timeout=15,
            )
            return result.returncode == 0
        except Exception:
            return False


def _detect_engine() -> str:
    """Auto-detect container runtime: prefer podman, fall back to docker."""
    for candidate in ("podman", "docker"):
        if shutil.which(candidate):
            return candidate
    raise RuntimeError("No container runtime found. Install podman or docker.")


# ── Module-level singleton ──────────────────────────────────────────────────

_runtime: ContainerRuntime | None = None


def get_runtime(engine: str | None = None) -> ContainerRuntime:
    """Get the runtime singleton.

    If *engine* is provided and differs from the current singleton's engine,
    the singleton is replaced so operators can pin the runtime via settings.
    """
    global _runtime
    if _runtime is None:
        _runtime = ContainerRuntime(engine)
    elif engine and _runtime.cmd != engine:
        _runtime = ContainerRuntime(engine)
    return _runtime


def runtime_available() -> bool:
    """Check if a container runtime is available without raising."""
    try:
        _detect_engine()
        return True
    except RuntimeError:
        return False
