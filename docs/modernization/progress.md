# SDD ledger — plan: docs/superpowers/plans/2026-10-31-actualizacion-proyecto.md

## Objective and authoritative workspace

Implement the entire referenced modernization plan, including all 43 scenarios, runtime evaluation, Ken integration, communication, migrations, prompt evaluations, and generated design references for every screen. Partial milestones do not complete this objective.

- Branch: `codex/project-modernization`.
- Workspace: `/home/andres/.codex/worktrees/b09e/researcher` (managed worktree).
- Starting commit: `e7b5719`.
- Original checkout and its pre-existing changes are preserved.
- Runtime comparison sources: `/home/andres/Proyects/infinidev` and `/home/andres/Proyects/ken`; managed-worktree placement does not preserve relative sibling paths.
- Process output: `.superpowers/sdd/2026-10-31-actualizacion-proyecto/`.

## Execution status

- [ ] Phase 0: clean installation, baseline tests/build, data inventory and failure reproductions.
- [ ] Phase 1: locked dependencies, one database configuration, repeatable safe startup and restore.
- [ ] Phase 2: Codex/Infinidev comparison, bounded execution, Ken MCP and subscription checks; runtime decision.
- [ ] Phase 3: durable vertical task, communication/control, corrections, cancellation and recovery.
- [ ] Phase 4: migrate retained capabilities, data, tools, review/CI, Git and infrastructure.
- [ ] Phase 5: complete prompt/inference inventory, communication guide and evaluations.
- [ ] Phase 6: design audit, pilot and at least 36 desktop concepts plus 12 mobile adaptations; recorded selection.
- [ ] Phase 7: implement all selected screens and verify workflows, accessibility and responsive behavior.
- [ ] Phase 8: remove replaced engine/CrewAI, prove all acceptance requirements, final independent review and release handoff.

Scenario status and evidence are tracked in `coverage.json`. An unchecked item is unfinished even if its supporting documentation exists.

## Pre-flight and rulings

- Pre-flight: runtime selection determines retained dependencies, tool schemas and prompt contracts; durable task/attempt/context identity must precede broad workflow migration; UI binds to those contracts; final acceptance requires real runtime and rendered UI evidence.
- Ruling: the user's new instruction activates implementation; historical wording in the plan that limits its original authoring session to documentation does not prohibit execution now — the scope remains the whole plan.
- Ruling: use the platform-managed worktree, copy the authored plan/instructions, and leave the source checkout unchanged — avoids mixing user edits into implementation; sibling-source references must be resolved explicitly.
- Ruling: this plan is a roadmap rather than a script-ready list of `Task N` headings. Record concrete task briefs here before each change and verify each deliverable; do not invent completion from the skill's heading extractor.
- Ruling: use Python 3.12 for the transitional legacy environment and maintained Node 24 LTS for frontend validation — the system Python 3.14 and absent Node are unsuitable as an implicit baseline. Revisit supported versions after selecting the runtime.
- Ruling: baseline tests run with outbound sockets blocked and inherited provider credentials removed; tests must not consume the user's subscription or mutate real services. Model smoke tests will be separate and bounded.

## Current task: baseline and reproducible environment

Files: `pyproject.toml`, `uv.lock`, generated `requirements.txt`, development toolchain declarations, baseline report, offline test configuration.

1. Resolve the current runtime requirements in an isolated Python 3.12 environment; record exact versions.
2. Run the original suite offline and the existing frontend build with its original lock; record all failures and limits.
3. Declare actual direct dependencies and dev tools once, generate the lock and requirements export, and validate a clean locked install.
4. Address configuration/startup failures with failing behavioral tests before implementation.

Installed transitional dependencies include CrewAI 1.15.33, crewai-tools 1.15.33, FastAPI 0.162.0, Pydantic 2.12.5, LiteLLM 1.106.6, ChromaDB 1.5.9 and pytest 9.2.0. This is an observed baseline resolution, not the final retained stack.

## Evidence and decisions from the first implementation pass

- Baseline: 813 tests; 710 passed, 100 failed, 3 skipped. Frontend original build passed on Node 24.22.2. Reports: `baseline.md`, `baseline-results.json`. No model calls or real data migrations.
- Data inventory checked six known locations in the original workspace/container default; none exists. `data-inventory.json` records exact scope. This is not proof that no database exists at an externally configured location.
- Ten new database tests were observed failing, then passed: selection, aliases, ambiguity, clean initialization, repeatability, migration failure propagation and unknown-database preservation. Related database/config tests: 30 passed.
- Ruling: replace the old test's `/research/infinibay.db` default expectation with the new settings/override contract — the old default contradicted the accepted data-path unification; existing paths are still detected and not moved.
- Ruling: isolate the standalone MCP script rather than downgrading FastMCP — latest installed FastMCP 4 requires MCP 2 while transitional CrewAI requires MCP 1. Its script lock and JSON-RPC initialize/tools-list check passed with 25 tools; no backend operation or model was invoked. This does not satisfy the final capability matrix or Ken/runtime integration.
- Ruling: add a 20-second offline test deadline; it exposed a listener shutdown waiting on a 30-second polling sleep. Fix the cause rather than extend the deadline. Two lifecycle tests were observed failing then passing; listener-related tests: 19 passed. Idle Stop now wakes polling; a live check retains ownership and reports timeout rather than pretending it stopped.
- `uv sync --locked` passed both in the project environment and a fresh environment. The clean environment initialized a temporary database, reported SQLite integrity `ok` and used the same path through settings/connections. The built wheel contains `backend/db/schema.sql`.
- Full post-change suite: 825 tests; 722 passed, 100 failed, 3 skipped. Its failing test identities match the 100 baseline failures; they are still unresolved. See `foundation-results.json` and the raw logs in this plan's scratch workspace. No whole-suite success claim is made.
- Ruling: local commits identify the assistant as `Codex <codex@localhost>` via per-command Git options because this host has no author identity configured; no global identity or user configuration was changed.

## Next work

Phase 0 is not fully complete: Stop/duplicate-effects scenarios still need runtime-level reproduction. Phase 1 is partial: safe Forgejo bootstrap, import-time inference removal, historical migration/restore validation and remaining startup work remain. Continue with those safety contracts, then evaluate Codex/Infinidev with bounded real-subscription checks and Ken before selecting the runtime. Do not spend effort repairing every obsolete CrewAI mechanism that phase 4 will retire.

## Inference-free startup and native transport foundation

Brief: make API import/factory and ordinary server/CLI startup inference-free; initialize persistence only during serving; preserve shutdown on lifespan errors; introduce bounded native stdio transport before model evaluation. This is transport groundwork, not a selected runtime or migrated product engine.

- API factory/import no longer initializes DB, starts maintenance or probes providers; serving runs migrations and propagates failure. CLI no longer performs a model-capability probe before dispatching its actual request. Native runtime replacement of the legacy CLI orchestrator is still pending.
- Ruling: disable automatic destructive cleanup at API startup until D08 retention/lifecycle guards exist — the previous scheduling was not safe to preserve; maintenance must be reintroduced explicitly after those contracts are verified.
- Local API defaults to loopback. Container/remote binding and access controls still require explicit configuration and verification.
- StdioRpcClient owns one process group, bounds frames/pending requests/event queues, correlates responses separately from events and server requests, drains stderr without logging secrets, never replays uncertain actions, and reaps its owned process on close. Write deadlines include blocked stdin. Linux process-group behavior is tested; cross-platform support is not claimed.
- Evidence: 18 focused startup/transport tests passed. New startup tests and 12 transport tests were observed RED→GREEN; a temporary lifespan mutation reproduced cleanup loss before restoring the verified implementation. Raw logs: startup-red.log, cli-startup-red.log, lifespan-red.log, rpc-red.log, rpc-write-red.log, native-startup-focused.log in the scratch workspace.
- Full suite: 843 tests; 740 passed, 100 failed, 3 skipped. Failure identities exactly match the baseline (native-results.json); no new failures. The whole suite is still red. Ruff passes for new transport/tests; three pre-existing lint findings remain in the touched legacy API/CLI files (PIE810, BLE001). uv lock --check and git diff --check pass.
- Real Codex metadata probe: 0.166.0 App Server initialized; native account/read returned chatgpt and model/list returned eight models. codex-inspection.json contains sanitized evidence. Zero model turns were sent; this does not prove task capabilities or runtime acceptance.
- Published ken-rank 0.18.0 is installed in an isolated tool environment. Infinidev source is being installed into a separate scratch environment; sibling sources and global configuration remain unchanged.

