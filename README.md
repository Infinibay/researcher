# Infinibay

A prototype multi-agent swarm system for autonomous research, investigation, and software development — designed to run on consumer hardware with small open-weight models (14B parameters and under).

Agents collaborate through an event-driven architecture: a team lead plans work, researchers gather information, developers write code, and reviewers check quality. All orchestrated by flows that react to events in real time.

## Requirements

- **Python 3.12 or 3.13** (the transitional CrewAI dependency does not support 3.14)
- **uv** (locked Python installation)
- **Linux C compiler and Python development headers** for the native execution-domain
  extension; source installs now build a platform-specific wheel. Its kernel path
  requires cgroup v2, `clone3(CLONE_INTO_CGROUP)`, `close_range(CLOEXEC)` and
  `cgroup.kill` (Linux 5.14 or newer). No spawn-then-migrate fallback is provided.
- **OpenSSL CLI** for ephemeral local TLS certificates in the test suite
- **Node.js 24 LTS** (for the frontend; version in `frontend/.node-version`)
- **Podman** or **Docker** (for sandbox and Forgejo)
- **Ollama** (for local LLM inference)
- A machine with at least 16GB RAM and a GPU with 12GB+ VRAM for 14B models

## Reproducible development setup

```bash
uv sync --locked
uv run --locked pytest
cd frontend
npm ci
npm run build
```

The test command blocks external sockets and limits each test to 20 seconds.
Real execution-domain tests create and remove unique children under the test
runner's delegated cgroup; they skip when that delegation is unavailable. Those
tests do not provision a production actor domain or enable mutable tools. See
[the execution-domain contract](docs/architecture/execution-domain.md).
Real-provider tests must run separately with explicit limits; ordinary tests do
not require provider credentials. The current baseline still contains known
failures, listed in [the baseline report](docs/modernization/baseline.md).

Declare Python dependencies in `pyproject.toml`, regenerate `uv.lock`, then
export the compatibility file instead of editing it by hand:

```bash
uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt
```

The standalone MCP server has its own locked script environment:

```bash
uv run --locked --script scripts/infinibay_mcp_server.py
```

The new scoped research MCP has a separate locked script environment:

```bash
uv run --locked --script scripts/researcher_mcp_server.py
```

Its host supplies `RESEARCHER_API_URL` and a short-lived `RESEARCHER_TOOL_TOKEN`;
project/task/actor are bound by that grant. It exposes research business tools,
not SQL or grant issuance. See [the research slice](docs/architecture/research-slice.md)
for tested behavior, limits and pending integration. The default product engine
is still being migrated; the candidate runtime is not yet the default.

Set `INFINIBAY_DB` to select a database explicitly. Without an override, an
existing recognized database is reused; multiple databases require a choice.
A new workspace defaults to `.data/infinibay.db`. Serving and CLI startup require an
initialized database: create a NEW installation explicitly with
`uv run --locked researcher-bootstrap init-db --database /absolute/path/source.db`,
then select that same path with `INFINIBAY_DB`. An absent or empty existing database
requires investigation/restore; startup does not recreate or move it.
See [explicit initialization and recovery limits](docs/modernization/bootstrap.md).

Implementation status for the modernization is recorded in
[the execution ledger](docs/modernization/progress.md).

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/your-org/infinibay.git
cd infinibay

# 2. Copy and edit the environment config
cp .env.example .env
# Edit .env — set your LLM model and API key (or use Ollama defaults)

# 3. For a NEW installation only: initialize the selected database
uv sync --locked
export INFINIBAY_DB="${XDG_STATE_HOME:-$HOME/.local/state}/researcher/source.db"
uv run --locked researcher-bootstrap init-db --database "$INFINIBAY_DB"

# 4. Start the legacy development stack (runtime migration is still in progress)
./start.sh
```

`start.sh` checks the initialized database before external setup, installs the locked
Python environment, migrates recognized data and starts the legacy Forgejo/backend/
frontend stack. Its provider/Forgejo lifecycle is still being modernized. For the
Codex subscription profile, follow [the owned runtime configuration](docs/architecture/owned-product-runtime.md).

Open http://localhost:5173 in your browser.

## Sandbox

When `INFINIBAY_SANDBOX_ENABLED=true`, each agent runs its tools inside an isolated Podman/Docker pod. This means file operations, shell commands, and git operations happen in a container — not on your host machine.

- Each agent gets its own persistent pod with a dedicated workspace
- Pods are created on demand and cleaned up when idle
- GPU passthrough is supported via `INFINIBAY_SANDBOX_GPU_ENABLED=true` (requires nvidia-container-toolkit)

Set `INFINIBAY_SANDBOX_ENABLED=false` for local development without containers.

## Tested Models

The system is designed for small models. Here's what works:

| Model | Speed | Tool Calling | Research | Notes |
|---|---|---|---|---|
| **nemotron-3-nano:30b** | Very fast | Excellent | Very good | Best throughput, follows tool calls reliably |
| **qwen3.5:27b** | Medium | Excellent | Excellent | Best overall quality, very few hallucinations |
| **gpt-oss:20b** | Very fast | Very good | Good | Excellent throughput, some tool hallucinations |
| **glm-4.7-flash:128k** | Medium | Very good | Good | Strong orchestration |
| **ministral-3:14b** | Very fast | Good | Very good | Medium orchestration |

### Closed-source models

The system works with Gemini, OpenAI, and Anthropic APIs — and they perform well. However, **token consumption is extreme** because the prompts are very explicit and detailed (necessary for small open-weight models to follow instructions reliably). Keep this in mind for cost.

## Configuration

All config uses the `INFINIBAY_` prefix. The essential variables:

```bash
INFINIBAY_LLM_MODEL=ollama_chat/nemotron-3-nano:30b   # LiteLLM format
INFINIBAY_LLM_API_KEY=not-needed               # Only needed for cloud providers
INFINIBAY_LLM_BASE_URL=http://localhost:11434/  # Only for Ollama/custom endpoints
INFINIBAY_SANDBOX_ENABLED=true
```

Embedding provider is auto-detected from your LLM provider. Override with `INFINIBAY_EMBEDDING_PROVIDER` if needed.

See `.env.example` for all options.

## Known Issues

- **UI bugs**: the Stop button doesn't actually stop agents — you need to `Ctrl+C` the backend process.
- **Duplicate tool execution**: some tools (particularly `send_message` and `add_comment`) occasionally fire twice in a single agent step.

## Contributing

This is an early prototype. The best way to contribute right now is:

- Trying it out and reporting bugs
- Sharing feedback on agent behavior
- Suggesting ideas for new capabilities or workflow improvements

Open an issue or start a discussion.

## License

See [LICENSE.md](LICENSE.md).

## Local web access during modernization

The backend now requires a local owner session for product HTTP/WS access.
Start it with `uv run --locked python -m backend.api.run`. Startup prints the
path of a private pairing-code file outside the workspace; enter that code in
the web access form. It is independent from the managed OpenAI subscription.
Restarting requires pairing again. See [local access](docs/architecture/local-owner-access.md)
for permissions, development origins and the separation from business MCP grants.
Legacy clients must migrate; do not give agents the owner's browser cookie.

With the pinned Node 24 environment, `npm test --prefix frontend` checks the
owner HTTP transport and retired WebSocket handling without a browser or model.
`uv run --locked python evals/security/run_local_access.py --live` explicitly
starts temporary local servers for a zero-model HTTP/WS protocol probe.
