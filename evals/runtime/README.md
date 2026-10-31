# Runtime comparison fixtures

These fixtures contain an **intentional invoice defect** and two tests expected
to fail before the correction scenario. They are synthetic, not product source
or a financial policy. Common backend tests never launch a model.

`manifest.json` preserves candidate versions, original source hashes, prompts,
bounds and evaluation limitations. Result excerpts live in
`docs/modernization/*-evidence.json`; the narrative and failed trial analysis are
in `docs/modernization/runtime-evaluation.md`.

For a manual trial, copy the fixture into a new temporary Git repository outside
product data, record a baseline commit, then prepare that exact directory with
published `ken-rank==0.18.0` (`ken retrieval prepare --path <fixture> --json`).
Initialize one candidate process per workspace. Check subscription auth and Ken
readiness before submitting the manifest's prompt. Disable unrelated MCP/apps,
remove inherited API keys/base URL overrides, and enforce the manifest's bounds
outside the model. Infinidev needs explicit MCP prewarm in its web harness.

The original code/control probes remain in the plan's scratch workspace. The
attachment/web → finding → report scenario now has an explicit portable runner,
`run_research.py`, with its separate `research_manifest.json` and the same prompt
for both candidates. This is not a completed benchmark or a prompt experiment.
Never run the slow tool or a model task as part of the common test suite.

From the managed project environment, install published `ken-rank==0.18.0` into
an isolated tool environment and pass its absolute executable path. Codex CLI
0.166.0 must already have a managed ChatGPT login. Run one candidate at a time:

```sh
.venv/bin/python evals/runtime/run_research.py --live --candidate codex \
  --ken-command /absolute/path/to/ken

.venv/bin/python evals/runtime/run_research.py --live --candidate infinidev \
  --ken-command /absolute/path/to/ken \
  --infinidev-python /absolute/path/to/isolated-infinidev-env/bin/python
```

For Infinidev, the supplied environment must contain the evaluated 0.30.0
release. Its test shim prewarms both MCPs, enforces the subscription completion
route and supplies the business grant privately to the MCP child. It does not
modify Infinidev source or inherit a paid provider key. Runtime-version checks
occur before the model task; `--live` is mandatory. Output defaults to an ignored
`.researcher/evaluations/<unique-trial>/` directory, with manifest, native
events, temporary SQLite database, logs and result. Keep failed trials too.

The runner creates synthetic projects and files, runs the real backend and
locked business MCP, and serializes campaigns under an OS lock. Each trial has
a 180-second task wall deadline, a 90-second no-tool-progress fuse, one native
turn, 25 observed tool items and 350,000 observed tokens. Infinidev also has a
32-completion-call fuse. These fuses do not imply equivalent internal request
counts or known remaining quota. Unreported token usage stays unknown.

The host independently checks persisted sources/citations, provisional finding,
draft report, numeric markers and the actual artifact HTTP response. It also
checks tracked file hashes, Git index/HEAD and unexpected output paths. Known
runtime state (`.ken/`, `.infinidev/`, `.mcp.json`) is excluded from the output
check. These checks prove final fixture state, not OS isolation or absence of
transient effects. Human explanation quality, rendered `/reports`, full task
acceptance and all product-level cancellation/recovery remain separate gates.

Do not restart a live trial after an observation timeout. Re-poll its process
handle, inspect the same unique trial and reconcile terminal state first. Reuse
an operation key after an uncertain business-tool receipt rather than creating
a fresh key. At teardown the runner revokes the business grant and reaps its
owned server processes. Raw trial directories may contain native conversation
data; durable excerpts belong in `docs/modernization/` after inspection.

For code corrections, independently run `python -B -m unittest -v` and inspect
Git diff against the baseline; model claims are not verification. For
cancellation, `slow_tool.py` deliberately writes a marker before a 60-second wait
and a delayed effect. A PID inside that execution environment is not necessarily
a host PID. Correlate native identity and terminal status, retire the connection
and reconcile before another attempt; never replay solely because observation
expired. Researcher's product-level cancellation acceptance is broader than
this fixture.

The command-only lifecycle probe does not submit model turns or need an account:

```sh
.venv/bin/python evals/runtime/run_commands.py --live --peer-loss --db-contention
```

It uses the installed Codex CLI 0.166.0 command API in private account-free peers,
real SQLite migrations and synthetic workspaces. The optional fault cases kill
only its directly owned RPC process and hold its temporary DB writer. It checks
physical Stop before DB unlock, detached-child readiness, other-owner survival,
cross-project access denial, disabled sockets and uncertain-result fencing.
Results remain under a unique ignored evaluation directory; do not replay a
live or uncertain job. See `docs/architecture/owned-commands.md` for scope.

Product artifact read-back now uses a separate paired owner session in the
backend runner. Its random code lives in a private temporary control directory,
never in candidate prompts/configuration or the business MCP environment.
Business grants remain restricted to `research-tools`; do not solve legacy
client authentication by passing the human cookie into a model process.