## Current task: bounded runtime comparison

Implement and test execution limits/control before real subscription turns; prepare a synthetic Git workspace and Ken index; evaluate both candidates on the scenarios in section 4.2. Capture actual tool evidence and artifacts, then choose the runtime and create the capability matrix. Readiness/health, safe bootstrap, migrations/restore and the full product engine migration remain unfinished.

## Bounded native session and first comparative trials

- Added CodexSession as a candidate boundary (not yet wired into the product): managed ChatGPT admission, native start/resume, streamed event consumption, steering receipt, terminal turn result, explicit host request decisions, wall/no-observable-progress/turn/tool/observed-token fuses. Native turn completion never marks a product task done.
- Nineteen native session behavioral tests were observed RED→GREEN. A cancellation/completion race initially masked budget failures with a native RPC error; corrected cleanup preserves the original cause. Stop during pending start now waits for native identity with a bounded fallback to owned-process termination, and duplicate Stop shares one interruption request.
- Focused runtime suite: 31 passed. Whole offline suite: 862 tests, 759 passed, 100 baseline failures, 3 skipped; identical failing identities (session-results.json). New runtime sources/tests pass Ruff; git diff --check passes.
- Published Ken 0.18.0 prepared three-file synthetic workspaces. Real Codex discovery and direct Ken query succeeded; the model subsequently used Ken successfully in a bounded explanation task, ran failing unittests and gave correct examples. Sanitized artifacts: codex-explain-evidence.json and runtime-evaluation.md.
- Ruling: support explicit host decisions for native MCP elicitation rather than silently granting all requests — Codex 0.166.0 requests consent even for these Ken queries. Evaluation allows only the selected Ken read tools in the synthetic workspace. Unhandled requests interrupt instead of granting permission.
- Real model calls now occurred through the subscription. Initial native trials stopped at unhandled Ken consent, then the scoped-consent trial succeeded. Native internal request count and remaining quota are not reported; only observed native tokens are recorded. No metered fallback was used.
- Infinidev source installed read-only into a separate environment; real authenticated HTTP preflight passed. Initial 8-completion-call fuse stopped the explain task before Ken/tests; a further trial uses equivalent wall/tool/observed-token limits with a larger request fuse. Candidate settings/source and global Codex config are not modified. The runtime decision remains open.
- Ruling: the comparison must record permission-policy or harness limitations separately from candidate failures — executing the exact fixture unittest command is already authorized and should receive an explicit scoped host decision, rather than being denied by a blanket evaluation policy.

## Comparative correction, native control and communication guide

- Both candidates corrected the same synthetic invoice function; independent parent-process unittest runs passed both tests and Git diffs contained only invoice.py. Codex: 19.19 seconds, 8 observed tool items, 109,235 native total tokens. Infinidev: 118.70 seconds, 26 intercepted subscription requests, token usage unknown. Single observations do not establish statistical performance superiority. Durable excerpts: codex-fix-evidence.json, infinidev-fix-evidence.json.
- Infinidev web bootstrap did not warm MCP, so cold tool discovery offered no Ken tools. A test-only explicit warmup exposed the four selected Ken readers before task admission. The prewarmed explanation trial then invoked Ken and ran tests, but its closure treated the expected test failures as task failure and omitted the requested explanation. Optional argument validation errors consumed repeated calls. Evidence: infinidev-explain-evidence.json; no sibling source edits.
- Codex native resume reopened the prior thread in another process, recalled the correction without tools and preserved source hash. A live correction during execution changed the proposed example from 100/0.21 to 200/0.10; proposal.md contained 220.00. Native receipt and artifact effects are separate evidence (codex-control-evidence.json). Durable product context/agent propagation remains unimplemented.
- Two additional characterization tests pass: cancellation without a start receipt reaps its directly owned protocol peer, and separate synthetic workspaces use distinct peer processes/threads. Focused runtime suite now 33 passed. Full offline suite: 864 tests, 761 passed, 100 baseline failures, 3 skipped; unchanged failure identities (control-results.json). Ruff passes for runtime sources/tests.
- Ruling: never interpret a PID reported by a native shell as a host PID — the real probe reported PID 2 inside another namespace. Host process-group ownership applies to the RPC child, not necessarily tools executed in the native environment. This costs an explicit reconciliation/job-ownership boundary before full Stop support can be accepted.
- Cancellation evidence is mixed, not a completed requirement: the first watchdog cleanup yielded native interrupted/failed-command (-1) and no delayed write past 60 seconds; early explicit cancellation lacked command-terminal telemetry; a controlled trial with a command identity still could not recover a terminal command item within a three-second observation window. A quoting-error trial never started and is excluded. Do not repeat live trials merely because observation timed out; inspect the same thread/marker and resolve ownership first.
- Created docs/interaction/communication-guide.md with provenance, evidence/assumption/authorization distinctions, purposeful examples/metaphors/diagrams and textual alternatives, correction semantics, honest wait/error/partial states and acceptance rubric. It applies Ousterhout's cognitive-load/information-hiding and Hunt/Thomas's single-source/feedback criteria. The product prompt/UI integration, reserved eval cases and human comprehension checks are still pending.

## Next concrete implementation work

1. The latest fixture is reconciled (see the policy update below). Integrate cancellation with durable product task/attempt ownership, all tool types and crash recovery; native tool identity remains distinct from the directly owned RPC process.
2. Build the typed, project-scoped business MCP and persistence slice for attachment → source → finding → report. Retain canonical report content in DB, operation identity/idempotency and safe artifact reconciliation; expose it through the actual /reports product flow. Run this same scenario through both candidates.
3. Complete candidate isolation/auth/Ken-failure/control scenarios and capability/inference inventories, then record the runtime decision. The code currently remains a candidate boundary; neither runtime is selected or wired into the product.
4. Continue durable task/context/event ownership and the broad engine migration, safe bootstrap/migration restore, prompt evaluations and all visual-design phases. The original whole-plan goal is active and far from complete.

## Interruption retirement policy and retained experiment inputs

- Ruling: retire the dedicated native connection before returning an interrupted/cancel-raced turn, and reopen its durable thread for later work — an interrupted turn can precede tool-terminal telemetry. This adds process restart cost after Stop but avoids continuing on a connection with uncertain tool lifetime. It is a candidate boundary; the product service still owns durable effects and acceptance.
- The new peer-reaping regression was observed RED→GREEN (session-reap-interrupted-red/green.log). Focused runtime suite: 34 passed. Full offline suite: 865 tests, 762 passed, the same 100 baseline failures, 3 skipped (control-results.json). Runtime Ruff, lock check and diff check pass.
- A real post-change slow-tool trial is justified by the policy change rather than an observation timeout: it confirmed native interrupted, a reconciled failed tool (-1), 0.43 seconds from Stop request through reconciliation and no delayed effect beyond the original 60-second deadline. Earlier failed/limited trials remain in the report; full product-level Stop is not marked complete.
- evals/runtime/ retains the exact synthetic source/script bytes, hashes, prompts, versions, bounds and comparison limitations. Probe scripts still live in this plan's scratch workspace; a portable guarded live runner remains pending. This is a runtime experiment, not a controlled before/after prompt benchmark.
- Ken was asked for blast radius; the new session file was not yet indexed, so literal consumer inspection confirmed only its tests and development probes. A published Ken prepare process is refreshing this worktree's index (session 65461, PID 663021); a read-only scope check found 513 indexed files and zero scratch paths. Re-poll that same live handle before starting any replacement.

## Current brief: project-scoped research persistence and business MCP

Base: 64cca48. Deliver a real attachment/web-source → quoted finding → canonical report slice, usable from both candidate runtimes and visible in the existing report API/UI. Keep runtime selection open until this scenario and the remaining isolation/control cases are demonstrated.

