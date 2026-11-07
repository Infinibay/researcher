# Researcher (historically Infinibay)

A local workspace for research, investigation and software development with recoverable agent execution.

The Python distribution and commands use `researcher`; some historical names and
configuration aliases still use Infinibay. The existing
[AGPL-3.0-or-later license and copyright notice](LICENSE.md) remain unchanged.
See [dependency notices and distribution scope](THIRD_PARTY_NOTICES.md) for
generated frontend notices, license evidence and the remaining release checks.

Agents work through a configured native runtime with scoped tools, retained evidence and separate review and owner acceptance. Planning, execution, correction and publication have distinct recorded decisions.

The modernization now connects native project planning, research/development,
independent review and explicit acceptance to one configured owner service.
The terminal uses that same service; it no longer creates another agent engine
or a local model team. See [current status](docs/modernization/execution-dashboard.md)
and the [CLI/TUI migration guide](docs/modernization/terminal-owner.md). The old
flows and provider backend have been retired; historical Ollama/LLM_MODEL settings
do not configure the native subscription runtime.

## Requirements

- **Python 3.12 or 3.13** (the retained supported range; broader runtime/kernel compatibility still needs verification)
- **uv** (locked Python installation)
- **Linux C compiler and Python development headers** for the native execution-domain
  extension; source installs now build a platform-specific wheel. Its kernel path
  requires cgroup v2, `clone3(CLONE_INTO_CGROUP)`, `close_range(CLOEXEC)` and
  `cgroup.kill` (Linux 5.14 or newer). No spawn-then-migrate fallback is provided.
- **OpenSSL CLI** for ephemeral local TLS certificates in the test suite
- **Node.js 24 LTS, at least 24.15** (verified 24.22.2 in `frontend/.node-version`, npm 11.19.1)
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
npm test
npm run build
```

Frontend migration choices, browser checks and outstanding lint/security findings
are recorded in [the frontend dependency report](docs/architecture/frontend-dependencies.md).
`npm run lint` currently reports 12 existing findings; it is not a clean release gate yet.

The Python installation uses the native runtime. CrewAI, crewai-tools, LiteLLM,
Ollama and Chroma, their old tool wrappers and the `legacy` extra have been removed.
Historical database records remain readable through the scoped native interfaces;
removing these packages does not delete or automatically migrate old data.

The duplicate code index, its file/structural tools and six tree-sitter requirements
have been retired. Code discovery uses Ken; edits use owned native commands in
the private development copy. See [code operations](docs/architecture/native-code-operations.md).

Shell/Git/RAG adapters, generic model SQL and the CrewAI documentation search
wrapper have also been retired. Their native replacements and remaining migration
work are described in [adapter migration](docs/architecture/native-adapter-retirement.md).

Actual model selection belongs to the configured native runtime; see
[model configuration](docs/architecture/model-configuration.md). The former
`anthropic`, `gemini` and `legacy` extras do not enable another inference backend.
The recorded schema snapshot and migration maps document the retired tool names.

Runtime configuration must explicitly select `owned-codex-v1`; the implicit
launcher, per-agent pods and sandbox image have been retired. Existing files
and attachments are preserved. Follow the [host migration guide](docs/architecture/native-sandbox-retirement.md)
instead of copying an old runtime configuration or sandbox environment variables.

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
has migration and legacy-service failures; removing optional packages does not
establish that every test has been ported. See the
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

## Container operation

The multi-stage `Containerfile` builds the web application and installs a Python
wheel including the native extension. Python dependencies use the hashed lock
export; frontend dependencies use `npm ci`. Image bases have fixed digests, and
the final process runs as an unprivileged user with data outside the installation.

See [container setup and persistence](docs/architecture/container-operation.md)
for explicit new-database initialization, local access and repeat startup.
Native agent execution also requires the external host resources described in
the owned-runtime guide; building a service image does not provision those resources.
The historical per-agent pod settings do not configure native isolation.

Forgejo15.0.11 is pinned separately, with loopback HTTPS and explicitly selected
data/TLS directories. See [Forgejo setup, upgrade and restore](docs/architecture/forgejo-upgrade.md)
for account bootstrap, native CA/token configuration and the verified synthetic
9.0.3→15.0.11 rehearsal. Updating the manifest does not migrate a running instance.

Attachment storage defaults to `<INFINIBAY_DATA>/uploads`, with `.data` below the
working directory as the default data root. Set `INFINIBAY_UPLOAD_BASE_DIR` to keep
using an existing attachment directory after moving or reinstalling the service.
No directory is relocated automatically. `INFINIBAY_DB` selects the database
independently. [.env.example](.env.example) lists the current operation variables.

## Remaining modernization work

The [execution dashboard](docs/modernization/execution-dashboard.md) tracks the
remaining host provisioning, migration/restore, history/budget, real-model and
human evaluation, and whole-product acceptance work. Local tests and the twelve
web pilots do not establish complete acceptance of the product.

Historical provider benchmarks and the original Stop/duplicate-tool reports
remain in Git history and the modernization plan; they are not measurements of
the current native runtime. Current failures and deferred details are recorded
in the dashboard and its evidence links.

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
