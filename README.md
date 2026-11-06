# Infinibay

A prototype multi-agent swarm system for autonomous research, investigation, and software development — designed to run on consumer hardware with small open-weight models (14B parameters and under).

Agents collaborate through an event-driven architecture: a team lead plans work, researchers gather information, developers write code, and reviewers check quality. All orchestrated by flows that react to events in real time.

The modernization now connects native project planning, research/development,
independent review and explicit acceptance to one configured owner service.
The terminal uses that same service; it no longer creates another agent engine
or a local model team. See [current status](docs/modernization/execution-dashboard.md)
and the [CLI/TUI migration guide](docs/modernization/terminal-owner.md). Remaining
legacy flows and provider setup below are transitional; Ollama/LLM_MODEL settings
do not configure the native subscription runtime.

## Requirements

- **Python 3.12 or 3.13** (the transitional CrewAI dependency does not support 3.14)
- **uv** (locked Python installation)
- **Linux C compiler and Python development headers** for the native execution-domain
  extension; source installs now build a platform-specific wheel. Its kernel path
  requires cgroup v2, `clone3(CLONE_INTO_CGROUP)`, `close_range(CLOEXEC)` and
  `cgroup.kill` (Linux 5.14 or newer). No spawn-then-migrate fallback is provided.
- **OpenSSL CLI** for ephemeral local TLS certificates in the test suite
- **Node.js 24 LTS** (for the frontend; version in `frontend/.node-version`)
- **Podman** or **Docker** only for the retained Forgejo/container deployment.
- The native backend uses the separately configured Codex toolchain, subscription
  authentication and the required published `ken-rank` installation. See
  [owned runtime setup](docs/architecture/owned-product-runtime.md).

## Reproducible development setup

```bash
uv sync --locked
uv run --locked pytest backend/tests/api/test_startup.py backend/tests/cli/test_bootstrap.py
cd frontend
npm ci
npm run build
```

The Python install defaults to the native runtime. CrewAI, crewai-tools, LiteLLM,
Ollama, Chroma and the old tree-sitter stack are optional historical readers:

```bash
# Only when inspecting old tool schemas or running the historical test corpus:
uv sync --locked --extra legacy
```

This extra does not enable an inference backend. Old provider calls are retired;
actual model selection belongs to the configured native runtime. The former
`anthropic` and `gemini` extras are no longer advertised. The old role catalogue
and constructors have been removed; remaining individual legacy readers still
require their optional dependencies. Native database/API/CLI operations need none
of those packages.

Optional library documentation uses the native Context7 source tools. Set
`CONTEXT7_API_KEY` on the server; the historical `INFINIBAY_CONTEXT7_API_KEY`
name is also accepted. Its provider quota is separate from the OpenAI subscription.
No extra package is needed. See [configuration, tools and evidence limits](docs/architecture/context7-sources.md).

Optional advanced page capture uses `researcher_capture_spider` with the server's
`SPIDER_API_KEY` (or historical `INFINIBAY_SPIDER_API_KEY`). `SPIDER_MAX_CREDITS`
sets its per-request provider credit ceiling, default 100. This uses Spider's
separate quota. The old `spider` extra and its SDK are removed; no SDK is required.
See [Spider setup and capture limits](docs/architecture/spider-sources.md).

The commands above run native smoke checks. The full historical test corpus still
has migration failures and expects the optional legacy readers; it is not a claim
that every test has already been ported. See the
[native installation evidence](docs/modernization/native-installation-results.json).

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

The packaged research MCP uses the same scoped business definitions and standard
MCP SDK as the native runtime. After installing the project, its host can launch:

```bash
researcher-mcp
```

For a source checkout, a separate locked script environment is also supported:

```bash
uv run --locked --script scripts/researcher_mcp_server.py
```

Its admitting host supplies `RESEARCHER_API_URL` (numeric loopback HTTP, default
`http://127.0.0.1:8000`) and a short-lived `RESEARCHER_TOOL_TOKEN`;
project/task/actor are bound by that grant. It exposes research business tools,
not SQL or grant issuance. Configure the mandatory Ken MCP separately through
the native host. An API key, old `INFINIBAY_*` actor labels or a syntactically
valid token do not authorize a call. This command does not start a host or mint
grants. `--help` works without credentials or storage.