- Source snapshots retain locator, content hash, extraction/transport provenance and capture time. Text is evidence, never authorization. Findings cite exact excerpts; reports link findings and keep canonical Markdown in artifacts.content.
- Ruling: add transactional tool grants and task context versions now — a project ID in model arguments or environment alone cannot prevent stale/cross-project effects. Grants bind project/task/actor/version/permissions, expire and can be revoked; every mutation rechecks them under its write transaction. The later runtime service must own grant issuance and context correction lifecycle.
- Ruling: introduce migration 18 from one SQL resource, applied statement-by-statement inside a transaction (not executescript with implicit commits). Legacy migrations are unchanged in this task and still need historical restore validation. Existing schema-only consumers remain compatible; serving/CLI ensure_migrations applies the new resource.
- Ruling: persist report text atomically in DB without a second filesystem copy — the report view already reads artifacts.content; binary storage and export remain separate capabilities. Legacy write_report is retained temporarily until its callers migrate.
- Start with behavioral tests for idempotent retries/conflicts, concurrent duplicate effects, scope and revocation/context races, citation fidelity, canonical report API recovery and migration rollback/data preservation. Then implement guarded attachment/web acquisition, typed HTTP/MCP tools and bounded live research trials. No model calls in the ordinary test suite.

## Research business boundary — implemented and verified

- Added plain research contracts/ports, bounded acquisition use cases and a SQLite adapter. Migration 18 creates project-bound sources, exact source excerpts, canonical report metadata/links, task context versions, hashed expiring tool grants and atomic operation receipts. Existing v17 project/report rows survive repeated upgrade; an injected SQL failure rolls back DDL and marker (migration tests RED→GREEN).
- Extracted the unchanged SQLite connection policy into backend/db/connection.py; legacy get_connection delegates to it. This keeps the new adapter free of the eager CrewAI tool-registry import. Related legacy DB tests pass. Updated the old generic annotation to the declared Python 3.12 syntax while clearing touched-file lint.
- The new /api/research-tools boundary has strict body schemas, scope from bearer credentials, transactional revocation/version/permission checks, bounded source/report windows and independent citation pagination. Model-side fields cannot select project/task/actor, mint grants or run SQL. Findings are provisional with confidence NULL; reports remain drafts and canonical in artifacts.content.
- Attachment traversal uses directory descriptors/O_NOFOLLOW, regular-file and byte checks, UTF-8 validation and a stable-revision check. Unsupported binary/PDF extraction is explicitly unfinished in this route; legacy capabilities remain until phase 4 migration.
- Public web acquisition pins vetted public DNS addresses, verifies the original TLS hostname, revalidates redirects and bounds bodies/time/DNS workers. The slow-drip header regression was observed failing at 0.60s against a 0.20s budget, then passed after bounding socket receives. Local TLS wrong-host and SNI cases pass. A real Python decimal documentation capture succeeded (research-web-evidence.json).
- New locked standalone MCP exposes ten researcher_* business tools. Real MCP initialize/catalog/calls against the real HTTP server and temporary DB passed for attachment + web → quoted finding → canonical report; same-key retry and recovery after backend/MCP reopen preserve the receipt, and revoked credentials become isError. No model calls in those smoke checks (research-mcp-evidence.json).
- Artifact detail now requires project_id. Its only frontend consumer sends it, scopes the cache by project and resets effective selection on project switch. Human report title/draft state are visible. This functional patch is not the phase 6/7 visual redesign.
- Verification: 71 research tests pass; the focused research/DB/startup group passed 89. Full offline suite: 936 tests, 833 passed, the identical 100 baseline failures, 3 skipped (research-tools-results.json). New/touched targeted Ruff and frontend TypeScript/Vite build pass; the existing large-chunk build warning remains. The whole suite and broader legacy lint are not yet green.
- Root worktree Ken preparation was confirmed live at >20 minutes, ~2 CPU cores and 513 indexed files with no scratch paths. It was deliberately stopped at a 20-minute setup resource budget (session 65461 terminal exit 143), not restarted after an observation timeout. No completed retrieval-profile claim is made. Small synthetic Ken MCP fixtures were already prepared and passed; full-project preparation needs a bounded background job and useful diagnostics.

## Next task: live research comparison and product runtime integration

Run the same bounded attachment/web/finding/report scenario through both candidates using the new business MCP and mandatory published Ken MCP, isolated projects/workspaces and subscription-only routes. Keep credentials out of prompts/workspace config; retain result artifacts and failure evidence. Then complete remaining runtime isolation/control/failure acceptance and the capability/inference inventories before choosing the production runtime. Global legacy HTTP/WS auth, durable run/context/events, all tool lifecycles, migration restore, prompt evals and all image/UI redesign phases remain open.

## Live research comparison, portable runner and inventories

- Continuation audit: the preceding status-only user turn did not advance implementation. Revalidated the managed worktree, commits, trial files and actual process table. The prior Codex research process was terminal with a persisted result; it was not restarted after losing its tool handle.
- Added the portable, explicit `--live` research runner and separate manifest. It starts real API/MCP servers against temporary projects/DB, prepares a bounded Ken fixture, checks pinned versions and subscription routing, serializes campaigns, records native events, independently verifies persisted evidence/report and artifact API, revokes grants and reaps owned servers. Infinidev credentials enter its shim through a private FD and are supplied only to the business MCP child. These are evaluation adapters, not production runtime integration.
- Codex research trial: 37.10s, 10 observed MCP tool items, 160,718 native reported total tokens; Ken + attachment/web → exact-cited provisional finding → canonical draft report + read-back and product API passed. Independent post-trial hashes/index/HEAD match the initial fixture; no unexpected outputs outside known runtime state. Human communication review and rendered report acceptance remain separate.
- Initial Infinidev trial is explicitly invalid as a candidate comparison: the evaluation policy recognized `mcp:server.name`, but the generic effect broker asked using a bare tool name. The harness denied authorized captures. Reproduced both forms in offline regression tests, corrected only the scoped policy and retained the failed trial. Unrelated tool effects, URLs and operation keys stay denied.
- Corrected Infinidev trial: 181.41s including Stop request/observation, 28 intercepted subscription requests, token usage unknown, final native `cancelling`. Both sources and one provisional finding persisted, but no report before the 180s deadline. Final repository-state check passed. No budget expansion or further trial was used to manufacture success. All grants from all three trials were revoked; their API/candidate/MCP process groups are terminal.
- A no-model diagnostic read the real published Ken schema and exercised Infinidev's own argument model: omitted `limit` passes, explicit null fails, while direct MCP accepts null. The nullable/default translation defect belongs to the pinned bridge; other repeated empty-argument failures remain unassigned. Durable evidence: research-runtime-evidence.json and runtime-evaluation.md.
- Ruling: the live runner now inherits an explicit toolchain/locale/auth-file-discovery allowlist instead of filtering selected API key names — filtering missed unrelated tokens, project settings and proxies. A regression was observed RED→GREEN; a native metadata-only probe still reported chatgpt with zero model turns after this change. The earlier live trials used the earlier scrub policy, so the new environment policy is not retroactively claimed as their setup. Filesystem/container credential isolation remains open.
- Added independent fixture-effect checks for source edits, unrequested files, staged additions and even an empty commit; all were observed failing before the guard existed. Known `.ken/`, `.infinidev/` and `.mcp.json` state is explicitly outside this final-output check. It does not prove OS isolation or absence of transient effects.
- Created capability-matrix.md covering all 71 registered tool names and their current Pydantic schemas in legacy-tool-schemas.json, plus 18 additional unregistered source declarations for consumer review. Schema collection refused socket connections and did not instantiate tools. Each family has a destination, scope/effect/persistence rules and pending acceptance; inventory is not capability migration completion.
- Created inference-inventory.md covering direct/transitive LoopEngine, CrewAI, chat summary, deep-research synthesis, memory, embedding/document wrappers, startup probes, warmup and external service credentials. Notably CrewAI Tools maps `default` embeddings to OpenAI; those routes must be removed or replaced before a whole-product subscription-only claim.
- Created engine-redesign.md before widening production integration: Researcher owns context/run/attempt/grants/acceptance; runtime owns inference. Fencing, correction, event durability, reconciliation, communication and consumer retirement are explicit. Domain contracts and their persistent implementation are the next required code deliverable, not already supplied by the document.
- Browser gate: product-design audit preflight found no saved context. Both CUA inventory and explicit IAB creation reported the browser host unavailable. A temporary report-view server over a DB copy was shut down. No screenshot, visual audit or rendered /reports acceptance is claimed; phases 6/7 and all 48 generated references remain open. Other implementation can proceed, so this is not a whole-goal blocker.
- Verification: focused runtime group 49 passed. Full offline suite 951 tests: 848 passed, the identical 100 baseline failures, 3 skipped (research-evaluation-results.json). New/touched targeted Ruff, runner help, lock and diff checks pass. Whole suite remains red; no production runtime decision or whole-plan completion claim.

