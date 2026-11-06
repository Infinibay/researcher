# Installed service startup

`researcher-start` runs already-installed services. `start.sh` is a thin source
checkout launcher that chooses the installed Python interpreter, changes to the
checkout and delegates to the same command implementation. Setup remains in
explicit `uv sync --locked`, frontend `npm ci` and `researcher-bootstrap` actions.

Normal startup does not source shell `.env`, create containers/users/tokens,
configure providers, pull models, install dependencies or consult `.pids`.
Export the actual host configuration before invoking it. Model/subscription and
the mandatory Ken MCP remain in the native runtime configuration and admission
path, not inferred from an old provider setting or a successful prerequisite check.

The launcher resolves the database using the shared project resolver and opens
it read-only to recognize existing migration history before starting anything.
Missing, empty, ambiguous or unrecognized state is refused with the explicit
new-installation bootstrap command. This check does not upgrade or repair data.
Actual serving migrations and runtime/resource validation stay in the existing
API lifespan. An absent native configuration is explicitly reported as inspection
mode: no generation/admission or legacy fallback is started.

`--check` inspects these prerequisites without creating files or spawning services.
It does not claim database restore/integrity, account login, model quality, Ken
readiness or host resource readiness. `--help` does not read storage. The default
API is numeric loopback port8000 and Vite is numeric loopback5173 with strict port
selection. `--api-only` supports an installed package outside a frontend checkout
and an explicit alternate API port. The frontend proxy still targets8000, so the
launcher refuses another API port when launching that frontend.

Services use direct `subprocess.Popen` handles, no shell command interpolation,
saved PID adoption, `pkill`, npm wrapper process or service registry. An exiting
service closes its peer and preserves its failure code. SIGINT/SIGTERM request
cleanup after in-flight process creation returns its original handle. Cleanup
sends termination to those handles, waits a shared15-second grace and kills only
a launched child that exceeds it. Forced termination explicitly asks the operator
to inspect native recovery state before resuming; it does not claim native runs
were gracefully closed or peers/authority were safely recovered. The existing
native runtime owns its actual workers and recovery protocol.

Tests use actual subprocesses to verify peer exit, OS signal cleanup and an
unrelated sentinel's survival. Existing missing/empty database guards remain.
The installed proof separately exercises the real API readiness/lifespan and
repeat startup, recording exactly whether the frontend was also launched and
which state was retained. This does not replace global runtime/restore tests,
full deployment provisioning, visual acceptance or real model/Ken evaluation.
