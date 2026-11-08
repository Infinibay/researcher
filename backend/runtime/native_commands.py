"""Private command-only native peers; no user credentials or inherited config."""

import asyncio
import json
import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.runtime.codex_rpc import JsonRpcClient, RpcProtocolError, StdioRpcClient
from backend.runtime.command_jobs import OwnedCommandExecutor
from backend.runtime.contracts import WorkspaceChanged
from backend.runtime.peer_registry import PeerRegistry
from backend.runtime.workspaces import PEER_WORKSPACE

VERSION = "codex-cli 0.166.0"


@asynccontextmanager
async def broker_command_executor(*, owner, registry, lease, workspace, asset):
    """Keep job semantics while the original broker owns this dedicated RPC peer."""
    peer_id = await asyncio.to_thread(registry.prepare, lease, "command")
    rpc = JsonRpcClient(
        owner.command(
            registry, peer_id, operation_key="command-" + peer_id, asset=asset
        ),
        request_timeout=10,
        max_messages=512,
    )
    async with OwnedCommandExecutor(
        rpc,
        journal=registry.runs,
        workspace=workspace,
        lease=lease,
        peer_id=peer_id,
        execution_workspace=PEER_WORKSPACE,
    ) as worker:
        yield worker


DISABLED = (
    "plugins",
    "apps",
    "shell_tool",
    "unified_exec",
    "view_image",
    "in_app_browser",
    "in_app_chat",
    "multi_agent",
    "tool_suggest",
    "workspace_dependencies",
    "shell_snapshot",
    "sleep_tool",
)


def _toml(value):
    """Encode scalar configuration values with JSON literals and nested mappings with TOML inline-table syntax."""
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(json.dumps(k) + "=" + _toml(v) for k, v in value.items())
            + "}"
        )
    return json.dumps(value)


def _version(binary, env):
    """Read the selected native binary version under the supplied environment with a five-second subprocess deadline."""
    return subprocess.check_output(
        [str(binary), "--version"], text=True, timeout=5, env=env
    ).strip()


@asynccontextmanager
async def command_executor(
    *,
    journal,
    lease,
    workspace: Path,
    control_root: Path,
    codex_binary: Path | None = None,
    readable_toolchains: tuple[Path, ...] = (),
    workspace_access: str = "write",
):
    """Scope commands to a host-selected workspace and explicit toolchain roots.

    The model cannot choose control paths or filesystem grants. Persisted jobs
    always select this named profile, never the user's configured defaults.
    """
    if workspace_access not in ("read", "write"):
        raise ValueError("Host must select read or write workspace access")
    workspace = workspace.resolve(strict=True)
    peer_workspace = workspace
    binding = await asyncio.to_thread(
        journal.workspace_binding, lease.project_id, lease.run_id
    )
    if binding is not None:
        info = workspace.stat()
        if workspace != Path(binding.workspace) or (info.st_dev, info.st_ino) != (
            binding.device,
            binding.inode,
        ):
            raise WorkspaceChanged("Admitted directory changed before command startup")
        peer_workspace = PEER_WORKSPACE
    control_root = control_root.resolve()
    if not workspace.is_dir() or control_root.is_relative_to(workspace):
        raise ValueError("Private command control must be outside the workspace")
    binary = Path(codex_binary or shutil.which("codex") or "").resolve(strict=True)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("An explicit executable Codex binary is required")
    control_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="native-command-", dir=control_root) as name:
        home = Path(name)
        code_home = home / ".codex"
        code_home.mkdir(mode=0o700)
        temporary = home / "tmp"
        temporary.mkdir(mode=0o700)
        env = {
            "PATH": os.defpath,
            "HOME": str(home),
            "CODEX_HOME": str(code_home),
            "TMPDIR": str(temporary),
            "LANG": "C.UTF-8",
            "SHELL": "/bin/sh",
        }
        if await asyncio.to_thread(_version, binary, env) != VERSION:
            raise RpcProtocolError(
                "Unsupported native command version; no command was submitted"
            )
        filesystem = {
            ":minimal": "read",
            ":workspace_roots": workspace_access,
            str(binary): "read",
            str(temporary): "write",
        }
        for path in readable_toolchains:
            path = path.resolve(strict=True)
            if (
                path == Path(path.anchor)
                or path == Path.home()
                or home.is_relative_to(path)
            ):
                raise ValueError(
                    "Toolchain roots must not expose the host root, home or control directory"
                )
            filesystem[str(path)] = "read"
        profile = {
            "filesystem": filesystem,
            "workspace_roots": {str(peer_workspace): True},
            "network": {"enabled": False},
        }
        shell_environment = {
            "PATH": os.defpath,
            "HOME": str(temporary),
            "TMPDIR": str(temporary),
            "LANG": "C.UTF-8",
        }
        overrides = {
            "default_permissions": "researcher_jobs",
            "permissions": {"researcher_jobs": profile},
            "web_search": "disabled",
            "shell_environment_policy.inherit": "none",
            "shell_environment_policy.set": shell_environment,
        }
        command = [str(binary), "app-server", "--stdio", "--strict-config"]
        for feature in DISABLED:
            command += ["--disable", feature]
        for key, value in overrides.items():
            command += ["-c", key + "=" + _toml(value)]
        peers = PeerRegistry(journal)
        peer_id = await asyncio.to_thread(peers.prepare, lease, "command")
        rpc = StdioRpcClient(
            peers.command(peer_id, command),
            cwd=home,
            env=env,
            request_timeout=10,
            close_timeout=1,
            max_messages=512,
            process_group_signals=False,
        )
        async with OwnedCommandExecutor(
            rpc,
            journal=journal,
            workspace=workspace,
            lease=lease,
            peer_id=peer_id,
            execution_workspace=peer_workspace,
        ) as worker:
            config = (await rpc.request("config/read", {"includeLayers": False}))[
                "config"
            ]
            actual = (config.get("permissions") or {}).get("researcher_jobs") or {}
            fs = {
                k: v
                for k, v in (actual.get("filesystem") or {}).items()
                if v is not None
            }
            if (
                config.get("default_permissions") != "researcher_jobs"
                or fs != filesystem
                or actual.get("workspace_roots") != {str(peer_workspace): True}
                or actual.get("network", {}).get("enabled") is not False
                or config.get("shell_environment_policy", {}).get("inherit") != "none"
                or config.get("shell_environment_policy", {}).get("set")
                != shell_environment
                or any(
                    config.get("features", {}).get(flag) is not False
                    for flag in DISABLED
                )
                or config.get("mcp_servers")
            ):
                raise RpcProtocolError(
                    "Native command peer did not retain its required isolated configuration"
                )
            yield worker