## Next brief: durable run, attempt, context and event ownership

Base: current comparison milestone. Apply DDIA transaction/fencing/reconciliation rules and Clean Architecture boundaries. Add neutral plain contracts and a SQLite coordination adapter with atomic run transition + events_log identity, idempotent admission, one active claim, stale-attempt/context rejection and cancellation intent that prevents future business effects. Expired ownership must enter reconciliation, never replay the original request automatically. Start with real SQLite tests for duplicate/concurrent admission, claim races, result-after-correction/Stop, restart and injected event-write failure. Preserve the current task schema until consumers migrate; native completion alone must not mark tasks done. Runtime selection/isolation/auth failure scenarios and the rendered report gate remain prerequisites for production rollout, not excuses to omit durable coordination.

## Durable coordination foundation — implemented, not yet wired into the product

- Continuation classification: the previous goal turn made progress (commit 09c9830). Revalidated the managed branch/status/ledger before starting this brief. No live candidate task was restarted and no model calls occurred in this turn.
- Added plain RunSpec/RunView/AttemptLease/event contracts and SQLiteRunStore: keyed admission, one active run per task, transactional claim, fencing/heartbeat, native thread/turn binding, typed terminal observation, Stop intent, context revision and ascending project history. Existing orchestration/API/WS consumers still need migration; this is a persistence foundation, not a functioning replacement engine.
- Migration 19 is additive, preserves legacy task rows, and adds runtime runs/attempts/context/command and native-observation receipts plus grant bindings. Extracted the SQL-resource transaction executor for migrations 18/19; a direct failure test showed its transaction stayed open, then passed after making its owner roll back on all failures. Per-version atomicity does not imply a transparent rollback of all historical migrations.
- Ruling: native `completed` yields `needs_review`; native `failed` or `interrupted` yields `reconciling` — a terminal runtime status does not prove every tool/job stopped. No path in this adapter accepts work or publishes, and no replacement attempt is admitted during reconciliation. A dedicated failing test caught the unsafe native-failed→failed shortcut before changing the policy.
- Ruling: binding history remains `runtime_bound=1` after its attempt FK becomes NULL — deletion must not restore a credential as an independent grant. The research MCP checks run/attempt/fence/context/lease inside every transaction, so an expired lease blocks even a previously obtained scope before an expiry sweep. Those two guard regressions were observed failing before the guard was added, then passing.
- Ruling: Stop withdraws this run's current attempt rather than all grants of its task — cancellation of a historical failed run must not revoke a newer run. A real SQLite regression reproduced that defect and passed after narrowing scope and treating historical terminal runs as unchanged. Context correction is separately task-version-wide and invalidates its older scopes.
- Corrections preserve message/example/evidence/assumption provenance, expected version, intent hash and receipt. State/context/grant changes and their durable event commit atomically; injected event failure restores all of them. The source label does not prove truth, shared understanding or authorization; producer/application acknowledgment remains separate.
- Native thread identity can commit before dispatching turn/start; the later turn receipt cannot silently select another thread. Native facts arriving after Stop/lease/context loss can still be stored idempotently, correlated to the original owner and native identity, without restoring authority or changing task state. A literal DONE inside the late payload remains data. Full crash recovery and real job reconciliation remain open.
- History now has a reusable ascending-by-id project reader with stable pagination over both runtime and pre-existing event sources, including equal timestamps. It preserves entity type/id and source instead of pretending every event belongs to a task. The public descending endpoint/live bus still needs replacement and cursor-retention handling; no whole catch-up claim.
- Verification: 28 new coordination tests pass; related runtime/research/legacy DB focused group passed 155 before the final added cases. Final full offline suite: 979 tests, 876 passed, identical 100 baseline failures, 3 skipped, zero new/resolved failure identities (coordination-results.json). Targeted Ruff, lock and diff checks pass. A rebuilt wheel's six selected schemas/modules exactly match current source bytes (coordination-packaging.json). No real user database was upgraded and no model inference ran.
- Remaining deployment conditions: the async service must perform blocking SQLite work outside its event loop; issue/bind grants before delivering them; persist budgets/configuration/ownership; reconcile tools and native identity; apply global HTTP/WS auth and filesystem/network boundaries; migrate old writers. Old binaries ignoring runtime_bound cannot be treated as a safe operational rollback. See run-coordination.md and the still-open full-plan coverage.

## Next brief: runtime service, owned jobs and protected delivery

Base: coordination milestone. Inspect the installed native capability/configuration controls to establish which built-in effects can be disabled or confined; do not infer that the RPC peer owns tools in another namespace. Compose CodexSession with durable admission/attempt/context/grants and an async host service, persist thread identity before dispatch, and control all job effects through owned/scoped operations where native ownership is insufficient. Keep public start/control endpoints behind a demonstrated user/session boundary and migrate HTTP/WS history/control together. Prove Stop/crash/late-event/correction against actual owned subprocesses and real persistence before exposing the first product execution. Finish runtime failure/isolation gates and production choice without abandoning Infinidev's retained comparison evidence. All retained capability migrations, restore/bootstrap, prompt evaluations, 48 generated design references and full UI implementation remain required.

## Owned native jobs — durable dispatch and real failure evidence

- Continuation audit: the preceding status-only response was no implementation progress. Revalidated the managed worktree and process table. The prior full suite, native lifecycle probe and wheel build were terminal; none was restarted after losing observation handles.
- Migration 20 adds per-run operation identity, one active/uncertain job, dispatch intent before native execution, immutable bounded binary output and terminal receipts. Duplicate operations do not replay on another connection. Original attempts can report late facts after Stop/correction without regaining authority. Unknown current effects atomically reconcile/fence the run and revoke its business grants.
- Added dedicated per-attempt command peers, separate from model inference/event consumers, using private HOME/CODEX_HOME, no account/credentials/inherited MCP, explicit host-selected filesystem profile and disabled network. Effective native configuration and pinned CLI version are checked. No new model turns were submitted.
- Ruling: physical termination proceeds in parallel with durable cancellation intent — SQLite contention must not let an already authorized Stop wait behind another writer while a child continues its effects; the final receipt still waits for persistence. Cost if wrong: a crash between physical Stop and intent commit requires conservative reconciliation rather than replay.
- Ruling: shell-reported native process IDs are never host PIDs; the host UUID is connection-scoped, and cleanup uses its directly owned RPC process. Cost if wrong: signalling a namespace PID could target an unrelated process. Native effect completion is separately observed.
- Added output ordering barriers before terminal persistence, bounded handles/buffers and durable observed-lease expiry to prevent clock rollback from restoring authority. The first output-barrier mutation test was too weak and passed; the strengthened gated-consumer regression fails with the barrier removed. SQLite-busy and expiry recovery regressions were observed RED→GREEN.
- Real portable `run_commands.py --live --peer-loss --db-contention`: Alpha/Beta homonyms and own access pass; cross-read and socket denied; hostile workspace config did not broaden permissions; confirmed detached child stopped without delayed effects; other project completed. Stop native exit 137 in 0.159s in this single trial. Killing the directly owned peer yielded unknown/reconciling, revoked grant and no observed detached delayed effect. Physical Stop preceded SQLite writer unlock. These are command API proofs, not a full production Stop claim or performance benchmark. Invalid setup/readiness/timing trials remain described in owned-command-evidence.json.
- Verification: runtime group 99 passed; full offline suite 1001 tests: 898 passed, the identical 100 baseline failures, 3 skipped (owned-jobs-results.json lists every failure). Targeted Ruff, lock and diff checks pass. Built wheel bytes match all four SQL resources and six runtime/migration modules (owned-jobs-packaging.json). The whole suite remains red. No global HTTP/WS auth or product runtime admission is exposed by this task.