`scripts/infinibay_mcp_server.py` now launches this same research gateway and
prints a migration notice on stderr. Its old task approval, role messaging, SQL
and PR tools are retired. Development, planning and formal review retain their
host-selected native catalogues; acceptance and publication use explicit owner
operations. See [the MCP migration](docs/architecture/native-mcp-entry.md) for
the outcome mapping and verification limits. Remaining Git/startup consumers
and legacy tests still need migration.

Tasks can reuse selected older files, an exact prior native candidate, or a
registered historical branch plus its full commit SHA as data for a fresh author.
Branch changes are captured by the existing owned preparation before the model
turn; a moving name or historical `approved` label cannot grant acceptance.
Checks, distinct review and owner acceptance/publication run again. See
[exact branch input](docs/architecture/prior-branch-input.md) for scope and limits.

Set `INFINIBAY_DB` to select a database explicitly. Without an override, an
existing recognized database is reused; multiple databases require a choice.
A new workspace defaults to `.data/infinibay.db`. Serving requires an initialized database; CLI/TUI connect to that serving
owner and do not bootstrap a local database. Create a NEW installation explicitly with
`uv run --locked researcher-bootstrap init-db --database /absolute/path/source.db`,
then select that same path with `INFINIBAY_DB`. An absent or empty existing database
requires investigation/restore; startup does not recreate or move it.
See [explicit initialization and recovery limits](docs/modernization/bootstrap.md).

Implementation status for the modernization is recorded in
[the execution ledger](docs/modernization/progress.md).

## Quick Start

```bash
# From this checkout: install the locked native Python environment
uv sync --locked

# For a NEW installation only; preserve existing deployments for migration/restore
export INFINIBAY_DB="${XDG_STATE_HOME:-$HOME/.local/state}/researcher/source.db"
mkdir -p "$(dirname "$INFINIBAY_DB")"
uv run --locked researcher-bootstrap init-db --database "$INFINIBAY_DB"

# Configure INFINIBAY_RUNTIME_CONFIG using the owned-runtime guide, then serve
uv run --locked python -m backend.api.run

# In another terminal, start the frontend
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

After installing Python and frontend dependencies explicitly, `./start.sh` starts
both services on loopback. It uses `.venv/bin/python`, or the executable selected
by `RESEARCHER_PYTHON`; `RESEARCHER_NODE` can select the installed Node executable.
It does not install packages, pull models, provision Forgejo or execute `.env`.
Export configuration in the host environment before launching.

```bash
./start.sh --check                 # Read-only prerequisite check, no services
./start.sh                        # API8000 + web5173; Ctrl+C closes these children
researcher-start --api-only        # Installed command, no frontend/Node needed
researcher-start --api-only --port 8100
```

The frontend proxy currently targets API port8000; alternate ports require
`--api-only`. Missing or empty databases are refused before services start. With
no `INFINIBAY_RUNTIME_CONFIG`, the launcher explicitly reports inspection mode:
owner history/read operations are available, native generation/admission is not.
Prerequisite checks do not verify account login, Ken availability or native host
resources; the API lifespan validates actual runtime configuration. See
[the startup contract](docs/architecture/native-startup.md).

Configure the actual Codex account/model, Ken installation, source workspace and
owned process resources using [the native runtime guide](docs/architecture/owned-product-runtime.md).
Python dependency installation does not provision these host components or restore
an existing deployment. The initialization command refuses existing files; use
migration/restore for existing data. Forgejo/container provisioning is a separate
operator action; the normal startup command does not configure these services.

Open http://localhost:5173 in your browser.

Use **Modelos** in the workspace header to set a global, project or project-agent
model and reasoning effort. Changes apply to new attempts; current attempts retain
their original selection. Codex checks the selected pair against its account
catalog before dispatch and does not substitute another model or billed provider.
See [model configuration](docs/architecture/model-configuration.md).

## Historical container deployment

The following container settings describe the retained deployment being migrated.
The native runtime uses the owned-process and authority configuration documented
above.

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
