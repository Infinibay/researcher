# Security Architecture

## Overview

PABADA uses ephemeral container sandboxing to isolate agent command execution. When an agent tool calls `ExecuteCommandTool`, the command runs inside a short-lived container that is destroyed immediately after execution.

```mermaid
graph TD
    A[FastAPI Backend<br/>Container - pabada:latest] --> B[CrewAI Flows<br/>in-process]
    B --> C[Agent Tools]
    C --> D{ExecuteCommandTool}
    D -->|SANDBOX_ENABLED=True| E[SandboxExecutor]
    D -->|SANDBOX_ENABLED=False| F[subprocess directo]
    E --> G[Ephemeral Container<br/>pabada-sandbox:latest<br/>--rm --network none<br/>--memory --cpus]
    G --> H[/research/workspaces/agent_id/<br/>Isolated volume per agent]
    I[CleanupManager<br/>daemon thread] -->|every 5 min| J[Remove exited containers<br/>+ orphaned workspaces]
```

## Old vs. New Isolation Model

| Aspect | Old system | New system |
|---|---|---|
| Agent execution | One container per agent (claude-code/opencode inside) | In-process CrewAI agents calling LLM APIs |
| Command isolation | Inherent — agent IS the container | Explicit — `SandboxExecutor` spawns ephemeral containers per command |
| Lifecycle | Container lives for the agent's lifetime | Container lives for a single command execution (`--rm`) |
| Networking | Agents share a pod/network | Sandbox containers use `--network none` by default |

## Sandbox Image (`pabada-sandbox:latest`)

Built from `Containerfile.sandbox`. Includes tools agents commonly need:

- **Languages**: Python 3.12, Node.js
- **Build tools**: make, cargo (if added), git
- **Python packages**: numpy, pandas, pytest, ruff, mypy, fpdf2, openpyxl, requests, beautifulsoup4
- **Utilities**: curl, wget, tar, unzip
- **LaTeX**: texlive-base, texlive-extra, latexmk

The image runs as non-root user `agent` (UID 1000) by default.

### Building the images

```bash
# Backend image
podman build -t pabada:latest -f Containerfile .
# or: docker build -t pabada:latest -f Containerfile .

# Sandbox image
podman build -t pabada-sandbox:latest -f Containerfile.sandbox .
# or: docker build -t pabada-sandbox:latest -f Containerfile.sandbox .
```

## Resource Limits by Role

Each agent role has specific resource constraints enforced at the container level:

| Role | Memory | CPUs | PIDs | Timeout |
|---|---|---|---|---|
| `developer` | 2g | 2.0 | 256 | 300s |
| `researcher` | 4g | 4.0 | 512 | 600s |
| `code_reviewer` | 1g | 1.0 | 128 | 120s |
| `research_reviewer` | 1g | 1.0 | 128 | 120s |
| `team_lead` | 512m | 0.5 | 64 | 60s |
| `project_lead` | 512m | 0.5 | 64 | 60s |
| `default` | 1g | 1.0 | 128 | 120s |

Defined in `backend/security/resource_limits.py`.

## Workspace per Agent

Each agent gets an isolated workspace directory at `/research/workspaces/{agent_id}/`.

- Created on first command execution via `WorkspaceManager.get_workspace()`
- Mounted into sandbox containers as `-v {path}:/workspace:z`
- Permissions: `0o755`
- Cleaned up by `CleanupManager` when the agent status is `idle`, `completed`, or `failed` in the roster

## Security Flags

Every sandbox container runs with these flags:

| Flag | Purpose |
|---|---|
| `--rm` | Auto-remove container on exit — no leftover state |
| `--network none` | No network access — agents use their own web/search tools for internet |
| `--read-only` | Root filesystem is read-only; only `/workspace` and `/tmp` are writable |
| `--tmpfs /tmp:size=256m` | Writable temp directory with size cap |
| `--security-opt no-new-privileges` | Prevents privilege escalation inside the container |
| `--security-opt seccomp=unconfined` | Required for git and python to function correctly |
| `--user 1000:1000` | Runs as non-root user |
| `--memory`, `--cpus`, `--pids-limit` | Resource caps per role (see table above) |

## Automatic Cleanup

`CleanupManager` runs as a daemon thread started in `create_app()`:

1. **Stale containers**: Every `CLEANUP_INTERVAL_SECONDS` (default: 300s), scans for exited containers with the `pabada-sandbox-` prefix and removes them.
2. **Orphaned workspaces**: When `cleanup_all_stale()` is called, checks the roster for agents in `idle`/`completed`/`failed` status and removes their workspace directories.

## Fallback Mode

When `SANDBOX_ENABLED=True` but no container runtime (podman/docker) is detected:

- `ExecuteCommandTool` logs a warning and falls back to direct `subprocess` execution
- The existing whitelist + dangerous-character validation still applies
- This is the expected mode during local development without containers

When `SANDBOX_ENABLED=False`:

- Commands execute directly via `subprocess` without any restrictions
- Only appropriate for trusted development environments

## Configuration

All sandbox settings are in `backend/config/settings.py` with `PABADA_` env prefix:

| Setting | Default | Description |
|---|---|---|
| `SANDBOX_ENABLED` | `True` | Master switch for all sandboxing |
| `SANDBOX_IMAGE` | `pabada-sandbox:latest` | Container image for command execution |
| `SANDBOX_CONTAINER_RUNTIME` | `None` (auto-detect) | Force `podman` or `docker` |
| `WORKSPACE_BASE_DIR` | `/research/workspaces` | Root directory for agent workspaces |
| `CLEANUP_INTERVAL_SECONDS` | `300` | Interval for periodic container cleanup |
| `SANDBOX_NETWORK` | `none` | Container network mode |