## Next brief: authenticated delivery and runtime composition

Base: owned command milestone. Implement local-owner authentication across HTTP and WebSocket before exposing durable runtime admission. Browser sessions must not inherit tool credentials; host-issued business tokens must not authorize legacy SQL/internal routes. Reject hostile origins/hosts and protect session bootstrap without placing credentials in URLs or served assets. Then compose runtime service with durable attempt ownership, mandatory Ken, subscription-only inference, corrections/Stop and replay-safe history. Continue all capability retirement, prompt/communication evals, migration restore and the complete visual redesign; the full plan remains active.

## Authenticated local delivery — implemented; product runtime still pending

- Added a default-deny owner boundary for every product HTTP route, docs/OpenAPI and WebSocket, with Host/Origin validation separate from CORS. Business bearer credentials remain accepted only at their typed research boundary and do not authorize owner APIs, generic SQL or project subscriptions. The human owner manages all local projects; no multiuser membership claim.
- Serving creates an instance-specific random pairing file 0600 in a user-owned 0700 directory outside the workspace; construction/import remains inert. Only its path is printed/logged. Pairing is JSON/header/body/deadline bounded; opaque HttpOnly/SameSite=Strict cookies, HTTPS Secure, monotonic expiry, bounded sessions/failures, CSRF and revocation are enforced. Restarts discard sessions. No OAuth or API credential is sent to the browser.
- Web access is gated before mounting product queries/WS. CSRF lives only in JS memory; the transport refuses external/control-character paths and redirects. Multipart uploads use it too. Logout/401/WS policy close retire caches/connections. Generation guards preserve fresh sessions against delayed old HTTP status/401 responses. This is functional access UI, not completion of the required visual redesign or a substitute for any of its 48 refs.
- RED→GREEN: anonymous HTTP/WS, hostile host/origin, owner pairing/control and tool-versus-owner separation; raw non-ASCII CSRF headers (previous direct comparison raised instead of denying); URL control-character and redirect guards; stale initial status; retired project socket events/error. A stale A socket previously closed B. The backend manager also retained a callback to a closed event loop; a two-loop real EventBus regression reproduced lost delivery and now passes after unsubscribing its last client.
- A real zero-model HTTP/WS probe passed anonymous denial, separate business grant authorization, internal SQL denial, owner CSRF, authorized ping and logout closing the open socket. Its backend process is terminal. Portable opt-in runner: evals/security/run_local_access.py. Updated the research runner to pair its independent human artifact reader through a private temporary control directory; candidate/MCP credentials remain separate.
- Ruling: owner sessions are process-local and restart requires pairing again — preserve a clear local-owner boundary without introducing accounts/OAuth storage into the browser; cost if wrong: user inconvenience on restart and no support for multiple independent server workers without a shared session design. Default launch remains one loopback worker.
- Ruling: the legacy unauthenticated internal client is allowed to fail closed during migration; never forward the human cookie to agents to keep it working — typed per-attempt tools are the destination; cost if wrong: transitional legacy pod/CLI operations need migration before their old workflows function.
- Browser verification remains unavailable: a fresh CUA inventory again returned no browsers and “browser access host is unavailable.” No alternative UI automation was used and no visual/keyboard acceptance is claimed. Backend and transport work proceeded independently.
- Verification: final owner/API lifecycle group 26 passed; combined API/research/runtime group 213 passed plus its known project-deletion baseline failure. Full offline suite now 1027 tests: 924 passed, the same 100 baseline failures, 3 skipped; every identity is retained in local-access-results.json. Four frontend transport regressions pass with pinned Node 24; TypeScript/Vite build passes (existing chunk-size/Browserslist warnings remain). Targeted Ruff, lock and diff checks pass. New wheel bytes match the six delivery modules and four SQL resources (local-access-packaging.json). Protocol and asset hashes: local-access-evidence.json. No whole-suite green or rendered-UI claim.

## Next brief: production native runtime and first authenticated vertical

Compose the production native boundary and asynchronous runtime service after this owner-delivery milestone. Read current code before relying on prior experiment launchers. Keep model inference on managed ChatGPT/Codex only, keep its credentials outside native-readable workspace/filesystem scopes, disable inherited apps/MCP/native effect tools and validate effective configuration. Verify published Ken cannot read another workspace/control secret through paths, symlinks, query scopes or saved findings; configure or wrap its boundary as evidence requires. Do not infer MCP isolation from the native command sandbox.

The service must own admission/attempt/lease/fence, persist identity before dispatch, mint/bind/revoke typed tool grants, retain native facts and proposal state, enforce durable work budgets, and expose Stop/correction/history through the authenticated API. Stop must initiate physical interruption without waiting behind a busy SQLite writer, while persistent fencing and receipts remain mandatory. Restart must reconcile old owners and uncertain dispatch without replay. A completed native turn is needs_review, never accepted task completion. Deliver one real task → explanation/evidence → correction → revised proposal path with mandatory Ken before widening legacy tool migration. Native request/approval handling, typed inter-agent/user questions, Git candidate acceptance, all retained capabilities, historical data restore, complete prompt/communication evaluation and visual phases remain required. The owner access state also needs professional visual exploration alongside the twelve canonical pages; none of their 48 required refs has been delivered.

## Current brief: isolated published Ken and production native composition

Base 279d751. Previous goal turn was progress (335ca0c and 279d751); current work continues the full objective, not another definition of completion. The worktree began with only the three instruction directories/files untracked and no live prior evaluation process. Connected Ken semantic/relationship data does not index the new worktree runtime/research modules; current source and real tests remain authoritative.

- Implemented (uncommitted at this checkpoint) `ken_worker.py`: pinned isolated published installation, interpreter-alias preservation, source read-only, writable .ken only, private HOME/cache, no inherited provider/grant credentials and an isolated network namespace. Source/state and verified public model files are pinned with descriptors before mount and not leaked into the child. Reject a foreign .ken symlink or a workspace containing the trusted tool installation. Root CLI entry point uses the same policy.
- First published isolation trial `ken-isolation-a8e1c4b4` failed before MCP checks: private HOME had no embedding assets, and network denial prevented Hugging Face downloads. This was a setup failure, not a successful isolation/capability trial. Process is terminal. Added exact model-artifact mounts from the four package-pinned manifests, SHA256/size verified before mount, and forced offline lookup. Do not mount all user caches or tokens. Failed setup remains retained.
- Corrected published trial `ken-isolation-c7e275c8` passed: local embedding/index preparation and real MCP initialize/catalog/read, foreign absolute path/symlink/control-secret denial, structural scope and imports denial, lexical search retained project scope, and separately seeded homonymous memories stayed local. Generative turns submitted: zero. Ken does use local embedding/ranking models; never describe this as zero local inference. Synthetic OS policy tests use a clearly labelled fake tool installation, not evidence about Ken implementation.
- Added host-local `LiveGrants` plus an optional runtime-authority guard inside SQLite research transaction revalidation. API composition supplies its own gate. Runtime-bound credentials require live registration; an already-authorized scope waiting at real BEGIN IMMEDIATE cannot mutate after host withdrawal, even before SQLite can persist revocation. Unbound host-issued evaluation grants retain their prior contract; they cannot be minted by agent-facing tools. Focused research/coordination/grant group 101 passed; policy/grant group 9 passed.
- Added native session named permission profiles, pre-thread async validation, on-started durable identity hook, async observers and a UTF-8 answer byte fuse. Five regressions observed RED→GREEN; session group 28 passed. Native interruption remains available while the on-started persistence hook waits. None is production API admission yet.
- Ruling: production Codex will receive the existing business MCP schemas/results through host-mediated dynamic tools; its business grant stays in the host-owned MCP child and never enters the model peer's environment or config. Keep the same MCP/tools/use cases instead of duplicating schemas/business rules. Ken remains a direct, isolated mandatory MCP. Cost if wrong: the pinned experimental native dynamic-tool bridge and a host MCP lifecycle require regression coverage; a later runtime adapter must translate that protocol. This is transport mediation, not retirement of the business MCP or reduced capability scope.

Next concrete implementation: build the native factory with managed ChatGPT auth (no OAuth copy/client), minimal environment, effective config preflight, named read-only inference scope, disabled inherited integrations/effect tools/hooks/host skill discovery, isolated Ken and host-owned business MCP mediation. Verify actual configuration and native catalog without a model before the first bounded task. Then compose the real async coordinator and authenticated run/control/history endpoints, durable dispatch budgets and restart reconciliation, and exercise the first task/explanation/correction/proposal path. All migration, prompts, other capabilities and visual work from the original plan remain open.


## Native composition and first authenticated product vertical — implemented

- Continuation audit: the immediately preceding status-only answer was no implementation progress. Revalidated the managed worktree, processes and retained logs. The lost native-resume probe and full suite were terminal, not restarted due to missing handles. The suite was 1057 tests / 954 pass / identical 100 failures / 3 skips. Zero-turn native resume failed as `thread not loaded`; this remains a limitation, not successful recovery evidence.
- Added production `CodexRuntime`, host-mediated existing business MCP, isolated published Ken, LiveGrants revalidation, cancellation-aware callbacks and named-profile preflight. Effective account/provider/auth endpoint, features, environment, MCP, model, cwd and permissions are checked before a turn. Defaults observed from the installed CLI: canonical ChatGPT endpoint with trailing slash and absent env_vars normalized to null. Resume cannot replace dynamicTools; it requires recorded catalog/cwd and is not used to replay uncertain work.
- Added RuntimeService, explicit host config, exclusive canonical-DB OS owner lock, workspace/repository selection, heartbeat/fence, grant mint/bind/withdraw, native identities, proposal persistence, authenticated Start/Stop/correction/context/history endpoints. API uses the exact same LiveGrants registry as workers. Blocking DB/inspection runs outside the event loop. Multiple repository choices and development tasks without migrated capabilities fail explicitly.
- Migration 21 reserves each native turn before dispatch, storing tool-catalog hash, runtime version, workspace and limits. Durable lifetime project budgets retain unknown reservations and observed overrun high water, without summing cumulative counters. They are work fuses, not known quota or a physical billing cap. No automatic budget renewal/policy change. Duplicate reservation never authorizes resend.
- Stop withdraws live authority before waiting for SQL, requests interruption and retires the directly owned native peer. The business MCP drains in its owning worker; caller errors are re-raised after normal SDK scope cleanup. A final cancelled state requires confirmed native/business closure, committed revocation and no unknown owned job. Teardown uncertainty stays reconciling, retains the proposal and blocks repeat dispatch. Known native failure can retire only after these local proofs. Native completion still never marks Task done.
- Corrections validate before interruption, preserve source strength/version and record intent for the next explicit request. Added RED→GREEN regressions for startup cancellation lock leakage, invalid correction preemption, blocked SQLite Stop, conservative usage high water, unknown job retirement, native failure reconciliation and teardown uncertainty. A strengthened Stop/disconnection case initially exposed that treating every body exception as unconfirmed teardown was too broad; the native/MCP adapter now provides explicit host closure receipts, separately from native outcome and usage.
- Ruling: choose Codex 0.166.0 as the migration target — managed subscription/control and the persisted research integration are demonstrated, while Infinidev comparison retains unresolved bridge/control/isolation issues — this is not statistical quality/performance superiority and does not complete the migration. See runtime-decision.md.
- First real product trial `product-runtime-eb05d6ff` failed: disabling `code_mode_host` made all model tools unavailable. Two honest native completions created no report. Local model metadata selects `code_mode_only`; official pinned runtime source confirms its host requirement and V8 delegated-tool boundary. Ruling: require code_mode_host and code_mode_interrupt while keeping shell/direct exec/unrelated integrations disabled — otherwise the selected model cannot use mandatory Ken/business tools. Effective-config refusal has a RED→GREEN regression.
- Corrected product trial `product-runtime-c6b3ae2f` passed through actual owner HTTP, service, managed subscription, Ken and business MCP: two captured sources, exact quoted provisional findings, two canonical draft reports, example 100→200 with tax 42/total 242. Independent DB checks verify quote membership, hashes, superseded first run, needs_review second run, unchanged task/source and revoked grants. Owned native rollout excerpts prove Ken calls and reveal one rejected finding_type=provisional; the model corrected it before any effect. Subsequently exposed valid category/report enums in the actual MCP schema and clarified category vs validation status; real locked-MCP schema checker observed RED→GREEN. This changes the catalog hash, so it is recorded separately from the two-turn trial.
- Real current `product-stop-1fe299eb` passed: one native turn admitted/bound, owner Stop receipt cancelling, final cancelled after both peer-close receipts, all grants revoked, no reports and Task unchanged. Usage is unknown and its dispatch keeps its reservation. This is Stop during generation, not the still-required slow business-tool product case. Total new generative turns in this milestone: five; the four completed turns report 321532 native cumulative tokens; remaining quota/internal requests/billing are unknown. No metered fallback.
- Final zero-turn `native-boundary-dfcaa835` passed with the new enum catalog and required code host: actual Ken read, mediated business read, own source positive, foreign secret denied, Python positive, read-only/network denial with errno controls, both peers and owned backend terminal. Earlier failed/weak trials remain classified in native-boundary-evidence.json. It does not prove native resume. No generative call in these probes.
- Actual host-loss command trial `parent-loss-fa168766` passed: killed only its owned holder, observed native peer terminal and no delayed write. First setup `4a46dbac` lacked Python pidfd wrappers; corrected harness uses libc stable pidfds. No additional supervisor was introduced without a demonstrated defect. This is not a remote billing-cancellation guarantee.
- Final full offline suite: 1080 tests, 977 passed, identical 100 baseline failures, 3 skipped, no new/resolved failure identities (runtime-service-results.json lists all names). Whole suite remains red. Targeted Ruff, uv lock and diff checks pass. Rebuilt wheel exactly matches 23 selected modules/resources, including all five SQL files. An earlier byte check correctly caught a wheel built before final comments; it was rebuilt and rechecked, not asserted from stale output.
- Browser recheck still returns no browsers and host unavailable. No alternative UI automation, screenshot, rendered UI acceptance, generated concept or implementation of the required 48 visual refs is claimed. No existing user DB, remote repository or main checkout was migrated/modified. Raw synthetic runs remain ignored; sanitized evidence is committed. All owned evaluation/test/server peers were terminal at the final process inspection.

## Next brief: make the new engine the product path, then migrate capabilities

Do not restart architecture discovery or re-prove metadata-only setup. Base is the native product milestone. Inspect current source and the evidence above. The new research API works, but existing task/chat/flow/frontend callers still use legacy paths. Connect owner-visible run controls, evidence inspection and durable history to those consumers without forwarding human cookies to agents or reviving old LLM loops. Add typed pending human questions and a conservative, operable recovery path for unknown attempts; preserve Stop/correction/late-fact semantics. Replace remaining development tools and agent communication with the same host ownership, then versioned Git/review/CI acceptance. Audit every producer/consumer and retain existing data/contracts rather than deleting failing tests to hide capability loss.

Continue the full original plan: historical migrations/backup+restore and clean bootstrap (including pinned public Ken assets), all retained web/document/wiki/Git/CLI/role/message capabilities, retirement of every auxiliary LLM/embedding paid path, complete prompt inventory/review/evals and human comprehension/correction cases, all twelve screen audits and 36 desktop concepts plus 12 mobile references, professional selected implementations and rendered accessibility/E2E gates, final independent whole-branch review. The runtime decision does not finish these deliverables. Legacy code and the known 100 baseline failures remain required migration work. Keep the original goal active until requirement-by-requirement evidence proves the full end state.


## Human workspace delivery, conversation ownership and model provenance

Base a8456cd. Continuation audit: previous goal turn was progress, committed the
native coordinator and real product/Stop proofs. Initial worktree had only the
three instruction files/directories untracked; no live prior evaluation handle
remained. The original goal and all visual/tool/prompt/data requirements persist.

- Migration 22 links native runs to existing human conversation records. User message, thread/task binding, admission and receipt commit together. A valid proposal, canonical result, revocation, chat reply and event share the completion transaction. Original run receipt format stays compatible when no conversation is supplied. Foreign/closed/other-task threads are refused; stale context cannot deliver a current reply. Task-run/context reads remain available for closed tasks.
- Added authenticated owner task workspace and source-window reads, without minting/forwarding an agent token. Read views operate without configured runtime and avoid host paths. Source project and immutable hash/offset are preserved; no-store headers and the existing cookie/CSRF boundary apply. Report deep links include project identity. User-task source metadata is bounded; full pagination/synchronization is still open.
- Task details have a functional Trabajo panel. Chat's default composer now selects a task and uses typed native instructions; old conversations/pending records remain readable. New UI displays admission vs running vs Stop confirmation vs proposal/uncertainty, explicit correction provenance/version, readable source windows and draft links. It does not infer on polling/reload. Ruling: this is interim functional delivery using the existing style, before the required generated concepts and complete professional implementation — it enables the early vertical workflow without claiming final UI acceptance; cost: these surfaces must be reconciled with the selected visual concepts.
- The generic chat endpoint now respects requested existing thread/project/status instead of silently creating another. Receipts distinguish stored notes, admitted instructions and proposals. Native conversation projection uses canonical joins. Full general project-lead dialogue and typed pending questions are not yet migrated; the older generic API/flows still exist and are not claimed subscription-only.
- Static consumer tracing found native user_to_agent rows could also wake old pollers. Added a compatibility guard to legacy message readers and create_message_event for native-marked threads (including later generic messages in them). The marker excludes old delivery, never grants authority. Positive legacy delivery remains tested. The poller consumes excluded messages and caps each read, so marker deletion does not replay old messages. This does not complete all old writer/flow ownership migration.
- UI reuses an immutable operation key for an ambiguous resend, and never automatically retries mutations. Two RED→GREEN service regressions found receipt recovery checked current context too early: old instructions now return the original receipt after correction; duplicate corrections return their recorded version without interrupting new-context work. A separate rollback-clock regression orders task-run history by local insertion, not wall time. The controlled inference helper itself selected the last attempt by tied timestamps and was corrected to use its actual grant/attempt identity; no production change was made to conceal that fixture error.
- Real conversation trial conversation-247bd3f1 passed using the actual owner HTTP API, coordinator, managed subscription, published Ken and business MCP: three instruction POSTs, one native dispatch, exact quoted provisional finding, draft report and same-thread proposal. A context correction and old-instruction retry did not infer again. Source hash/quote membership, zero legacy agent_events, revoked grants and unchanged task acceptance were independently checked. Native usage is recorded in conversation-evidence.json; subscription quota/internal request count/billing remain unknown. New generative turns this milestone: one. No metered fallback.
- User steering asked whether models are configurable. Confirmed the existing global JSON field model, loaded on serving/restart; no per-agent/project policy or web selector. Added display of configured model plus migration 23 for the model actually reported/validated by each native thread and stored before dispatch. Duplicate dispatch cannot be relabelled with another model. Historical NULLs are not guessed from current configuration. A backup of the real version-22 trial upgraded repeatably to 23: eight content/receipt tables unchanged, FK errors zero, old model unknown. Current zero-turn native-boundary-d1f9f092 passed and verifies the native model accessor, current MCP/config policy and peer closure; it is not another generative turn or native-resume proof.
- Final whole offline suite: 1096 tests / 993 passed / identical 100 baseline failures / 3 skipped, zero new/resolved identities (workspace-delivery-results.json lists every failure). API route fixtures were corrected to enter real serving lifespan: an earlier targeted run exposed an unmigrated test DB, rather than adding runtime migration side effects to production reads. Selected new/touched modules pass Ruff; eight existing diagnostics in communication/service.py and flows/event_listeners.py are unchanged against HEAD and recorded separately. Lock/diff checks pass. Wheel bytes match 28 selected files, including seven SQL resources. No real user DB was upgraded.
- Seven Node source/transport regressions pass; TypeScript/Vite build passes with existing chunk/Browserslist warnings. Reverted only the generated tracked tsbuildinfo cache, initially clean. No browser is available in fresh CUA inventory; no fallback UI automation, rendered/keyboard acceptance, visual audit, generated concept or completion of the 48 visual references is claimed. See workspace-frontend-evidence.json. All live evaluation servers and native peers are terminal.

## Next brief: pending human questions, recovery and remaining engine consumers

The task/chat research path is now functional; do not redo it or native metadata
discovery. Preserve user steering: global model is configurable, no web selector
or per-agent policy yet; model provenance must remain immutable/unknown as stored.
Next add durable typed human questions/answers and an operable conservative
recovery path for uncertain attempts. Migrate the remaining generic project/role
conversation, project start/stop and old autonomous writers into the same host
ownership rather than leaving a second LLM loop. Continue development capabilities,
versioned Git/review/CI acceptance and every retained tool family. Complete data
restore/bootstrap, all prompt review/evals and human comprehension work. Then
finish all concept/audit/implementation/accessibility requirements and the final
whole-branch independent review. The full plan remains active; the 100 inherited
failures and pending visual deliverables are not accepted final limitations.


## Durable human questions checkpoint

- Continued the active implementation plan; this is not plan completion. Started
  from e8ca5db and preserved user main/instruction copies. The user's model-choice
  question was checked against runtime_dependencies.py: host JSON `model` is
  global and restart-loaded; no web selector or per-project/agent override exists.
- Ruling: model a native information question as a durable pause, not a completed
  proposal or implicit authorization. Persist question + chat + operation receipt
  + authority withdrawal atomically; confirm waiting_input only after both owned
  peers close and no owned job is unknown. If this is too strict, the cost is an
  explicit new run after answering rather than a live waiting model turn.
- Ruling: answer records the literal question/answer pair, increments context,
  supersedes the prior run and does not submit inference. Unknown model usage keeps
  its budget ceiling; local teardown does not prove remote final billing.
- Migration 24 rebuilds the run status CHECK, preserving rowids/children/custom
  objects and restoring SQLite connection settings. Three migration tests passed
  after the initial FK-setting test fixture was corrected. Injected failure rolls
  back DDL/data/marker. A read-only source fixture copy upgraded 22→24 twice:
  all original rows/columns of 104 tables preserved, zero FK errors. User data was
  not migrated (question-migration-evidence.json).
- Domain tests observed RED→GREEN (7 missing-module failures before implementation).
  Coordinator tests observed RED→GREEN (2 missing-question-service failures).
  Owner API test observed RED→GREEN (missing question projection); MCP HTTP test
  observed RED→GREEN (missing endpoint). Tests exercise Stop/context precedence,
  unconfirmed closure, grant withdrawal, exact answer IDs, foreign scope, answer
  atomicity, idempotent receipts and denial of the legacy answer bypass.
- Real locked MCP catalog now has 11 business tools. Its schema check initially
  assumed $defs and failed; the live catalog inlines nested models. Corrected the
  checker to inspect the actual nested schema; it passes with zero model turns.
  No permission/effect elicitation is automatically accepted as a user answer.
- Web form renders every question group of the selected task, reasons/examples,
  choices and free text; no default answer. Submission freezes a copy and retains
  its key across an ambiguous receipt. New transport test observed RED→GREEN
  (prepareAnswer absent → valid immutable retry). Eight Node tests and build pass.
  No browser was available; no rendered/accessibility/comprehension claim.
- Live subscription trial questions-709512e4 passed: exactly two native dispatches
  with gpt-6.1-sol, first question → confirmed local closure → answer 200 (same
  answer POST repeated with no generation) → separate explicit instruction →
  quoted provisional finding and canonical draft with 200/42/242. Five same-thread
  messages retain typed delivery and context. Both grants revoked, no legacy
  agent events, task still in_progress, owned server terminal. No other model
  turns were submitted in this checkpoint (human-question-evidence.json).
- Final offline suite: 1,110 cases, 1,007 pass, same 100 baseline failure identities,
  three skip; no new/resolved failures (human-question-results.json). The complete
  suite remains red. Targeted new/changed code lint is checked separately; two
  preexisting blind-catch diagnostics remain in the guarded legacy user_requests
  endpoint. Packaged wheel bytes match 33 selected modules/resources, including
  all eight schemas (question-packaging.json). Existing Vite chunk/Browserslist
  warnings remain.

## Next brief after human questions

Continue the FULL implementation objective. Do not redo the working task research,
conversation, model provenance or question path. Add conservative owner recovery
for uncertain attempts (inspect native/job/tool receipts without prompt replay).
Then migrate all remaining legacy project/role orchestration and old writers,
all retained tool families, development/Git/review/CI acceptance, auxiliary
inference, backup/restore/bootstrap, every prompt/book-skill review and communication
comprehension evaluation. Native input requests outside researcher_ask_user still
fail conservatively; any adapter must preserve secret/permission boundaries.
Complete 36 desktop concepts plus 12 mobile references, selection, professional
implementation, browser/accessibility acceptance and final independent whole-branch
review. No final design claim, no accepted permanent baseline failures, no goal
complete/blocked/paused status. Model selection is still global JSON only.


## Peer ownership and research recovery checkpoint

- Previous goal turn classified as progress: 0e75769 implemented and verified human
  questions. Revalidated branch, status, ledger and plan constraints before work.
  The full implementation objective remains active; this is another checkpoint.
- Applied ken-plan-change and Release It! to separate authority, physical actor
  lifetime and known effects. Clean-context design reviewer review_recovery_contract
  verified that returncode/killpg does not prove setsid descendants closed, and
  thread/read plus revocation cannot substitute for physical closure. No final
  whole-branch implementation review has occurred.
- Ruling: contain each production native/business peer in a fresh PID namespace,
  with a trusted stdin gate and durable registration before G. No extra agent loop.
  Cost: Linux procfs/pidfd and Bubblewrap become runtime prerequisites; bootstrap
  and deployment readiness still need their full delivery. The namespace owns
  lifetime and does not replace existing filesystem/network/credential policy.
- A rejected-identity cleanup regression observed RED→GREEN: the launcher had
  retained a candidate before validation and could retire another fixture peer.
  It now verifies monitor parentage and only retains a fully accepted identity.
  A forged metadata test proves the other real namespace remains alive.
- Migration 25 adds peer scopes, records, recovery operations and protection against
  deleting live ownership history. Scope plus both required peers are prepared
  atomically. Kernel init identity is validated before bind; helper only consumes
  one byte and preserves the first actual RPC frame. EOF/timeout never exec payload.
  Parent-death linkage and namespace retirement cover detached descendants.
- Ruling: do not equate another boot ID with the original host rebooting. It can
  be a transferred DB. Differing kernel/observer remains unknown. Migration 26
  binds new peers to canonical DB path/device/inode hash; historical NULL remains
  unknown. A copied-DB test initially killed its original fixture peer (RED); the
  fixed test verifies rejection with the original still alive (GREEN). Handoff,
  in-place restore generation and cross-database workspace ownership remain open.
- Ruling: withdraw live tool authority as soon as the native run exits, before
  slow teardown. A real SQLite cached-scope regression observed RED→GREEN: native
  error plus blocked peer exit no longer admits a late business write. Cost:
  cleanup bookkeeping must remain host-only, outside the retired business grant.
- Injected failure preparing the second peer initially left a claimed attempt
  with no recoverable scope (RED). Production claim, scope and peer preparation
  now share one transaction (GREEN); failure leaves the original request queued,
  no attempt/grant/payload, and ordinary Stop can cancel it. The final actual
  zero-turn holder also uses this atomic claim path.
- Shared finalization/park now checks durable peer proof when the protocol is
  registered. Owner inspection and POST recovery are authenticated/CSRF protected,
  exact-attempt/fence scoped, idempotent and never issue turn/start. Read preflight
  precedes concurrent physical closure and durable intent; each result is drained.
  The API closure initially waited for a busy writer (RED) and now kills the init
  before that writer releases (GREEN). Disconnect keeps the owned control alive.
  A transient closure error initially stayed cached forever (RED); same-intent retry
  now rechecks current evidence and completes (GREEN).
- Ruling: local closure does not manufacture success, exit code, final remote usage
  or task acceptance. Stop/correction/current pending question determine outcome;
  otherwise retire failed with artifacts retained. Unknown usage keeps its ceiling.
  Unit tests restore a pending question without reusing its stale native handle.
- Added interim functional web inspection/recovery with frozen attempt/fence/key,
  known effects, blocked-origin reasons and no automatic mutation retry or inference.
  Nine Node tests and TypeScript/Vite build pass; existing chunk/Browserslist
  warnings remain. No browser, rendered/accessibility or comprehension acceptance.
- Native-boundary-7e6d4c9b passed actual Codex/Ken/business metadata and profile tests
  with zero generation under the v25 namespace boundary. Conversation-9e79317a
  passed through production HTTP/service with three POSTs/one subscription turn,
  exact captured quote, draft report, same-thread reply, correction and no replay.
  It preceded later origin/early-teardown hardening; those are not retroactively
  claimed as that trial's setup. Generative application evaluation turns this checkpoint: one, subscription
  only; no metered fallback. Ken's local embeddings are separate from model turns.
- Real SIGKILL/reopen/owner-HTTP recovery passed four times without generation:
  crash-recovery-788bf64b (v25), crash-recovery-d63a25b6 (v26 origin checks), and
  crash-recovery-fe2073f4 (v26 launcher-parent/cleanup checks), and
  crash-recovery-a01f39e9 (final v26 atomic claim/scope preparation).
  Original native thread, two peers, no dispatch replay, grants revoked, task still
  in_progress, duplicate recovery receipt stable and all owned servers terminal.
  Portable opt-in runner: evals/runtime/run_crash_recovery.py. Evidence is sanitized
  in recovery-evidence.json; private pairing/config/auth material is not committed.
- A source version-25 trial copy upgraded repeatably to 26 with all original rows/
  columns of 108 tables preserved, rowids intact, FK errors zero and old DB origins
  NULL (recovery-migration-evidence.json). No user database was changed.
- Final whole offline suite: 1137 tests, 1034 pass, same 100 baseline failures,
  3 skip; new/resolved failure identities empty (recovery-results.json). Suite
  remains red. An extra blocked external-connection warning is unassigned; the old
  HTTP size-limit test was strengthened to assert its actual limit error and passes
  alone without that warning. Do not infer an allowed network request or root cause.
  New focused regressions were observed fail before fixes; the first
  broad run was repeated only after additional origin and teardown changes. Selected
  changed modules pass Ruff; lock/diff checks pass. Wheel bytes match 32 selected
  files including all ten schemas (recovery-packaging.json). Generated tsbuildinfo
  is restored, not source. Instruction-copy directories remain untracked.

## Next brief: finish ownership, migrate remaining engine consumers, start design assets

Continue the FULL modernization objective. The current research conversation,
questions and same-DB/same-kernel recovery paths work; do not rebuild them or spend
more generation rediscovering their protocol. Keep all old evidence and failures.
Also persist repository/workspace selection in admission intent and add structured
startup/failure explanations and an explicit queued-start retry. Current atomic
preparation failures stay cancelable in queued; there is no auto-replay.
Next integrate command_executor into the same peer registry, link job ownership
and distinguish physically quiescent unknown results from live unknown jobs.
Remove remaining transport-only tree assumptions. Add cross-database workspace
exclusion and project start/stop/delete ownership; deletion currently has a SQL
ownership guard, but needs typed API/UX and safe filesystem cleanup. Preserve
lifetime budget history through deletion. Add verified deployment/restore generation
and handoff before allowing copied/restored state to act; kernel change is not
proof of original-host closure, and in-place rewind is not detected by inode alone.
Then migrate every legacy loop/role/writer, all 71 retained tool families,
development/Git/review/CI acceptance, auxiliary inference, bootstrap and historical
restore. Complete all prompt/book-skill and human comprehension evaluations.
Start the 36 desktop concepts plus 12 mobile references even if browser access
remains absent; then select, implement and verify all screens/accessibility when
available. Full synchronization and final independent whole-branch review remain.
No goal complete/blocked/paused status; no accepted permanent baseline failures.
