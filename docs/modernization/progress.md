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


## Visual task pilot checkpoint

- Previous goal turn was an informational model-configuration answer, with no
  authoritative implementation change. Revalidated the 1daf8f6 recovery commit,
  clean tracked worktree and full plan, then took the next safe design action.
  The full objective is unchanged; this checkpoint is progress, not completion.
- Applied imagegen, Product Design ideate/image-to-code and inline executing-plans.
  Product Design preflight has no saved visual context. CUA freshly returned no
  apps/browsers and “The browser access host is unavailable”. No Playwright or
  alternate UI automation was used; product screenshot audit remains pending.
- Ruling: defer unavailable source capture and prepare the explicitly requested
  new design from the code inventory and plan. Cost: rendered density, behavior
  and visual regressions must be checked and corrected once a browser is available.
  No concept is represented as a screenshot of the current product.
- Generated and inspected three independent desktop concepts for /tasks: editorial
  list/inspector, operational board and research notebook. Selected the editorial
  list/inspector using the plan's weighted criteria; selection.md records scores,
  tradeoffs and corrections. Ruling: select without asking for approval per screen,
  as explicitly delegated by the user. Cost: a taste mismatch remains correctable
  against concrete images and implementation.
- Generated and inspected one mobile adaptation with the selected image attached
  as reference. Four original PNGs, exact prompt texts, intrinsic dimensions and
  SHA-256 hashes are stored in docs/design/concepts/tasks. Built-in Image Gen does
  not return the exact image model; manifest model is NULL, with that limitation
  explicit. No CLI/API-key fallback or inferred image-model identifier.
- Ruling: preserve runtime truth over an incorrect mock control. The desktop image
  enabled Start while a proposal awaited review; production keeps its existing
  canStart guard. Context correction and a fresh instruction are separate actions.
  The mobile concept reflects that correction. Synthetic design data stays out of
  production. Cost: fidelity comparisons must distinguish intentional contract
  corrections from accidental layout drift.
- Replaced the task modal with an embedded labelled TaskInspector, a selectable
  task index, search and filters, a readable paper/ink/green theme and responsive
  task/list views. Sources and context become a secondary reading area that stacks
  when space is limited. Existing instruction/answer/correction/recovery identities
  and mutation paths remain intact. New tasks default to research, the currently
  supported native task type; the other types remain explicitly available.
- Project-keyed workspace remount prevents carrying the selected task or drafts to
  another project. List loading/error/filter changes keep the selected inspector
  mounted. Delete is a separate labelled button instead of a nested interactive
  span. Mutation errors remain visible; title/description edits close on success.
- Added a shared responsive navigation shell with a native popover menu, skip link,
  explicit project/activity labels and mobile activity overlay. Legacy project
  Start/Stop and other eleven page bodies still need their full migrations/redesign.
  Semantic structure is not a claim that the menu/focus/zoom is browser-verified.
- Two inspector regressions were observed RED then GREEN (embedded region and
  proposal/context admission guard). A failed task read previously rendered an
  endless spinner. Its SSR fixture initially exercised optimistic remount loading;
  after correcting retryOnMount, the prior 1daf8f6 component was rechecked and
  demonstrably failed the error test. Current inspector passes and provides retry
  plus return-to-list. Tests use actual React/query components via Vite SSR, not
  screenshot or browser emulation.
- Final frontend suite: 12 passed, 0 failed. TypeScript/Vite build passed, with
  existing Browserslist and chunk-size warnings. Seven listed static color pairs
  exceed 4.5:1 (minimum 6.03); this is not full WCAG acceptance. Exact source/log
  hashes and scope are recorded in the concept manifest. No backend code changed;
  the earlier backend suite remains red with its 100 recorded baseline failures,
  not reclassified as accepted or fixed by this frontend run.
- Application generative evaluation turns this checkpoint: zero. Four independent
  built-in image-generation calls; billing/model details not exposed by that tool
  are not inferred. No user database was migrated or populated. No model/test/server
  process is intentionally left running for a nonexistent browser handoff.
- Visual inventory now has 3/36 desktop concepts and 1/12 mobile adaptations, one
  selected pilot in code and 0/12 visually accepted routes. design-qa.md explicitly
  says final result: blocked for visual verification. Coverage remains in_progress;
  the full goal remains active.

## Next brief after the visual task pilot

Continue the FULL modernization objective. Do not regenerate the four saved task
concepts or rebuild the completed research conversation/questions/same-origin
recovery protocol. When browser access exists, capture the old/pilot flow with
synthetic data, compare against the selected desktop/mobile references, fix layout,
focus, keyboard, long/empty/error/correction/recovery states and perform human
comprehension checks. All eleven other routes still need three concepts each,
one mobile adaptation, reasoned selection, implementation and acceptance; shared
panels/dialogs need additional coverage. Structured explanation/diagram blocks and
accessible rendering remain pending. No complete-design or full-WCAG claim.
Meanwhile finish command-peer ownership and quiescence distinct from unknown exit
code, remaining transport lifetime assumptions, persisted repository admission,
explicit queued retry and structured failure explanations. Implement cross-database
workspace exclusion, project lifecycle/delete ownership, retained lifetime budgets,
verified deployment handoff/restore generation, and all legacy engine/role/tool
migrations. Complete all 71 tool families, Git/review/CI candidate acceptance,
subscription-only auxiliary inference, prompt/book-skill inventory and evals,
backup/restore/bootstrap, full synchronization and final fresh whole-branch review.
Resolve or replace the 100 baseline failures with evidence; they are not permanently
accepted. Model selection remains global JSON only. No goal complete/paused/blocked
status while meaningful work remains.


## Command peer ownership and quiescence checkpoint

- Previous goal turn classified as progress: commit 1032e0e saved four design assets
  and the task workbench pilot. Revalidated that commit, tracked status and the full
  next brief. This checkpoint advances command lifetime; it does not replace or
  narrow the modernization objective. No generative application turn was submitted.
- Applied ken-plan-change, Release It! and inline test-first verification. Connected
  Ken still indexes original main rather than the managed worktree; its search and
  blast-radius miss were followed by source reads and a manual caller inventory.
  All command_executor and OwnedCommandExecutor callers were migrated together.
- Ruling: command peers require an existing registered attempt scope, original lease,
  a bound namespace and an immutable job/peer link. Do not launch an uncontained peer
  while waiting to learn its owner from the first command. Cost: host callers must
  supply the lease up front; historical unlinked jobs are not silently upgraded.
  Registered unowned reservation and unscoped peer creation both demonstrated RED
  before the new guards passed. Tests/evals now use the same actual gate protocol.
- Migration 27 adds nullable peer_id and validation/immutability triggers. New scoped
  reservations check bound kind, attempt, fence and DB origin before commit. A retry
  resolves its original receipt without rebinding to another connection. Historical
  NULL stays NULL, including when a later caller tries to attach invented proof.
- Ruling: code of the command principal and actor closure are separate observations.
  CommandJob and owner inspection derive local_execution_closed from the durable
  namespace record. Closed unknown jobs can retire an uncertain attempt, preserving
  output and NULL exit code. Dispatching/cancelling without a receipt becomes unknown
  in the retirement transaction and emits job.quiescent. No success or task acceptance
  is manufactured; unlinked unknown jobs still block. Cost: callers must interpret
  both fields, and effects can still need human reconciliation after physical closure.
- The executor checks the trusted launcher prefix and original peer identity before
  initialization. It supervises the peer even after all command responses arrived,
  with a bounded authority query. A completed parent with a detached child is tested
  under both lease expiry and a busy DB writer; the delayed child effect is absent.
  A foreign attempt cannot borrow a bound peer and the original still executes.
- Ruling: cancelling a command closes its whole dedicated peer, including detached
  children, and forbids further dispatch there. Cost: a host needing a different
  operation must open a new peer with live authority; the cancelled/unknown operation
  is never replayed. Command integration explicitly opens a new peer after its known
  cancellation rather than pretending the cancelled connection is reusable.
- Physical namespace closure and transport teardown proceed concurrently. A DB write
  does not precede killing an already-bound actor. Control tasks remain owned/shielded
  when their supervisor is cancelled. Completed command responses retain their true
  code; failures remain unknown. Cancellation, output barriers and binary receipts
  preserve the earlier contracts.
- Registered native/command stdio transports no longer signal numeric process groups
  after reaping; the contained launcher is a direct child, and pidfd/namespace provides
  descendant proof. Native factory's controlled real-stdio test first failed the new
  flag assertion, then passed. The generic diagnostic transport keeps its historical
  fallback and the MCP SDK retains its own teardown; no universal closure claim.
- Actual pinned native command trial command-integration-7b135d2a passed: eight jobs,
  seven registered peers closed, project source separation, network denied, busy-writer
  physical Stop preceding unlock, detached child suppressed, other owner preserved,
  and connection loss revoking its business grant. Generation/dispatch count zero.
- Actual parent-loss-f4240efa killed only the directly owned host holder. The original
  command had started; its delayed effect was absent, its guard was terminal, and
  same-DB host RunRecovery retired the attempt failed with unknown/NULL plus physical
  closure. No replay or task acceptance; three registered peers closed. This trial's
  recovery driver is direct host control, not an owner HTTP smoke. Existing API tests
  cover authenticated common recovery controls; command-tool product wiring remains.
- All seven new tests pass in the final full suite: 1144 total, 1041 passed, identical
  100 baseline failure identities, three skipped, 29 warnings. All 216 runtime cases
  pass. The complete suite remains red; baseline failures are not accepted permanently.
  Failure-set comparison uses the same JUnit classname::name representation as the
  old evidence; a first analysis attempt incorrectly mixed pytest path IDs and was
  corrected before recording any comparison claim. Results preserve every failure.
- Frontend displays closure separately from unknown result and preserves original
  recovery intent; up to 25 jobs with explicit truncation. Twelve Node tests and
  TypeScript/Vite pass, with existing Browserslist/chunk warnings. No browser, keyboard,
  accessibility or comprehension acceptance. The earlier visual manifest remains
  historical evidence for its own checkpoint; no new image/visual approval is inferred.
- A read-only synthetic version-26 trial was backed up to a new rehearsal file and
  migrated repeatably to 27. Original values/rowids of all 108 data tables and FK
  integrity survive. The separate old-job fixture preserves binary bytes and NULL
  ownership. No user DB changed. Wheel bytes match 32 selected runtime/migration files,
  including all eleven SQL resources. Selected lint, offline lock and diff checks pass.
- Evidence: command-ownership-{evidence,results,migration,packaging}.json plus
  docs/architecture/command-peer-lifetime.md. All owned eval/test/build handles are
  terminal; all actual trial namespace records are closed. Generation turns this
  checkpoint zero, no API-key fallback. Four prior visual assets remain unchanged.

## Next brief after command ownership

Continue the FULL plan. Do not rebuild the verified native research conversation,
question/recovery paths or regenerate the saved task concepts. The new command
primitive now has registered ownership and separate quiescence/result facts; migrate
actual retained shell/tool and flow consumers onto it. Persist repository/workspace
selection in admission intent; add structured startup/failure explanations and an
explicit queued-start retry. Complete cross-database workspace exclusion, project
start/stop/delete ownership, lifetime budget retention and verified deployment/restore
handoff. Migrate remaining legacy loops/roles/writers, all 71 tool families, versioned
Git/review/CI candidate acceptance and subscription-only auxiliary inference. Complete
prompt/book-skill inventory and evaluations, communication/context comprehension,
backup/restore/bootstrap and full event synchronization. The 100 baseline failures
still need resolution or replacement with correct behavior. The UI still needs the
other 33 desktop concepts and 11 mobile adaptations, implementation of eleven other
routes/shared panels and browser/accessibility/human acceptance of every route,
including the existing pilot. Finish with fresh whole-branch independent review.
No complete/paused/blocked goal status while meaningful work remains; model choice
remains the verified global JSON setting, without a web/per-project selector.


## Durable admission checkpoint — 2026-11-01

- Previous implementation goal turn classified as progress: a644164 established
  command peer ownership. The intervening model-selection answer was read-only;
  it did not advance implementation. This continuation recovered pending admission
  changes and verified their authoritative source/log hashes rather than repeating
  completed trials. Full objective remains unchanged and active.
- Migration 28 atomically records original repository choice, registration path,
  canonical directory identity, historical name, request, conversation, receipt and
  event. Binding updates are forbidden; historical rows acquire no invented binding.
  WorkspaceRegistry now owns selection/validation and keeps its service import.
- Ruling: duplicate admission reads its receipt even while queued; starting queued
  work requires an explicit owner retry-start control. Cost: capacity becoming free
  does not drain a queue automatically. Same control identity never schedules twice;
  a confirmed unsuccessful control permits a new explicit decision with a new key.
- Ruling: an original automatic selection stays bound after catalog changes. Explicit
  repository identity is part of intent, and retries cannot substitute request/repo.
  Cost: changed or unprovable selection requires resolving the issue or a new request.
  Legacy receipts remain readable but cannot acquire an inferred historical binding.
- Revalidate original registration/directory at scheduling, claim and inference.
  SQL claim/inference/command reservation checks binding too. These checks do not
  pin an open directory, freeze content, prevent inode reuse or prove global ownership.
  Cross-database exclusion and deployment/restore generation remain required.
- Startup issues carry stable code, safe message, next action and observed inference
  state. Ruling: false only before dispatch, NULL for unknown history/unacknowledged
  dispatch, true only after observed native start. Cost: uncertainty remains visible;
  absence of a response is never zero consumption or permission to replay.
- RED→GREEN covered immutable repo intent, duplicate queued read, original selection
  after restart, changed registration/replaced directory, capacity, legacy unknown
  history, atomic binding/issue events, owner HTTP controls, immutable client retry,
  unsupported task type and three startup observation states. A shutdown test exposed
  a late worker published after threaded validation; owner is now rechecked immediately
  before publication. No await separates that check and publication.
- Task workspace shows original repository/request/context version, safe issue and
  explicit start retry. It does not claim all metadata is frozen: legacy task writers
  still need versioning/fencing. No selector web/per-project was added for model choice;
  the verified model setting remains global JSON loaded at serving startup.
- Independent clean-context read-only analysis mapped actual consumers and all 71
  individual tool classes in 11 categories, recorded in tool-migration-map.md. Earlier
  ledger wording “71 tool families” was imprecise. Host-owned command primitives are
  not yet connected to production model tools; next facade must preserve attempt
  ownership and avoid a second LLM loop. This is not the final whole-branch review.
- Final full-suite evidence: 1160 total, 1057 passed, identical 100 baseline failure
  identities, 3 skipped, 29 warnings; all 232 runtime cases passed. Thirteen frontend
  tests and TypeScript/Vite passed. Full suite remains red. Source hashes (15), log
  hashes (8) and all 35 selected packaged wheel file bytes were reverified here.
- Read-only synthetic v27 trial copied to a separate rehearsal then migrated twice
  to 28: all 108 original data tables preserve values/rowids; FK errors zero; no
  historical bindings/issues invented. No user DB changed. No application generative
  turn or image call this checkpoint; inference is doubled in DB/filesystem/ASGI tests.
- Browser was not exercised; no rendered, keyboard, accessibility or comprehension
  acceptance. Visual scope remains 3/36 desktop concepts, 1/12 mobile, zero accepted
  routes. Existing image manifest is historical evidence for its own source version.

## Next brief after durable admission

Continue the FULL modernization plan. First characterize/version/fence task metadata
writers: original request plus context_version is not a frozen task snapshot. Then
connect retained commands/tools through a host facade, with cross-database workspace
ownership and task capability policy before enabling mutable production capabilities.
Do not put execution in the credentialed business MCP, reuse legacy ambient context,
replay unknown jobs, or add a second model loop. Preserve original receipt identities.
Complete workspace/lock alias ownership, verified deployment/restore handoff, typed
project lifecycle/deletion and lifetime budget history; migrate all legacy loops,
roles/writers and 71 individual tools/11 categories. Implement exact-candidate
Git/review/CI acceptance, subscription-only auxiliary inference, full prompt/book-skill
inventory/evals, human communication/context comprehension, accessible structured
explanations/diagrams, backup/restore/bootstrap and complete event synchronization.
Resolve or replace the 100 baseline failures with correct behavior and evidence.
UI still requires 33 desktop concepts and 11 mobile adaptations, eleven remaining
route implementations/shared panels and rendered/mobile/keyboard/accessibility/human
acceptance of every route, including Tasks. Finish with a fresh independent whole-
branch review. No goal complete/paused/blocked status while meaningful work remains.


## Task input versioning checkpoint — 2026-11-01

- Continuing the full objective after b8f861e, which committed durable repository
  admission. Fresh verification of that checkpoint ran all 232 runtime cases with
  zero failures. The subsequent implementation below adds 23 cases; it does not
  complete the broader engine/context migration or narrow the original plan.
- Reproduced a concrete stale-context defect: changing task inputs during native
  work left context version unchanged and allowed the original result into
  needs_review. Initial new tests demonstrated 16 failures before the new boundary.
- Ruling: all UPDATE writers cross one SQLite task-input boundary, including legacy
  SQL. Thirteen fields (documented explicitly) advance context exactly once per
  changed row/statement; no-op/operational progress writes do not. Cost: changes to
  scheduling/assignment fields conservatively invalidate work too. Related objects
  and external files still require their own contracts; this is not a full frozen
  context claim. Legacy writers still must migrate to typed product commands.
- Migration 29 atomically preserves before/after, version and event; revokes grants,
  fences affected runs, supersedes queued/proposal/waiting work, leaves active work
  reconciling and expires pending questions. Event failure rolls back all those
  changes and the task edit. History rejects UPDATE. No historical edits are inferred.
- Ruling: task metadata proves a database write and its values, not user testimony.
  Actor remains NULL, source_kind task_metadata, while explicit examples/corrections
  retain their verified submission source classifications and references. Cost:
  author attribution awaits typed, authenticated editing receipts. Shared version
  order interleaves changes and explicit corrections without relabelling either.
- context_snapshot now sends all thirteen tracked fields plus status, metadata
  before/after and the original correction history. Owner API notices a committed
  input change and interrupts its local worker. Direct/legacy writers still revoke
  authority immediately in SQL; physical interruption is separately detected by
  existing heartbeat/command supervision. No universal immediate-preemption claim.
- Fencing alone initially left a late native completion in reconciling. Its RED test
  drove host-only retire_withdrawn: after actual peer closure it derives Stop/context
  precedence from durable state before processing a native result or local callback
  outcome. No closure proof means no retirement. No replay, new turn, task done or
  acceptance is manufactured. Next explicit request receives current input/history.
- Owner-edit interruption and frontend concrete before/after/unknown-author display
  each failed before implementation, then passed. React SSR checks actual inspector
  integration and escaping; frontend invalidates workspace data after task edits.
  History text distinguishes invalidation from confirmed physical stop.
- Old migration fixtures now explicitly exclude the future v29 resource while
  constructing v23/v26/v27 fixtures. The old queued-type test intentionally changes
  expectation: a type edit now supersedes the old request before explicit start,
  rather than leaving it queued with an unsupported-type issue. New guard remains
  research-only. These were five initial compatibility failures, all addressed.
- Final full suite: 1183 total, 1080 passed, identical 100 baseline failure identities,
  3 skipped, 30 warnings; all 255 runtime cases passed. Exact comparison and all
  failing names are in task-inputs-results.json. Existing socket-denial warnings,
  deprecated Starlette/httpx integration and unknown integration mark remain visible.
  The full suite is red; its 100 failures remain required work, not accepted defects.
- Frontend: 14 passed, zero failed; TypeScript/Vite build passed with existing
  Browserslist/chunk warnings. Selected runtime/test/loader Ruff passed. The changed
  legacy task route retains five lint findings, compared against b8f861e with identical
  codes/messages (F401 x1, S110 x2, BLE001 x2); no global lint-green claim.
- Rehearsed v28→29 twice on a separate copy of the prior synthetic trial. All 109
  original data tables preserve values and available rowids, including 16 WITHOUT
  ROWID tables checked by ordered primary keys; old migration rows preserved, FK
  errors zero, no historical task changes invented. First analysis incorrectly
  queried rowid universally; it failed before applying migration, then used the
  proper table metadata and verified the copy against the read-only source.
- Wheel bytes match all 37 selected runtime/SQL/loader/owner-route files, including
  the new packaged resource. Evidence hashes 18 source files and ten complete logs.
  No user DB or original checkout changed; no new application inference or images.
  All observed test/build handles are terminal; no server is intentionally left live.
- Browser/human verification remains unperformed. Design inventory remains 3/36
  desktop concepts, 1/12 mobile, zero visually accepted routes. The final fresh
  independent whole-branch review is still pending after the complete implementation.

## Next brief after task input versioning

Continue the FULL plan. Do not redo schema28 admission, schema29 direct task-input
versioning, native research conversation/question/recovery or the four saved Task
concepts. Complete related context dependencies (task dependencies, project/epic
content, source/files/Git/permissions), typed editing commands with concurrency and
receipts, verified actor provenance and the effective-context snapshot. A number
alone is not proof that all inputs are frozen. Then wire actual retained command
consumers through a host-owned facade without a new LLM loop; enforce cross-database
workspace ownership and task capability policy before production mutable tools.
Complete owner-lock aliases, verified deployment/restore generation, project lifecycle
and safe deletion, retained lifetime budgets, all legacy engine/role/writer consumers
and 71 individual tools in 11 categories. Implement exact-candidate Git/review/CI
acceptance, subscription-only auxiliary inference, full prompt/book-skill inventory
and evals, communication/comprehension and accessible structured diagram rendering,
backup/restore/bootstrap, complete event synchronization/pagination/retention, and
resolve/replace the 100 baseline failures with correct behavior. UI still requires
33 desktop concepts plus 11 mobile adaptations, all eleven other route bodies/shared
panels and rendered/mobile/keyboard/accessibility/human acceptance of every route
including Tasks. Final fresh independent whole-branch review before integration.
Model selection is verified global host JSON, restart required, with no web/per-agent/
project selector. Keep full goal active; no complete/paused/blocked status while
meaningful work remains. Do not push, merge or deploy without the appropriate scope.


## Conversation design and question inbox checkpoint — 2026-11-01

- Previous goal turn classified as progress: b8f861e and d0f1161 committed durable
  admission and atomic direct task-input versioning. Verified HEAD/tracked status,
  ledger and existing implementation before moving to the explicit full web-redesign
  requirement. No active process was inferred from an old log; new test/build handles
  were polled to terminal. Full objective remains active, not redefined as a pilot.
- Used Product Design/get-context/ideate/image-to-code and built-in ImageGen. Saved
  context preflight reports no user-context.md. Fresh CUA inventory again returns
  apps=[], browsers=[], browser access host unavailable. No app screenshot exists.
  Existing Tasks concept was opened directly and attached as style reference to
  each independent desktop generation, not misrepresented as a running UI capture.
- Ruling: user explicitly delegated choosing the best generated concept; do not
  ask again for a numbered selection. Continue the authorized existing-repo build
  without a new starter or deployment, while visual verification stays blocked.
  Cost: rendered fidelity/accessibility/comprehension cannot be accepted until a
  real browser comparison exists. design-qa.md records this limit and exact skill gate.
- Generated, displayed, inspected and copied four independent images to the project:
  conversation-with-evidence, case-notebook, intervention-desk and a mobile adaptation
  of the selected first concept. Three desktop1487×1058 native rasters target1440×1024;
  mobile853×1844 targets390×844. Full prompts, attached references, file hashes and
  actual sizes preserved in concepts/chat/manifest.json. Exact image model/billing
  metadata were not exposed and are not inferred; no API-key/metered fallback.
- Selected conversation-with-evidence (88.5 weighted concept expectation vs81.5/68).
  Ruling: no verified hypothesis, confidence or source is invented to fill the gutter.
  Intervention-desk incorrectly calls absence of a stable key proven; its assumption
  inflation was a reason to reject it. Cost: production uses only actual captured
  provenance and may have fewer sections than an attractive but false mock.
- Replaced old dark task selector plus collapsed project history/dead reply handlers
  with task index, project-wide paginated pending requests, visible chronological
  current exchange, real source/context gutter and read-only archive. Paper/ink/green
  tokens, editorial headings, separators, natural reading measure, container-based
  context stacking and mobile return preserve the selected direction. No synthetic
  Atlas data or generated mock text is inserted into production.
- New owner-only GET /api/projects/{p}/questions is available without inference config.
  One page is a read transaction with count, stable ID cursor and bounded results.
  Every native item keeps original request/task/run/thread/current and asked context,
  typed question IDs/options and readiness. Waiting for physical closure is distinct
  from ready to answer. No reread starts/answers/replays work; tools bearer is denied.
  Legacy requests remain visible with no inferred task/context; option objects are
  not reduced to display labels. Their typed reply/producer migration remains pending.
- Ruling: an inbox row is a navigation pointer, not an authorization receipt. Answer
  still uses the exact existing project/task/question/version mutation contract.
  Cost: workspace/controller must revalidate after navigation; stale page data can
  never authorize a response. Choosing project/task remounts drafts and a foreign
  task URL cannot mount its workspace. Current question controls retain stable IDs.
- Current messages distinguish sender, receipt, task and context. Old results are
  conserved, never declared current/accepted. Other tasks in the same thread are
  labelled explicitly. Pending question text is shown by its typed controls rather
  than twice. Current proposal is not duplicated when its exact receipt is visible;
  durable proposal remains available if history fails. No automatic scroll-to-bottom
  on every poll. Programmatic question/title focus is coded but not browser-verified.
- Ruling: visible history is not proof of delivered/applied shared model context.
  UI states what the next work currently receives (task, revisions/corrections and
  answers); effective-context snapshot and full conversation continuation are still
  pending. Cost: general notes/proposals in the archive must not be implicitly treated
  as instructions or approvals. No second inference loop was added to implement chat.
- Four backend tests observed RED for missing inbox/route after correcting fixture
  native bindings and required legacy fields, then GREEN. They cover multiple tasks,
  readiness, project scope, cursor, legacy values, expiry/answers, owner/bearer guards,
  invalid limits and no inference reservation. Eight focused API/workspace cases pass.
- Three actual SSR failures drove visible exchange, all pending tasks and explicit
  history errors; foreign-task guard also stays covered. Four new frontend cases
  pass alongside all previous14. React Router's installed node export needed test-
  only ESM aliases; Zustand SSR initial state is restored after each render. Both
  fixture Vite servers now disable WS explicitly; an initial parallel port collision
  is absent from the final logs. No testing adaptation changes production routing.
- Final full suite1187 total:1084 passed, identical100 baseline failure identities,
  three skipped,29 warnings; all259 runtime cases pass. Final frontend18 passed,
  zero failed; TypeScript/Vite1250 modules passes with existing Browserslist/chunk
  warnings. Selected Ruff/diff checks pass. Full suite remains red; task creation/
  legacy inference/tool failures still require real resolution, not permanent waiver.
- All37 selected packaged runtime/SQL/loader/owner-route files match current source
  bytes. Schema stays29; this read projection adds no migration or historical rewrite.
  No user DB changed. Application inference turns0, built-in image calls4. Hashes bind
  fourteen changed source/test files and seven final/RED logs to this checkpoint.
- Visual inventory now6/36 desktop concepts,2/12 mobile adaptations,2 selected pilots
  in code and0/12 accepted routes. CUA absence blocks visual comparison, focus/keyboard/
  zoom/screen reader and human comprehension acceptance. No preview server is left
  live or handed off as verified. All observed test/build handles are terminal.

## Next brief after Conversation

Continue the FULL original modernization goal. Do not regenerate the eight saved
Task/Conversation concept assets or rebuild existing schema28/29/native research/
question/recovery contracts. The remaining ten routes require30 independent desktop
concepts,10 mobile adaptations, reasoned selection and real implementation, plus
all shared panels and rendered/mobile/keyboard/accessibility/human acceptance of
all twelve routes. Recheck browser availability before visual claims; source/SSR/
build cannot substitute capture and comparison. No design completion from pixels alone.

Close effective input snapshot and explicit conversation continuity: current visible
archive is not automatically all sent to the next model. Complete related context
revisions (dependencies, project/epic, sources/files/Git/permissions), typed editing
with concurrency/receipts and verified author provenance. Migrate legacy questions,
role/project conversations and full event synchronization/history pagination/retention.
Connect actual retained commands/tools through the host facade with cross-database
workspace exclusion and task capability policy before mutable production capabilities.
Finish lock aliases, deployment/restore generation, typed project lifecycle/deletion,
lifetime budgets, all legacy engine/role/writer consumers and71 individual tools/11
categories; exact-candidate Git/review/CI acceptance; subscription-only auxiliary
inference; every prompt/book-skill inventory/rewrite/eval; human communication and
accessible structured explanations/diagrams; backup/restore/bootstrap. Resolve or
replace100 baseline failures with correct behavior. Final fresh independent whole-
branch review before integration. Model remains global host JSON/restart, no selector
web/per-agent/project added. Full goal stays active; no complete/paused/blocked status
while meaningful authorized work remains. No push/merge/deploy performed.


## Frozen input and continuity checkpoint — 2026-11-01

- Previous goal turn classified as progress: 3d37ca3 saved Chat concepts/pilot and
  scoped project inbox. Revalidated HEAD/ledger/source before addressing the explicit
  missing effective-input/continuity contract. Full goal remains unchanged and active.
- Applied inline test-first, Ken change planning (index still original main; no indexed
  match for new store), A Philosophy of Software Design mini and current OpenAI Docs
  prompt guidance fetched from its official page. No alternate model/API-key route.
- Ruling: record the exact Researcher initial text, developer instructions and business
  catalog, not a claim about hidden native system content, every Ken schema, future
  tool results, understanding or acceptance. Cost: broader provenance still needs
  separate records; the inspection UI explains this boundary instead of overclaiming.
- Migration30 adds immutable input snapshots tied to dispatch. reserve_input owns
  authority/scope, one-turn budget, context/history composition, snapshot and event
  in one SQL transaction. Event/oversize failure leaves no partial reservation or
  budget. The coordinator sends the returned text verbatim, with no reconstruction
  after reservation. Diagnostic reserve_inference remains non-generative compatibility;
  production uses the complete operation. Exact native instructions/catalog exposure
  was verified against the real stdio thread/start request (RED→GREEN).
- run_inputs.py owns shared message projection and continuity/format/limit policy;
  views preserves MESSAGE_SELECT import compatibility. Source revisions/examples/
  assumptions keep classification. The new native prompt explains how current request,
  corrections and historical constraints relate, without another LLM summary/loop.
- Ruling: conversation cutoff is the current admission message ID. Include earlier
  same-task native exchanges and unattributed records; exclude/count other tasks and
  never infer a product conversation from a native thread. Cost: later notes are not
  delivered as steering; use the correction controls. A mixed-task legacy fixture
  resets its old unbound marker deliberately; normal admission still forbids retargeting
  a native conversation to another task. No production scope was widened for the test.
- Ruling: preserve complete included messages or refuse before generation. Up to200
  previous messages/1MiB combined host input; no silent suffix loss or hidden LLM
  summary. Cost: long history needs explicit separation/new task or future checkpoint/
  compaction. UI can start without prior conversation while retaining task/corrections/
  answers, and explains carrying forward important conditions. These local byte fuses
  do not establish model-specific token-window fit or physical billing limits.
- Seven initial input tests failed before new API/format/persistence. Controls tests
  exposed an initially false no-start claim for an existing reservation; dispatch
  existence now preserves unknown and never replays. Owner read route returns no_record
  for old rows without inventing input. Input content/hashes survive message edits and
  context correction; snapshot UPDATE is rejected. Owner API is authenticated/no-store.
- Initial focused suite40 passed; eight historical migration cases pass. Old fixture
  constructors exclude future30 explicitly, while migration29 asserts its own marker
  rather than assuming it will forever be the maximum version.
- Actual input-continuity-1fff674c passed via owned HTTP/server, Codex0.166.0,
  gpt-6.1-sol, published Ken0.18.0 and existing subscription. Two native turns, no replay
  or metered fallback. First uses base137; second current request omits137 and receives
  two earlier records plus a user_example correction to200. It correctly explains
  policy28.77/165.77 vs42/242 and code's direct addition137.21/200.21. Both reports
  remain draft; task not done, four peers closed, all grants revoked, source files
  unchanged. Original frozen input remains identical after correcting context.
- Real native reported total tokens117774 and95739 are observed usage, not billing/
  quota accounting. Correct output does not isolate the history's causal influence
  because business tools could also read the recorded source/report. No universal
  prompt-quality or human-comprehension result is inferred from this single scenario.
- Live handle30827 was terminal exit0. A concurrent DB read had sampled running just
  before that exit; after completion the DB was reread sequentially and confirmed
  superseded/needs_review plus four closed peers. No stale sample was treated as a
  live job or reason to restart. All observed test/build/trial handles are terminal.
- Final complete suite1198:1095 passed, identical100 baseline failure identities,
  three skipped,30 warnings; all270 runtime cases pass. Frontend20 passed plus TS/Vite
  build; existing Browserslist/chunk warnings remain. New input-inspection/explicit
  conversation-choice SSR tests observed RED then GREEN. No browser interaction,
  keyboard/accessibility or human acceptance is claimed.
- Rehearsal v29→30 twice on a new copy preserves110 original data tables, values and
  available rowids (16 WITHOUT ROWID tables checked by PK), old markers and FK
  integrity. No inferred historical input and no user DB changed. All39 selected
  runtime/SQL/loader/owner-route wheel bytes match current source. Source/log hashes
  bind25 changed source/test files and11 complete logs. No image calls this checkpoint.
- User requested planned/done/missing list. Saved docs/modernization/status.md against
  the actual plan/evidence, distinguishing implemented components from complete phases.
  Updated coverage's stale pending items for the now-recorded runtime choice and
  initial input/context evaluation; no blanket completion of engine/tools/prompts/UI.
- Design inventory remains6/36 desktop,2/12 mobile,2 pilots in code and0/12 accepted
  routes. No push, merge or deployment; original user checkout/data were preserved.

## Next brief after frozen input

Continue the FULL modernization plan. Do not redo native research/questions/recovery,
repository admission, schema29 task-input versions, schema30 input/continuity or the
8 saved visual assets. Read status.md and coverage for real scope; many phases remain
partial. Current host input is exact, not hidden provider context or future outputs.
Long history needs explicit evidence-preserving checkpoints/compaction, broader
project/dependency/source/file/Git/permission invalidation and verified author receipts.
Complete typed editing and legacy question/role/project communication migration plus
full event catch-up/history pagination/retention. Connect retained command/tool consumers
through a host facade, cross-database workspace exclusion and task capability policy
before mutable production tools. Finish owner aliases/handoff/restore generation,
project lifecycle/deletion/lifetime budgets, all legacy loops/roles/writers and71
individual tools/11 categories, exact-candidate Git/review/CI acceptance, subscription-
only auxiliary inference, full prompt/book-skill inventory/rewrite/held-out evals and
human comprehension/structured accessible diagram rendering, backup/restore/bootstrap.
Resolve or replace100 baseline failures with correct behavior. UI still needs30 desktop
concepts and10 mobile adaptations for ten other routes, all shared panels and actual
rendered/mobile/keyboard/accessibility/human acceptance of all12 routes. Final fresh
independent whole-branch review before integration. Model remains global host JSON/
restart with no web/per-agent/project selector. Goal active; no complete/paused/blocked
status while meaningful authorized work remains. Do not infer native delivery from
prepared input, observed start from missing receipt, or understanding from good output.


## Host-owned analysis tools — base4d9127b

- Previous user turn was a requested status report, not implementation progress.
  This goal turn adds the actual host tool consumer rather than re-planning it.
- AnalysisTools exposes strict start/read/cancel/Python schemas. ProjectTools joins
  them with eleven business schemas before thread/start, checks unique names and
  hashes the combined catalog. Diagnostic sessions without AttemptPeers retain the
  old eleven-tool catalog; production scopes have fifteen. Resume checks the exact
  combined hash. The historical business_catalog API/SQL name is retained.
- Ruling: research calculations/diagnostics use an explicitly read-only workspace,
  no network/inherited credentials, host-selected isolated standard-library Python
  and explicit public toolchain read mount. This is a retained analysis capability,
  not a substitute for writable development, scientific packages or output artifacts.
  Those still require global workspace ownership/capability policy and acceptance.
- Each job owns one native peer. Identical receipt lookup happens before opening
  another peer; changed intents conflict, unknown/previous connections never replay.
  Model reads require current authority before/after; owner recovery remains separate.
  Canonical output persists at termination, not live incremental streaming. Windows
  preserve exact bytes/base64 and mark lossy UTF-8; closed/exit/result/acceptance differ.
- Terminal reads and scope exit close all descendants, even detached children after
  exit0. Cancellation of a reader keeps a shielded, joinable cleanup task. Unknown
  command results revoke authority; zero exit still does not accept the task.
- Nineteen initial facade cases failed because the implementation was missing;
  wiring failed for absent schemas. Extra RED cases caught malformed envelopes,
  missing cwd and cancelled cleanup. Fixed and included in the full suite. Source-
  level lineage search reached ExecuteCommandTool but the new runtime is not indexed
  by connected Ken; manual callers/source verified, no broad reindex was attempted.
- Real no-inference CLI probe first completed six cases then hit peer capacity.
  Initial public hypothesis of lease expiry was wrong: timestamps showed3sec and
  source showed the eight-row historical cap. Ruling: eight peers without closure,
  up to128 retained receipt rows per attempt. Nine sequential jobs verify reuse of
  physical capacity without deleting evidence. Fresh real CLI probe64c1776c passed
  all7 calculation/read/write-denial/external/symlink/network/environment cases,
  including poisoned local permissions. No model calls in these probes.
- Full suite1227:1124 passed, same100 baseline identities,3 skipped,29 warnings.
  All299 runtime tests pass. No new or resolved baseline failures; all100 names are
  in analysis-results.json. Lint passes for changed Python; wheel contains identical
  bytes for all23 runtime modules. No schema migration/new user database changes.
- Actual analysis-inference-7792402f submitted one subscription turn (gpt-6.1-sol),
  mandatory published Ken0.18.0 and pinned Codex0.166.0. Native code-mode trace confirms
  actual Ken read/recall and returned invoice source. One host Python job printed
  tax28.77/total165.77/code137.21; one report remains draft, task not done, sources
  unchanged, grants revoked, all3 peers closed. Reported180751 tokens are observed
  native usage, not billing/quota accounting. No hidden/internal trace content copied.
- The generative harness failed after successful completion by querying reports.id
  instead of artifact_id. Fixed the harness; verified the existing terminal DB and
  exact native thread trace with --verify-root, zero extra generation. Original
  failure evidence preserved and hashed. Its repeated HTTP receipt check was not
  reached; receipt tests are separate evidence. No second run was used to hide it.
- Bound11 changed source/test/eval files and16 logs, with separate native/live/suite/
  packaging reports. No image calls, frontend edits, visual or human acceptance.
  All observed test/build/trial handles are terminal; no server intentionally left.

## Next brief after host analysis

Continue the FULL modernization plan. New production research sessions have15
project tools plus mandatory Ken; old sessions cannot silently resume with changed
catalog. The analysis profile is read-only/standard-library and jobs have terminal
output persistence. Do not redo input/context/chat/tasks work or the8 saved concepts.
Next connect owner output windows and UI/read-only recovery, broaden real Stop/
correction/unknown-receipt scenarios and migrate actual retained command consumers.
Before mutable tools, finish cross-database workspace ownership and capability policy;
then exact-candidate edits/tests/review/Git/CI acceptance. All71 tools/11 categories,
legacy engine/roles/flows/autonomy, coordination, typed edits and related-context
invalidation, long-history checkpoints, external effects, lifecycle/deletion/budgets,
backup/restore/bootstrap, subscription-only auxiliary calls and full prompt/book-skill/
held-out/human communication acceptance still remain. Resolve/replace100 original
failures correctly. Visual scope remains6/36 desktop+2/12 mobile,2 pilots and0/12
accepted pages; produce30 desktop+10 mobile, implement10 other routes/shared controls
and verify all12 pages with browser/mobile/keyboard/accessibility/human acceptance.
Final fresh whole-branch review remains required. Model is host-global JSON/restart,
not per-agent/project or web-selected. No push, merge or deployment. Keep goal active.


## Host-owned analysis tools — base4d9127b

- Previous user turn was a requested status report, not implementation progress.
  This goal turn adds the actual host tool consumer rather than re-planning it.
- AnalysisTools exposes strict start/read/cancel/Python schemas. ProjectTools joins
  them with eleven business schemas before thread/start, checks unique names and
  hashes the combined catalog. Diagnostic sessions without AttemptPeers retain the
  old eleven-tool catalog; production scopes have fifteen. Resume checks the exact
  combined hash. The historical business_catalog API/SQL name is retained.
- Ruling: research calculations/diagnostics use an explicitly read-only workspace,
  no network/inherited credentials, host-selected isolated standard-library Python
  and explicit public toolchain read mount. This is a retained analysis capability,
  not a substitute for writable development, scientific packages or output artifacts.
  Those still require global workspace ownership/capability policy and acceptance.
- Each job owns one native peer. Identical receipt lookup happens before opening
  another peer; changed intents conflict, unknown/previous connections never replay.
  Model reads require current authority before/after; owner recovery remains separate.
  Canonical output persists at termination, not live incremental streaming. Windows
  preserve exact bytes/base64 and mark lossy UTF-8; closed/exit/result/acceptance differ.
- Terminal reads and scope exit close all descendants, even detached children after
  exit0. Cancellation of a reader keeps a shielded, joinable cleanup task. Unknown
  command results revoke authority; zero exit still does not accept the task.
- Nineteen initial facade cases failed because the implementation was missing;
  wiring failed for absent schemas. Extra RED cases caught malformed envelopes,
  missing cwd and cancelled cleanup. Fixed and included in the full suite. Source-
  level lineage search reached ExecuteCommandTool but the new runtime is not indexed
  by connected Ken; manual callers/source verified, no broad reindex was attempted.
- Real no-inference CLI probe first completed six cases then hit peer capacity.
  Initial public hypothesis of lease expiry was wrong: timestamps showed3sec and
  source showed the eight-row historical cap. Ruling: eight peers without closure,
  up to128 retained receipt rows per attempt. Nine sequential jobs verify reuse of
  physical capacity without deleting evidence. Fresh real CLI probe64c1776c passed
  all7 calculation/read/write-denial/external/symlink/network/environment cases,
  including poisoned local permissions. No model calls in these probes.
- Full suite1227:1124 passed, same100 baseline identities,3 skipped,29 warnings.
  All299 runtime tests pass. No new or resolved baseline failures; all100 names are
  in analysis-results.json. Lint passes for changed Python; wheel contains identical
  bytes for all23 runtime modules. No schema migration/new user database changes.
- Actual analysis-inference-7792402f submitted one subscription turn (gpt-6.1-sol),
  mandatory published Ken0.18.0 and pinned Codex0.166.0. Native code-mode trace confirms
  actual Ken read/recall and returned invoice source. One host Python job printed
  tax28.77/total165.77/code137.21; one report remains draft, task not done, sources
  unchanged, grants revoked, all3 peers closed. Reported180751 tokens are observed
  native usage, not billing/quota accounting. No hidden/internal trace content copied.
- The generative harness failed after successful completion by querying reports.id
  instead of artifact_id. Fixed the harness; verified the existing terminal DB and
  exact native thread trace with --verify-root, zero extra generation. Original
  failure evidence preserved and hashed. Its repeated HTTP receipt check was not
  reached; receipt tests are separate evidence. No second run was used to hide it.
- Bound11 changed source/test/eval files and16 logs, with separate native/live/suite/
  packaging reports. No image calls, frontend edits, visual or human acceptance.
  All observed test/build/trial handles are terminal; no server intentionally left.

## Next brief after host analysis

Continue the FULL modernization plan. New production research sessions have15
project tools plus mandatory Ken; old sessions cannot silently resume with changed
catalog. The analysis profile is read-only/standard-library and jobs have terminal
output persistence. Do not redo input/context/chat/tasks work or the8 saved concepts.
Next connect owner output windows and UI/read-only recovery, broaden real Stop/
correction/unknown-receipt scenarios and migrate actual retained command consumers.
Before mutable tools, finish cross-database workspace ownership and capability policy;
then exact-candidate edits/tests/review/Git/CI acceptance. All71 tools/11 categories,
legacy engine/roles/flows/autonomy, coordination, typed edits and related-context
invalidation, long-history checkpoints, external effects, lifecycle/deletion/budgets,
backup/restore/bootstrap, subscription-only auxiliary calls and full prompt/book-skill/
held-out/human communication acceptance still remain. Resolve/replace100 original
failures correctly. Visual scope remains6/36 desktop+2/12 mobile,2 pilots and0/12
accepted pages; produce30 desktop+10 mobile, implement10 other routes/shared controls
and verify all12 pages with browser/mobile/keyboard/accessibility/human acceptance.
Final fresh whole-branch review remains required. Model is host-global JSON/restart,
not per-agent/project or web-selected. No push, merge or deployment. Keep goal active.


## Owner command inspection — base b243ce3

- The preceding goal turn made implementation progress (b243ce3). This turn adds
  the actual owner reader rather than another status-only continuation. Full scope
  remains the original modernization plan.
- OwnerRuntimeView now provides paginated job metadata and bounded stdout/stderr
  windows, scoped jointly by project/run/job. New GET routes require owner session,
  reject agent bearer access and return no-store. Reads work after Stop/lease loss,
  unknown result and with the runtime unconfigured; no control or replay is exposed.
- SQL reads only BLOB substr windows, not full output. Shared command_output encoding
  preserves model reader compatibility, base64 bytes and lossy UTF-8 flags. Focused
  investigation proved substr(X'',1,8) is NULL in installed SQLite; COALESCE restores
  legitimate empty windows. The large-output/unknown tests caught this actual failure.
- Ruling: public sequence cursors are decimal strings. A RED case with rowid
  9007199254740993 caught the original JSON-number design; IDs beyond JS safe integer
  precision now paginate exactly. Server accepts bounded SQLite integer cursor strings;
  frontend preserves them literally. This does not claim all legacy entity IDs in
  the web app have undergone a general64-bit identity migration.
- Fourteen owner HTTP cases cover binary/multibyte output, partial unknown receipts,
  no authority revival,27-job pagination, scope/session/bearer separation, limits and
  4MiB tail counterevidence. Initial negative scope/auth cases already passed through
  existing middleware; positive reader cases were RED before routes existed. Explicit
  path annotations now reject malformed IDs with422 instead of generic ValueError400.
- RunCommands/CommandReceipt integrate into current and historical task work. Reads
  are lazy; windows can go forward/back/to tail. Original args/base64 expand separately.
  Capture loss, partial read, exit code, closure and acceptance remain distinct. Raw
  HTML stays text; terminal/bidi controls are visible escapes. Changing scope resets
  selection/offsets/placeholders. Same-job transitions label old bytes while loading;
  closing the inspector stops its receipt polling. User selection can move focus;
  polling never moves focus/scroll. Errors offer GET again, not command execution.
- Final complete suite1241:1138 passed, identical100 baseline identities,3 skipped,
  29 warnings; all313 runtime tests pass. Frontend28 passed plus TypeScript/Vite build.
  Existing Browserslist/chunk-size warnings remain. All25 selected wheel sources
  (24 runtime modules and owner route) equal current source bytes. No new migration.
- Actual HTTP probe owner-command-inspection-352bc3ed uses a new copy of prior real
  native trial7792402f and an owned local server with runtime unconfigured. Fourteen
  requests of7-byte windows reconstruct all95 bytes. Recorded closure/exit0 survive;
  anonymous/bearer401 and cross-project404 are real HTTP responses. Fingerprints of
  nine tables in original/copy stay unchanged, no new inference/image call, source
  fixture/user DB unchanged. The first probe f5109066 also passed before cursor types
  changed; the final recheck verifies the changed wire contract, not a replay of work.
- Fresh CUA inventory: apps=[],browsers=[], browser host unavailable. CLI discovery
  found no Chromium/Chrome/Playwright on PATH or project dependency. No rendered,
  keyboard/mobile/accessibility/human acceptance. Official Playwright browser-install
  docs were consulted: https://playwright.dev/docs/browsers . Investigate an isolated
  container test browser as fallback; unavailable CUA is not a reason to stop backend
  work or call the complete modernization blocked.
- Bound12 source/test/eval files and13 final/relevant logs; separate suite/HTTP/wheel/
  QA reports preserve evidence limits. Source/log hashes verified before commit. All
  observed test/build/probe handles terminal; no server intentionally left running.
  Generated tsbuildinfo restored to its recorded version; instruction copies untouched.

## Next brief after owner command inspection

Keep the FULL modernization objective active. The read-only analysis facade, frozen
input/continuity, owner receipt API/UI, source/context/chat/tasks pilots and all8
concept assets exist; do not redo them. New job cursors are strings, not JS numbers.
Owner read is independent of agent authority and copied proof does not grant control.
Try an isolated Playwright/Chromium test tool using official installation docs to
unblock actual UI captures/interaction checks; CUA host is unavailable and no test
browser was detected, but no installation/launch was attempted this turn. Retain
zero accepted routes until actual visual/interaction/accessibility/human criteria
are met. Next backend priority is global workspace exclusion/ownership/capability
policy before mutable development tools, plus production Stop/correction/unknown
jobs and actual migration of retained consumers. All71 tools/11 categories and
legacy engine/roles/flows/autonomy/coordination still need completion; exact Git
candidate/base/head/context review/CI acceptance, typed edits and related-context
invalidation, long-history checkpoints, external effects, lifecycle/deletion/budgets,
backup/restore/bootstrap and subscription-only auxiliary inference remain. Full
prompt/book-skill inventory/rewrite/held-out/human communication acceptance and
100 baseline failures remain. Visual scope:6/36 desktop+2/12 mobile,2 pilots,0/12
accepted pages; still produce30 desktop+10 mobile, implement10 other routes/shared
controls and verify all12. Final fresh independent whole-branch review before
integration. Model remains global host JSON/restart, with no per-agent/project/web
selector. No push, merge or deployment. Do not mark goal complete/blocked while
meaningful authorized work remains.


## Owner command inspection — base b243ce3

- The preceding goal turn made implementation progress (b243ce3). This turn adds
  the actual owner reader rather than another status-only continuation. Full scope
  remains the original modernization plan.
- OwnerRuntimeView now provides paginated job metadata and bounded stdout/stderr
  windows, scoped jointly by project/run/job. New GET routes require owner session,
  reject agent bearer access and return no-store. Reads work after Stop/lease loss,
  unknown result and with the runtime unconfigured; no control or replay is exposed.
- SQL reads only BLOB substr windows, not full output. Shared command_output encoding
  preserves model reader compatibility, base64 bytes and lossy UTF-8 flags. Focused
  investigation proved substr(X'',1,8) is NULL in installed SQLite; COALESCE restores
  legitimate empty windows. The large-output/unknown tests caught this actual failure.
- Ruling: public sequence cursors are decimal strings. A RED case with rowid
  9007199254740993 caught the original JSON-number design; IDs beyond JS safe integer
  precision now paginate exactly. Server accepts bounded SQLite integer cursor strings;
  frontend preserves them literally. This does not claim all legacy entity IDs in
  the web app have undergone a general64-bit identity migration.
- Fourteen owner HTTP cases cover binary/multibyte output, partial unknown receipts,
  no authority revival,27-job pagination, scope/session/bearer separation, limits and
  4MiB tail counterevidence. Initial negative scope/auth cases already passed through
  existing middleware; positive reader cases were RED before routes existed. Explicit
  path annotations now reject malformed IDs with422 instead of generic ValueError400.
- RunCommands/CommandReceipt integrate into current and historical task work. Reads
  are lazy; windows can go forward/back/to tail. Original args/base64 expand separately.
  Capture loss, partial read, exit code, closure and acceptance remain distinct. Raw
  HTML stays text; terminal/bidi controls are visible escapes. Changing scope resets
  selection/offsets/placeholders. Same-job transitions label old bytes while loading;
  closing the inspector stops its receipt polling. User selection can move focus;
  polling never moves focus/scroll. Errors offer GET again, not command execution.
- Final complete suite1241:1138 passed, identical100 baseline identities,3 skipped,
  29 warnings; all313 runtime tests pass. Frontend28 passed plus TypeScript/Vite build.
  Existing Browserslist/chunk-size warnings remain. All25 selected wheel sources
  (24 runtime modules and owner route) equal current source bytes. No new migration.
- Actual HTTP probe owner-command-inspection-352bc3ed uses a new copy of prior real
  native trial7792402f and an owned local server with runtime unconfigured. Fourteen
  requests of7-byte windows reconstruct all95 bytes. Recorded closure/exit0 survive;
  anonymous/bearer401 and cross-project404 are real HTTP responses. Fingerprints of
  nine tables in original/copy stay unchanged, no new inference/image call, source
  fixture/user DB unchanged. The first probe f5109066 also passed before cursor types
  changed; the final recheck verifies the changed wire contract, not a replay of work.
- Fresh CUA inventory: apps=[],browsers=[], browser host unavailable. CLI discovery
  found no Chromium/Chrome/Playwright on PATH or project dependency. No rendered,
  keyboard/mobile/accessibility/human acceptance. Official Playwright browser-install
  docs were consulted: https://playwright.dev/docs/browsers . Investigate an isolated
  container test browser as fallback; unavailable CUA is not a reason to stop backend
  work or call the complete modernization blocked.
- Bound12 source/test/eval files and13 final/relevant logs; separate suite/HTTP/wheel/
  QA reports preserve evidence limits. Source/log hashes verified before commit. All
  observed test/build/probe handles terminal; no server intentionally left running.
  Generated tsbuildinfo restored to its recorded version; instruction copies untouched.

## Next brief after owner command inspection

Keep the FULL modernization objective active. The read-only analysis facade, frozen
input/continuity, owner receipt API/UI, source/context/chat/tasks pilots and all8
concept assets exist; do not redo them. New job cursors are strings, not JS numbers.
Owner read is independent of agent authority and copied proof does not grant control.
Try an isolated Playwright/Chromium test tool using official installation docs to
unblock actual UI captures/interaction checks; CUA host is unavailable and no test
browser was detected, but no installation/launch was attempted this turn. Retain
zero accepted routes until actual visual/interaction/accessibility/human criteria
are met. Next backend priority is global workspace exclusion/ownership/capability
policy before mutable development tools, plus production Stop/correction/unknown
jobs and actual migration of retained consumers. All71 tools/11 categories and
legacy engine/roles/flows/autonomy/coordination still need completion; exact Git
candidate/base/head/context review/CI acceptance, typed edits and related-context
invalidation, long-history checkpoints, external effects, lifecycle/deletion/budgets,
backup/restore/bootstrap and subscription-only auxiliary inference remain. Full
prompt/book-skill inventory/rewrite/held-out/human communication acceptance and
100 baseline failures remain. Visual scope:6/36 desktop+2/12 mobile,2 pilots,0/12
accepted pages; still produce30 desktop+10 mobile, implement10 other routes/shared
controls and verify all12. Final fresh independent whole-branch review before
integration. Model remains global host JSON/restart, with no per-agent/project/web
selector. No push, merge or deployment. Do not mark goal complete/blocked while
meaningful authorized work remains.


## Ken admitted identity and CLI cache — base ae749ae

- Previous goal turn was implementation progress (ae749ae). Fresh independent
  architectural review read current ownership/workspace/gate sources with clean
  context. Saved workspace-authority-design.md: global publication before G,
  recovery independent of a lost source DB, durable generation/bootstrap/restore
  and actors outside namespaces remain obligations, not implemented guarantees.
  A single global mutable concession is a proposed throughput tradeoff, not a
  silently substituted concurrency requirement. No editable capability enabled.
- Immediate source-boundary work follows a demonstrated gap: Ken main accepted
  --model-cache but dropped it when calling worker_process. Direct helper tests
  and file reads missed this; new actual CLI test observed missing mounted bytes.
  main now forwards the cache, preserving pinned public asset hashes/no-token mount.
- Four new worker/CLI and two factory cases were RED, then GREEN. Native factory
  uses durable source identity when available; diagnostics without binding pin the
  current source at entry. Worker fstat must match before mkdir/open .ken. Rename
  after opening keeps the admitted FD view; replacement beforehand is rejected
  without state in the substitute. This is not global ownership/content freezing
  or a pinned view for all command/development actors.
- Full suite1247:1144 passed, identical100 baseline failure identities,3 skipped,
  29 warnings. All319 runtime cases pass. Frontend unchanged; previous28/build
  verification remains in owner-command evidence. All24 runtime wheel sources
  match current bytes. Five source/test/eval files and nine logs bound by hashes.
- Real CLI/native probe ken-identity-cc7e897d passes prepare, actual semantic
  ken_find and ken_read with isError=false via Codex0.166.0/published Ken0.18.0.
  Fifteen project tools, two registered peers closed, grant revoked, sources
  unchanged, no inference dispatch/model turn/image call. Fixture tests were read,
  not run. The diagnostic run retires failed deliberately; it is not a proposal.
- First probe d80bc1d2 lacked its own Git root and inherited an unrelated ancestor
  MCP from the managed worktree. Production preflight refused before thread/turn.
  Retained the guard, isolated the fixture Git repo and reran the no-generation
  diagnostic. Original failure evidence kept; its closed attempt was explicitly
  reconciled through RunRecovery, no replay. Direct metadata probes also confirmed
  config-table replacement must not be assumed to disable inherited servers.
- Product Design audit skill requires asking before Playwright CLI if unchosen.
  An async question was initially asked, then inspection of the actual authorized
  plan found section3 line81 explicitly requires Playwright and axe. User's full
  implementation authorization already covers this. Corrected the extra question
  in commentary; no answer is needed to proceed. No browser/package was installed
  at this checkpoint. npm metadata verified @playwright/test1.64.1 requires Node>=20;
  existing pinned Node24 is compatible. CUA host unavailable is an observation,
  not a permanent blocker on testing through the authorized test framework.
- All observed metadata/test/build/probe handles are terminal. No new inference,
  browser or server intentionally left. Original user checkout/instruction copies
  untouched. No push, merge or deployment.

## Next brief after Ken CLI identity

Continue FULL modernization. Proceed with Playwright+axe/browser installation under
plan section3 (already authorized; do not ask again merely because CUA is down).
Use actual current screenshots/interactions and compare with selected Tasks/Chat
concepts before asserting visual acceptance. No test browser installed yet; CUA is
unavailable. Eight visual assets/2 pilots exist,0/12 routes accepted. Still need
30 desktop+10 mobile concepts,10 other routes/shared controls and all12 acceptance.
Do not redo frozen input/continuity, owner output windows or Ken CLI fixes. New
CLI always forwards cache and checks admitted FD identity; it does not pin all
native filesystem views. Implement global workspace authority/bootstrap/generations,
duplicated namespace publication before G and physical closure/restore handoff
before mutable tools; read clean-context review in workspace-authority-design.md.
All71 tools/11 categories, legacy engine/roles/flows/autonomy/coordination, exact Git
candidate review/CI acceptance, typed edits/context dependencies/checkpoints,
external effects, lifecycle/budgets, historical backup/restore/bootstrap, subscription-
only auxiliary calls, complete prompt/book-skill/held-out/human communication work,
100 baseline failures and final independent whole-branch review remain. Model is
host-global JSON/restart, no per-agent/project/web selector. Full goal stays active.


## Ken admitted identity and CLI cache — base ae749ae

- Previous goal turn was implementation progress (ae749ae). Fresh independent
  architectural review read current ownership/workspace/gate sources with clean
  context. Saved workspace-authority-design.md: global publication before G,
  recovery independent of a lost source DB, durable generation/bootstrap/restore
  and actors outside namespaces remain obligations, not implemented guarantees.
  A single global mutable concession is a proposed throughput tradeoff, not a
  silently substituted concurrency requirement. No editable capability enabled.
- Immediate source-boundary work follows a demonstrated gap: Ken main accepted
  --model-cache but dropped it when calling worker_process. Direct helper tests
  and file reads missed this; new actual CLI test observed missing mounted bytes.
  main now forwards the cache, preserving pinned public asset hashes/no-token mount.
- Four new worker/CLI and two factory cases were RED, then GREEN. Native factory
  uses durable source identity when available; diagnostics without binding pin the
  current source at entry. Worker fstat must match before mkdir/open .ken. Rename
  after opening keeps the admitted FD view; replacement beforehand is rejected
  without state in the substitute. This is not global ownership/content freezing
  or a pinned view for all command/development actors.
- Full suite1247:1144 passed, identical100 baseline failure identities,3 skipped,
  29 warnings. All319 runtime cases pass. Frontend unchanged; previous28/build
  verification remains in owner-command evidence. All24 runtime wheel sources
  match current bytes. Five source/test/eval files and nine logs bound by hashes.
- Real CLI/native probe ken-identity-cc7e897d passes prepare, actual semantic
  ken_find and ken_read with isError=false via Codex0.166.0/published Ken0.18.0.
  Fifteen project tools, two registered peers closed, grant revoked, sources
  unchanged, no inference dispatch/model turn/image call. Fixture tests were read,
  not run. The diagnostic run retires failed deliberately; it is not a proposal.
- First probe d80bc1d2 lacked its own Git root and inherited an unrelated ancestor
  MCP from the managed worktree. Production preflight refused before thread/turn.
  Retained the guard, isolated the fixture Git repo and reran the no-generation
  diagnostic. Original failure evidence kept; its closed attempt was explicitly
  reconciled through RunRecovery, no replay. Direct metadata probes also confirmed
  config-table replacement must not be assumed to disable inherited servers.
- Product Design audit skill requires asking before Playwright CLI if unchosen.
  An async question was initially asked, then inspection of the actual authorized
  plan found section3 line81 explicitly requires Playwright and axe. User's full
  implementation authorization already covers this. Corrected the extra question
  in commentary; no answer is needed to proceed. No browser/package was installed
  at this checkpoint. npm metadata verified @playwright/test1.64.1 requires Node>=20;
  existing pinned Node24 is compatible. CUA host unavailable is an observation,
  not a permanent blocker on testing through the authorized test framework.
- All observed metadata/test/build/probe handles are terminal. No new inference,
  browser or server intentionally left. Original user checkout/instruction copies
  untouched. No push, merge or deployment.

## Next brief after Ken CLI identity

Continue FULL modernization. Proceed with Playwright+axe/browser installation under
plan section3 (already authorized; do not ask again merely because CUA is down).
Use actual current screenshots/interactions and compare with selected Tasks/Chat
concepts before asserting visual acceptance. No test browser installed yet; CUA is
unavailable. Eight visual assets/2 pilots exist,0/12 routes accepted. Still need
30 desktop+10 mobile concepts,10 other routes/shared controls and all12 acceptance.
Do not redo frozen input/continuity, owner output windows or Ken CLI fixes. New
CLI always forwards cache and checks admitted FD identity; it does not pin all
native filesystem views. Implement global workspace authority/bootstrap/generations,
duplicated namespace publication before G and physical closure/restore handoff
before mutable tools; read clean-context review in workspace-authority-design.md.
All71 tools/11 categories, legacy engine/roles/flows/autonomy/coordination, exact Git
candidate review/CI acceptance, typed edits/context dependencies/checkpoints,
external effects, lifecycle/budgets, historical backup/restore/bootstrap, subscription-
only auxiliary calls, complete prompt/book-skill/held-out/human communication work,
100 baseline failures and final independent whole-branch review remain. Model is
host-global JSON/restart, no per-agent/project/web selector. Full goal stays active.


## Owner browser capture and real UI fixes — base 7ae7d98

- Revalidated HEAD, dirty files and terminal captures after a status-only response;
  resumed implementation rather than repeating status. Playwright/axe are already
  authorized by the plan. The CUA host limitation no longer blocks local browser QA.
- Installed exact dev-only Playwright1.64.1 and axe4.14.0; Chromium156 launched with
  chromiumSandbox=true. Host uses the Ubuntu24.04 fallback build, explicitly noted.
  npm audit before/after has the same18 advisories (5 low/3 moderate/10 high), no new
  vulnerable packages. Dependency remediation remains required, no force audit fix.
- Real browser initially displayed a blank root: same-origin script/style requests
  on a dynamic local port received403. Five API cases were RED then GREEN; allow
  only the exact validated loopback endpoint plus explicit configured dev origins.
  Session/CSRF, other-port, cross-site and untrusted Host checks remain enforced.
  Local access30 pass; full backend1252:1149 pass,100 identical baseline failures,
  3 skip,29 warnings. Runtime319 pass. Failure identities compared, not just counts.
- Real axe contrast RED (2.89:1 on start) then GREEN; darkened start/stop controls.
  KaTeX CSS/fonts moved from CDN to the existing local dependency, lang=es/title
  Researcher. No new concept image or model generation in this checkpoint.
- Mobile RED showed a64px header clipping its second row. Increased selector
  specificity, anchored project options below the entire header; bounds and axe
  target-size checks now pass. Keyboard RED showed skip after navigation; moved
  link first. Navigation RED showed main focus missing and mobile heading outside
  viewport; route changes now reset content scroll/focus without stealing initial
  focus or query-only task-selection behavior. Actual final browser checks pass.
- Driver waits for actual task/workspace/receipt/history completion, rejects blank
  roots, records ARIA/PNG/header geometry/axe and failure diagnostics, refuses external
  dependencies and product mutations. One transient capture, one missing heading
  assumption and one overly broad header selector were diagnosed and corrected;
  transient/failed captures are not final acceptance evidence.
- Final synthetic copies owner-ui-a91436fe (8desktop) and owner-ui-07d210fa (9mobile)
  pass. Saved screenshots inspected directly or byte-identical to files inspected
  in the same audit, compared with selected Tasks/Chat references and exported to
  docs/design/audits/2026-11-01-owner-workspace. Read all95 output bytes in the UI.
  Zero model turns, external origins, JS errors, failed assets or browser product
  mutations. Real HTTP pairing before browser; login UI untested. Nine runtime
  tables unchanged in source/copies; no claim all110 tables compared in this audit.
- Connected Ken memory rejected the new local-access dependency as unavailable
  in its original-checkout index. This report/ledger preserves branch evidence;
  no memory saved against an unrelated old source as a substitute.
- Latest frontend28 pass and TypeScript/Vite build; existing chunk/Browserslist
  warnings. Restored generated tsbuildinfo to HEAD bytes. Ruff check/format and
  git diff checks required before commit. Wheel contains25 checked API/runtime
  files with matching bytes; it does not bundle frontend assets, so clean full
  product installation remains unfinished. No browser/server intentionally left.
- QA/status/inventory now distinguish actual browser progress from route acceptance:
  0/12 formally accepted,6/36 desktop concepts,2/12 mobile adaptations,2 pilots.
  Remaining interactive/login/error/recovery/zoom/screen-reader/human checks remain.
  Header still exposes legacy project start/stop; no click or hidden migration claim.
- Ruling: retain the current real prior-trial fixture as bounded reproducible audit
  evidence — it exercises the actual persisted native command receipt; clean-install
  deterministic E2E fixture/bootstrap remains required, not silently declared done.

## Next brief after browser checkpoint

Continue the FULL authorized plan. Browser access now works through Playwright;
never repeat a CUA-only blocker or ask again for already authorized browser tests.
Do not redo Ken CLI/input/command features or these demonstrated UI fixes. The
owner command inspector and saved conversation have actual desktop/mobile evidence;
finish all state/keyboard/zoom/screen-reader/human acceptance, not just these17 states.
Next critical backend work: global workspace authority/bootstrap/generation,
publication before G, pinned views and physical closure acrossDBs/deployments before
mutable development; use workspace-authority-design.md and migrate legacy host
writers/control paths. Keep all71 tools/11 categories, full engine/loop/roles/flows/
autonomy/agent communication, exact candidate Git/review/CI acceptance, typed context
edits/dependencies/checkpoints, lifecycle/budgets/external effects and restore in scope.
Remaining10 routes/30 desktop+10 mobile concepts, all prompts/book-skills/evals,
subscription-only auxiliary inference, dependency upgrades/18 npm advisories,
100 backend baseline failures, clean install/CLI/TUI/package frontend and final fresh
independent whole-branch review remain. No push/merge/deploy. Full goal stays active.


## Pinned peer source and ownership bootstrap debate — base 7bbbd41

- Previous goal turn was progress:7bbbd41 implemented browser fixes/evidence.
  Revalidated its clean tracked state; only instruction copies untracked. This turn
  continues full engine/workspace modernization, not another status-only turn.
- Reused untracked Ken global-workspace-authority-before-gate finding and re-read
  current workspaces/peers/service sources. Connected Ken cannot index these new
  worktree modules (find error/file not indexed); direct known-source reads supply
  evidence rather than claiming source coverage from those tool failures.
- Applied DDIA source-of-truth/durability/unknown-outcome rules and Ousterhout's
  information-hiding rule:PeerRegistry owns original admission lookup, guard owns
  Linux mounting/lifetime, native factories own effective profiles and RPC mapping.
  Coordinator/business APIs do not receive FD orchestration or another LLM loop.
- Continued architectural debate with existing clean-context ownership reviewer,
  without per-task implementer/reviewer agents. Saved workspace-authority-bootstrap:
  no auto genesis from absent paths; managed complete actor domain + closed spawn
  gate for origin proof; witnessed PREPARE/SQL/COMMIT before effects; real state
  hashes; missing/rewound state fails closed; jointly restored witness/SQL requires
  reference outside that restore domain. Broker/cgroup/service account are proposals,
  not installed/proven ownership. Host cgroup2/user subtree permissions observed
  read-only; no cgroup writes/services/account changes. Global authority still pending.
- Six real namespace tests initially RED:before-open replacement, rename between
  open/mount, rename after G, in native and command peers. First bind-FD at original
  host path passed4/6 but mountpoint followed its host dentry post-rename. Rebuilt
  private ancestor tree passed6/6 and real CLI but full suite exposed bwrap9000 args
  with thousands of /tmp/pytest siblings (106 failures, six new). Kept that evidence;
  discarded enumeration, not tests. Overlay root probe returned EINVAL and reviewer
  identified underlying-live-tree undefined behavior; no overlay adopted.
- Ruling:use private /run/researcher-source per registered peer instead of source
  host path — stable mount destination with preserved /run siblings; bounded by
  system runtime entries rather than project/temp directory cardinality. Cost:
  absolute host argv paths aren't rewritten/granted; historical cwd must reconcile.
  Relative cwd/file names remain the intended tool contract. Host journal identity
  remains original binding; source root/parent rename doesn't redirect the peer.
- Factory wire and real CLI config assertions observed physical/logical mismatch
  RED before native+command profile/thread/Ken/cwd mapping. Native factory's new
  test initially omitted required cwd in its synthetic helper config/read; corrected
  that harness error, not production protocol. The seven-case probe without a view
  assertion could pass while still using the host path; added explicit real profile
  assertion, observed RED, then GREEN. No inference/model dispatch for these probes.
- Two closure races appeared with fast peers. A trusted local diagnostic wrapper
  captured ProcessLookupError reading /proc/PID/stat after pidfd open, while stdout
  already contained done. Added FileNotFound/ProcessLookup tests, both RED then
  GREEN:wait bounded pinned pidfd barrier, never signal/claim closed by missing
  metadata. Permission/observer failure stays unknown. Product errors remain redacted.
- Added two RED→GREEN cases preserving host trusted-asset overlap checks after
  logical mapping:Ken command/cache cannot hide inside physical source. Resolve
  once and use canonical values in worker args; not a new source permission grant.
- Final targeted68 pass. Full suite1265:1162 pass, identical100 baseline failure
  identities,3 skip,29 warnings; all332 runtime cases pass. No new/resolved failures.
  Source/parent rename cases, factory profile checks and actual CLI all exercise
  admitted bindings. Real Ken cf3fabfe prepare/find/read passed isError=false, model
  turns0, source unchanged, original admission retained, peers closed and attempt
  retired. Analysis dfa7d70a:7 calculation/read/FS/symlink/network/env cases passed,
  verified logical roots, no inherited credentials/account, source unchanged, peers
  closed, diagnostic attempt explicitly retired failed because no native proposal.
- Five earlier closed synthetic diagnostics explicitly retired using original lease
  and peer proofs; zero inference dispatches/replayed jobs. Kept cleanup receipts.
  Wheel rebuilt after final code; all24 runtime source bytes match. Frontend untouched;
  previous28/build/17 browser-state evidence remains historical, not fresh acceptance.
- Admission still records dev/inode rather than a live reference from admission
  through opening; pre-open identity reuse/restore continuity is explicitly unproven
  and retained in authority/lifecycle acceptance, not claimed from rename tests.
- Full source/log/native/package hashes in peer-workspace-evidence/results/native/
  packaging/cleanup. No new generation/images, user DB migration, push/merge/deploy.
  Tracked status/coverage retain full goal. Workspace ledger is a symlink to this
  file; appended once to avoid the duplicate discovered in prior checkpoint.

## Next brief after pinned peer source

Continue the FULL plan. Source object pinning now works for registered native and
command actors with durable admission; do not redo it or mistake it for content
snapshot/global ownership. Next authority work:bootstrap/provisioning adapter with
complete managed actor domain, witnessed journal, global namespace publication
before G and physical closure independent of lost project DB; verified restore/
handoff/generations and legacy writer migration. Mutable development still gated.
Retain all71 tools/11 categories, legacy engine/loop/roles/flows/autonomy and agent
coordination, exact candidate Git/review/CI acceptance, context typed edits/dependencies/
checkpoints, lifecycle/budgets/external effects, backup/bootstrap/CLI/TUI/clean install
and frontend packaging. All prompts/book-skills/evals/human comprehension, subscription-
only auxiliary inference and dependency upgrades/18 npm advisories remain. Visual
inventory still6/36 desktop+2/12 mobile concepts,2 pilots,0/12 routes accepted;30 desktop
and10 mobile concepts/10 routes and full12 state/keyboard/zoom/screen-reader/human
acceptance remain.100 baseline backend failures and final fresh whole-branch review
are required, not waived. No permanent blocker while other meaningful work remains;
full goal stays active.


## Witnessed authority storage and independent closure — base 2afeb37

- Previous turn answered a status request (no implementation progress). Revalidated
  the actual worktree, untracked journal/tests and terminal logs; resumed the full
  goal instead of repeating status. Original checkout and instruction copies untouched.
- Implemented open-only WitnessedAuthorityJournal: existing private/inode-bound
  SQLite/witness/mutex, actual canonical-row hash, CAS/original-intent receipts,
  fsynced PREPARE/DELETE-EXTRA SQL/COMMIT and forward storage-only recovery. No
  auto genesis, launch authorization, effect replay or product broker integration.
- Malformed HEADER shapes had three recorded RED cases (AttributeError); explicit
  dict/identity validation now classifies them AuthorityUncertain and preserves
  bytes. Earlier eight sequence/type/zero-write RED cases remain in raw evidence.
  Lost COMMIT fsync receipt refuses verification until sync works; retry returns
  original fresh=False after later state. Both witness records reserved before write.
- Actual SIGKILL at six boundaries, actual SQL rollback, two competing processes,
  independent file loss/replacement/rewind and busy SQL/mutex are exercised. A
  real fork with another thread owning RLock exposed inherited-handle deadlock RED;
  reject before that lock and close only child FD copies GREEN, parent still works.
- Test host globally publishes real private namespace identity before local bind/G,
  deletes its synthetic project DB, then another process closes namespace from only
  the separate journal; includes setsid child and lost monitor. This is test-orchestrated
  protocol integration, not a managed complete host actor domain or productive global
  publication. The first test version could wait for inherited pipe EOF and let the
  child expire. Strengthened live-heartbeat/30s child fixture reproduced timeout RED;
  poll exact monitor returncode instead, prove child active immediately pre-closure,
  then prove late effect absent. Final44 storage/recovery cases pass in2.33s.
- First full suite1308:1205 pass,100 baseline failures,3 skip. After fork correction,
  next1309 suite exposed two intermittent old source-view peers (102 failures).
  Private diagnostic launcher reproduced EACCES at /proc/PID/ns/pid during fast exit;
  do not dismiss this as environment or rerun for a green count. New EACCES terminal
  test RED; extend pinned-pidfd terminal wait to PermissionError, without signaling
  unreadable identity. Separate live-init denial stays unknown and still answers
  input. Permission/boot/observer failures without terminal proof remain unknown.
- Final targeted69 pass;25 diagnostic iterations x6 actual peer cases =150 pass.
  Final bare suite with JUnit1311:1208 pass,100 identical baseline failure identities,
  3 skip,29 warnings;378 runtime pass. New/resolved failure identity sets both empty.
  All intermediate failures/logs retained and hashed, including the102-failure run.
- All8 changed/new Python sources pass Ruff check/format. Offline wheel rebuilt;
  all25 runtime sources match. A separate -I -S process outside the repository imports
  storage from the wheel, commits/reopens/retries synthetic state with fresh=False.
  This does not bundle frontend or establish clean full-product installation.
- Local microbenchmark0/1000/10000 initial records and30 commits:~214ms median commit
  at10000, with full actual-state/history verification. Historical measurement before
  fork hardening, no production latency acceptance. Checkpoint/rotation/retention
  remain required rather than silently pruning authority history.
- Connected Ken recall has no finding for these new worktree files; blast_radius
  says file not indexed. Earlier focused search hit legacy classes, not this core.
  Read known runtime/registry/guard/test sources directly; no memory fabricated on
  unrelated indexed files. DDIA durability/unknown-success and module ownership rules
  guide separation of storage receipt from semantic grant/physical actor closure.
- Ruling: commit the verified storage core without enabling mutable tools — it is a
  required part of authority, not proof of genesis, a complete actor domain, broker,
  source lifetime, global exclusion or verified restore/handoff. Losing this distinction
  could authorize an actor from a storage-only receipt; production integration remains gated.
- Current contract/status/coverage distinguish implemented storage from future
  bootstrap/authority. Source/log/results/package hashes in authority-journal evidence.
  No model turns/images, user DB migrations, host accounts/services, push/merge/deploy.

## Next brief after witnessed storage

Continue the FULL plan. Do not redo journal crash/rewind, source pinning or browser
fixes. Implement the semantic authority and managed-domain/provisioning adapter:
complete spawn gate/domain, durable genesis/generation, global publication before
local bind/G, revocation and recovery/release independent of project DB. Integrate
PeerRegistry/host actors; migrate retained legacy writers before mutable development.
Test two DBs/aliases, spawn-revoke and missing-state races, restore/handoff and budgets;
local SQL+witness rollback together still requires an external monotonic reference.
Storage receipts do not permit launches or effects. Retain all71 tools/11 categories,
full engine/loop/autonomy/roles/flows/agent communication, exact Git candidate/review/CI,
typed context/dependencies/history checkpoints, external effects/lifecycle, historical
backup/restore/bootstrap/CLI/TUI/clean install/frontend packaging. Complete all prompts,
book-skills/evals/human comprehension, subscription-only auxiliary inference, dependency
upgrades/18 npm advisories and100 baseline failures. Visual inventory remains6/36 desktop,
2/12 mobile,2 pilots and0/12 accepted routes; remaining30+10 concepts/10 routes and all12
state/accessibility/human acceptance required. Final fresh independent whole-branch review
still required. Full goal active; no push/merge/deploy and no permanent blocker inferred.


## Contained kernel birth and pre-publication recovery — base 45d560d

- Previous goal turn was progress:45d560d implemented witnessed storage. Revalidated
  clean tracked state, plan/contracts and active next brief. Full goal remains active.
- Continued the user-authorized architectural debate with the existing ownership
  reviewer (not an implementation/review agent per task). Decision: more spawn states
  cannot recover an unknown child; require concrete domain, atomic contained birth
  and broker ownership of G. Reviewer supports clone3 with explicit FD handling and
  identifies cgroupfs/D-Bus escape as a remaining decisive deployment boundary.
- Read-only host evidence corrected a stale generalized availability assumption:
  cgroup2 is rw, UID1000 user service/current scope are writable; current scope
  Delegate=no is NOT a complete actor-domain or no-migration proof. Linux6.18.55,
  glibc2.44, GCC16.2.1, systemd262 observed. No accounts/services/parent processes changed.
- Added Linux native _domain_spawn extension and ExecutionDomain kernel primitive.
  clone3(CLONE_INTO_CGROUP|CLONE_PIDFD), SIGCHLD, explicit copied argv/env and FD
  mapping; all sources duplicated above destinations, CLOEXEC remainder, exec-error
  pipe, signal dispositions/mask normalized. Child executes only native safe ops;
  parent exec acknowledgment releases GIL. No fork/migrate or unsupported fallback.
- Open-only cgroup2 identity pins device/inode+boot+PID/cgroup observers. A regular
  directory cannot impersonate it. Two RED self/ancestor cases now reject controller
  domains before control writes. These are kernel objects, not durable genesis.
- Actual direct birth and a setsid descendant close from another handle; stale
  removed cgroup FD cannot create a late actor. Real subprocess crash test first
  commits domain intent, then kills broker before publishing any PID; original
  synthetic project DB is deleted. Detached writer heartbeat remains live after
  broker death. Separate process reads global journal, retires/removes domain and
  persists tombstone; no late effect/source DB recreation. Constructor fixture
  has no product G/bind: it proves unknown-identity domain recovery, not final broker.
- Tests initially RED for missing implementation. Two harness issues corrected:
  raw native spec must explicitly map all std FDs, and Python itself opens a THP
  FD after exec (not inherited leakage). Test now verifies fake-secret exclusion,
  actual environment/signals, remap cycles and parent descriptor preservation.
  Partial pipe allocation leaked owned FDs RED; allocation now occurs under cleanup.
- Frozen-before-exec real cgroup test RED exposed retirement blocked on spawn lock.
  Retirement now withdraws admission and repeatedly kills before waiting for/draining
  constructors; canceled birth returns no transport. Then populated0+rmdir. NaN,
  infinity, negative and bool deadline cases RED; reject before kernel writes GREEN.
  No domain release by timeout or a momentarily empty observation.
- Final16 domain cases pass in1.41s. Bare full suite1327:1224 pass,100 identical
  baseline failure identities,3 skip,29 warnings;394 runtime pass, no new/resolved
  failures. Prior11-case full run also retained; no regression count hidden.
- Ruff check/format, clang-format and GCC -Wall/-Wextra/-Werror pass. Locked offline
  uv sync/check passes. Build now needs Linux compiler/Python+Linux headers and
  setuptools ext-modules support; wheel is cp312/Linux x86_64 rather than universal.
  README documents changed source-install requirements and conditional real CG tests.
- Built wheel+sdist, checked26 runtime Python source bytes and C source in archive.
  Separate -I -S process imports native module from extracted wheel, creates child
  in an exact private test domain, reaps and retires/removes it. Source archive builds
  another native wheel offline. This is not clean full-product/frontend packaging,
  other ABI/architecture acceptance or production deployment.
- Ruling: implement/test this kernel primitive before semantic grant states — a
  grant protocol without recoverable pre-publication actors could release while an
  unknown child still runs. Cost: native build/platform requirement; hide it in the
  domain module and validate packaging, rather than give callers a spawn/move recipe.
- Ruling: no mutable capability enabled from cgroup membership/empty alone — no-migration
  profile and complete origin/enrollment, broker gate/authentication and all legacy
  writer migration remain obligations. Escaped actors invalidate domain-only closure.
- Connected Ken recalled the global-before-gate finding; pyproject blast-radius
  reports only a lower bound (6/919 unresolved internal imports). Read actual launch,
  registry, service, build/startup and tests; do not claim graph completeness or save
  memory on unrelated legacy source anchors. Book design rules keep kernel mechanics
  separate from semantic grants and a future single run_peer entry point.
- Source/log/results/package hashes saved in execution-domain evidence. Only unique
  temporary child cgroups created/killed/removed; no parent cgroup migration, secrets,
  model turns/images, user DB migrations, system services/accounts, push/merge/deploy.

## Next brief after native execution domain

Continue the FULL plan. Next integrate a trusted broker's semantic run_peer using
this primitive: non-reused durable domain intent/generation, contained constructors,
global namespace publication, concrete local PeerRegistry validation and sole broker
ownership of G. Close all cgroupfs/service-manager migration channels in the actual
payload profile and test adversarial escape before mutable capability. Revocation
must withdraw G immediately, drain constructors/controls, close known namespaces plus
unknown domain actors, retire the domain and persist release; lost receipts never
spawn or send G again. External root enrollment/complete actor-origin proof and
historical writer migration remain required, not inferred from empty test cgroups.
The primitive does not authenticate users or authorize tools. Retain two DB/alias,
restore/handoff/generation and budget acceptance. All71 tools/11 categories, whole
engine/loop/autonomy/roles/flows/agent communication, exact Git candidate/review/CI,
typed contexts/dependencies/checkpoints, external effects/lifecycle, historical
backup/bootstrap/CLI/TUI/clean install and frontend packaging remain. All prompts,
book-skills/evals/human comprehension and subscription-only auxiliary inference,
dependency upgrades/18 npm advisories and100 baseline failures still required.
Visual inventory unchanged6/36 desktop+2/12 mobile,2 pilots,0/12 accepted; remaining
30+10 concepts/10 routes and all12 state/accessibility/human acceptance remain.
Final fresh independent whole-branch review required; full goal active, no push/merge/deploy.


## Participating peer broker and concrete analysis gate — base 9b352c8

- Previous turn was progress:9b352c8 implemented contained kernel birth/retirement.
  Revalidated tracked clean state and next brief; retained complete plan. This turn
  implements the first actual host run_peer composition, not more enum-only states.
- PeerBroker owns witnessed reserve→contained birth→global namespace publication→
  concrete PeerRegistry bind→dispatch intent→G decision. Sources bind original
  physical DB/attempt/fence/context/workspace; global active concession and monotonic
  fence serialize participating brokers. One externally supplied domain per attempt;
  no origin/enrollment, genesis or root creation inferred from an empty path.
- Extracted PeerRegistry lease lookup shared by admission/bind, retaining actual
  origin/authority checks. Local receipt booleans are not accepted as bind proof.
  ExecutionDomain now supports explicit auxiliary FDs and required resource limits.
- Concrete readonly stdlib AnalysisCapsule: minimal mounted runtime, pinned RO source,
  private PID/cgroup/network namespaces, no host HOME/control/sysfs/session bus,
  sealed gate/BPF assets. This interpreter lacks os.memfd_create (four real cases RED);
  C helper now provides bounded sealed memfd, verified rewrite/resize rejection RED→GREEN.
  Native/compiled source remains host infrastructure, never an LLM tool/grant issuer.
- Real global/local/G order, same-key receipt-only retry and changed-intent conflict
  pass. Actual revocation during blocked local bind closes/removes domain before bind
  resumes. G shares only a short decision lock with withdrawal; no long SQL wait in
  that lock. Client only receives post-G data copies; broker retains original pidfd/
  reaping. Client-close test RED exposed closing owner pidfd; transport separation GREEN.
- Global SQL contention test RED exposed journal.load before physical Stop. Move
  physical closure first; busy durable write leaves live withdrawal + cached physical
  proof and no global release, then persistence retries without replay. Post-G seal
  test RED exposed false gate_sent=False. Dispatch intent now stores null; live write
  observation may later persist true, crash unknown stays null. Never resend G to learn.
- Live-owner recovery test RED: new recovery requires original owner pidfd/ticks to
  prove terminal/replaced; insufficient visibility stays unknown. Three actual broker
  SIGKILL phases now pass: before global PID publication, before local bind, after G
  before seal (payload printed before crash). Separate process recovers from global
  journal after deleting original source DB; false vs null retained, no new process/G.
- Raw syscall test RED proved initial socket-only filter allowed unshare(0) and clone3.
  Deny namespace/mount/control calls and alternate x32 ABI. Payload clone3 returns
  ENOSYS for libc ordinary clone fallback; legacy clone flags cannot create namespaces.
  Child subprocess inherits socket denial. This does not weaken host clone3 birth.
- Private128 PID/512MiB/swap0 required, no missing-controller fallback. Actual fork
  pressure hits private cap then all descendants close. Actual two independent DBs
  register identical physical source; second concession rejected while first remains
  usable. Source writes through normal path and inherited directory FDs are denied;
  controller symlink, /proc/1/root and D-Bus paths unavailable in the real capsule.
- Retired-attempt test RED found reactivation in fresh domain using still-valid local
  lease (source Stop projection not yet durable). Persist original DB/attempt/fence
  reference beyond retirement; new domain now rejects it before birth. Old receipts
  remain readable; explicit new source attempt required. This is a global fence,
  not a claim that source-local lifecycle projection is already integrated.
- Final targeted57 pass;15 broker +17 domain cases pass. First full1342:1239 pass,
  same100 failures/3 skip; retained raw evidence. Final after tombstone1343:1240 pass,
  identical100 baseline failure identities,3 skip,29 warnings;410 runtime pass. New/
  resolved failure sets empty. All changed Python passes Ruff check/format and C
  clang-format/GCC Werror; locked offline sync/check succeeds.
- Final wheel28 runtime Python source bytes match, C source included in SDist. Fresh
  -I -S process imports only extracted wheel runtime/native, uses prepared synthetic
  migrated source/global journal/private domain, computes137+63=200, retries without
  dispatch, retires and rejects old attempt in another fresh domain. Package verifier
  saved locally with hash. Source preparation imports legacy migration helpers and a
  guarded socket attempt was traced to urllib3 IPv6 localhost capability detection;
  not inference/provider traffic. Original socket diagnostic retained, not guessed.
- Ruling: keep this first concrete profile model-free/readonly until full enrollment,
  native/Ken/business/development profiles and all writers migrate — socket denial is
  correct for stdlib analysis but not a generic inference networking policy. Cost:
  existing RuntimeService launchers remain to be replaced; this is not product-wide
  authority merely because an actual broker path now works.
- Ruling: missing domain after removal-before-durable-retirement still fails uncertain
  without a managed parent/generation/no-rename proof — do not fabricate closure or
  initialize another authority. Same-owner in-memory closure can retry persistence;
  cross-process missing-domain restore/handoff acceptance remains explicit work.
- Ken recall/related could not index these new managed modules; peer_registry
  blast-radius reports file not indexed. Read direct known registry/guard/service/
  kernel/test consumers instead, preserving old-test protection; no unrelated memory
  anchors used. Release It stability and Clean Architecture ownership guide the host
  composition without a new scheduler, bus or LLM loop.
- Technical contract/status/coverage/evidence updated. Broker is trusted in-process,
  has no exposed HTTP/IPC/auth endpoint and is not yet installed/wired into product.
  Durable output capture, wall/CPU/lease fuses, local projection, catalog/asset runtime
  manifests, complete origin/generations/restore/external budget proofs remain pending.
  No new model turns/images, user DB migrations, account/service install, parent
  cgroup migration, push/merge/deploy. Only exact private test cgroups used/removed.

## Next brief after participating peer broker

Continue FULL modernization. Adopt broker via a real managed enrollment/composition
adapter: external origin/complete actor-domain proof, durable non-reused domain creation,
authenticated host control, sole G ownership and migration/rejection of every retained
launcher. Integrate RuntimeService/CommandJobs and async stdio transport, durable bounded
outputs, wall/CPU/lease controls and source-local attempt retirement. Add concrete
Codex subscription/Ken/business/development profiles (do not reuse socket-denied analysis
as generic inference), bind runtime/assets manifests/catalog versions and test real
published Ken+subscription through the integrated path before enabling mutable tools.
Solve removal-before-durable-retirement/parent-generation proof, cross-deployment alias,
restore/handoff and external uncertain budget acceptance. Missing state never means new
installation. Preserve all71 tools/11 categories, engine/loop/autonomy/roles/flows/agent
communication, exact Git candidate/review/CI, typed contexts/dependencies/checkpoints,
external effects/lifecycle, historical backup/bootstrap/CLI/TUI/clean install/frontend
packaging. All prompts/book-skills/evals/human comprehension and subscription-only
auxiliary inference, dependency upgrades/18 npm advisories and100 baseline failures
remain required. Visual inventory unchanged6/36 desktop+2/12 mobile,2 pilots,0/12 accepted;
remaining30+10 concepts/10 routes and all12 state/accessibility/human acceptance remain.
Final fresh independent whole-branch review still required. Full goal active, no
push/merge/deploy, no permanent blocker inferred while meaningful work remains.

## Async broker transport and per-peer closure — base a1e9289

- Previous goal turn was a status report, not implementation progress. Revalidated
  worktree/HEAD and the live failing transport log; resumed the existing uncommitted
  adapter instead of recreating prior milestones. Full modernization remains active.
- Brief: separate JSON-RPC protocol from process ownership, connect actual broker
  pipe endpoints asynchronously, preserve sibling peers on ordinary close and keep
  whole-attempt Stop independent of occupied launch/peer-close workers. Do not enable
  product launchers by pretending that a config flag proves managed enrollment.
- `PeerBroker.close_peer` closes the original namespace before publication/SQL,
  reaps its owned child and persists execution closure without releasing siblings.
  Real two-peer and busy-SQL tests observed RED→GREEN. Whole-domain retirement and
  recovery now explicitly record execution closure; that never accepts a task.
- `JsonRpcClient` owns protocol/correlation/barriers/bounds only. Existing CLI
  `StdioRpcClient` delegates birth/signals/reaping to its compatibility endpoint;
  public command/cwd/env/process-group settings and existing consumers remain usable.
- `AsyncPeerBroker` has separate launch, peer-close and Stop executors, eight pending
  launch slots and128 endpoint history capacity. Real nonblocking event-loop pipes
  connect the broker's post-G data copies. No duplicate inference loop or RPC parser.
- RED blocked-write shutdown reproduced an event-loop callback on a released FD,
  including malformed synthetic SQLite from descriptor reuse. CPython3.12 pipe
  implementation confirmed graceful close leaves a registered pending writer.
  Abort/unregister before releasing data FDs fixes the actual failing integration.
- RED lifecycle tests proved close could race birth and return an already-closed
  connection, and startup cleanup failures disappeared. Shared shutdown rejects
  late startup success and chains the cleanup error to the primary failure.
- RED control test proved owner cleanup returned while its peer-close worker still
  ran. Stop now physically removes the domain first, then drains those raw futures;
  endpoint tasks are not awaited from owner shutdown, avoiding an ownership cycle.
- RED completion/cancellation test proved a future removed by its completion observer
  could strand undelivered data FDs. Cancellation attaches disposal to that exact
  birth future, including an already-completed result, without another dispatch.
- Final focused27 pass. Full bare suite1357:1254 pass, identical100 original baseline
  failure identities,3 skip,29 warnings;424 runtime pass. New/resolved failure sets
  empty. Changed Python Ruff check/format, git diff check and offline lock check pass.
- Offline wheel/sdist build passed. All29 runtime Python sources match the wheel;
  native C source matches SDist. Isolated -I -S extracted-wheel process exchanged
  actual broker JSON-RPC137+63=200, closed its peer while concession stayed active,
  retried receipt-only, retired the domain and rejected the old attempt in a fresh
  domain. Synthetic source preparation still uses legacy migration helpers and the
  previously diagnosed blocked urllib3 IPv6 localhost probe; no inference occurred.
- Ruling: startup cancellation before transport delivery withdraws the whole attempt
  — ownership/identity may still be uncertain; ordinary connected endpoint close is
  per-peer — cost: startup cancellation can interrupt siblings until a narrower safe
  admission/cancellation contract is implemented and proved.
- Ruling: leave source-local retirement projection for an open-existing-only source
  transaction integration — current SQLiteRunStore can create a missing DB before
  origin validation — cost: global closure is proved but local lifecycle projection
  is still pending and must not be mistaken for finished product adoption.
- Architecture/status/coverage/results/package evidence updated. No scenario or
  phase marked complete, no new images/model turns/user DB migrations/host service
  installation/shared-parent changes/push/merge/deploy. Core integration is concrete;
  production launchers and inference-capable profiles are still to migrate.
- Ken recall/blast-radius again report the new runtime file unindexed. Attempted
  to save the non-obvious pipe-FD finding with actual worktree evidence; Ken refused
  dependencies outside its original-checkout project. Kept the finding anchored in
  this architecture/evidence/ledger instead of saving a misleading original path.

## Next brief after async broker transport

Continue the FULL plan. Connect the actual broker transport into managed host
composition and RuntimeService/CommandJobs, with authenticated admission, external
origin/complete actor-domain proof and non-reused provisioned generations. Implement
Codex subscription/Ken/business/development profiles, bounded durable outputs,
wall/CPU/lease controls and open-existing-only source retirement. Preserve startup
cancel scope, per-peer close, sole G ownership and receipt-only retries; do not use
the socket-denied analysis capsule as an inference profile. Validate published Ken
and subscription through the final integrated launch path before mutable tooling.
Removal-before-durable-retirement, alias/restore/handoff, budgets, all71 tools/11
categories, engine/autonomy/roles/flows and agent communication, exact Git candidate/
review/CI, complete prompts/book-skills/evals/human communication, data/backup/bootstrap/
CLI/TUI/clean install, dependency upgrades/18 npm advisories and100 baseline failures
remain. UI still6/36 desktop+2/12 mobile concepts,2 pilots,0/12 accepted pages;30+10
concepts/10 routes and all12 acceptance remain. Final independent whole-branch review
still required. Keep the complete objective active.

## Current brief: existing source DB and broker closure projection — base f3c5d5b

- Close the demonstrated source-recreation gap before product adoption: runtime
  transactions must open an existing DB and never create a replacement when state
  disappears. Keep explicit legacy/bootstrap creation available. Preserve shared
  SQLite pragmas and filenames containing URI punctuation.
- After actual global peer closure, project the receipt through concrete
  PeerRegistry.close outside the event loop. Physical/global closure must precede
  local SQL; a missing/locked source reports incomplete projection, never replay.
- Tests: absent DB before first access, DB removed after runtime admission, URI
  punctuation, sibling/local closure/capacity and original DB loss during shutdown.
- Ken recall/related have no indexed connection/runtime modules in the original
  checkout; direct source/callers/tests are read in this worktree. No assumption
  of whole-host enrollment or physical DB pinning is added by mode=rw.

### Existing-source stage: implementation and next projection contract

- The first three actual missing-source/URI-name tests failed as intended, then
  passed with the opt-in shared connector and runtime existing-only transactions.
  Expanded direct consumer audit found the same defect in WorkspaceRegistry,
  OwnerRuntimeView and SQLiteResearchStore. Three more real missing-state tests
  failed before applying existing-only open to all their maintained callsites.
- Targeted existing-source/bootstrap/connection tests21 pass. Default creation
  remains available to explicit migrations/bootstrap and transitional legacy callers.
  mode=rw is not an identity pin, actor enrollment, restore proof or alias policy.
- Ruling: commit the demonstrated shared source-open contract before implementing
  closure projection — all retained new adapters must agree on absence semantics;
  cost: broker closure and source-local projection remain separate in this checkpoint.
- Projection still required: derive owned operations from the broker's global grant,
  not only endpoints that successfully returned. Validate original source physical
  identity, attempt/fence, peer and immutable namespace before recording local closure.
  A changed local binding must not cause a second signal against another namespace.
  Use concrete host ownership, never an external closed=True callback as evidence.
- Global physical retirement must precede local SQL. Busy/missing/replaced source
  must leave a visible incomplete local projection without recreating state, replay
  or release of a foreign grant. Drain known workers while reserving Stop capacity.
  Tests must cover connected-close capacity release, early bind/birth cancellation,
  source loss, local writer contention and mismatched namespace/source records.

- The first complete consumer suite1363 exposed101 failures:100 baseline plus
  test_live_grants::test_cached_scope_waiting_for_sqlite_cannot_write_after_live_withdrawal.
  Its real-SQL instrumentation wrapper accepted only the old positional signature;
  existing_only caused TypeError before BEGIN IMMEDIATE, so the trace event never
  fired. Forwarding keyword options preserves the actual connection policy and
  the original no-write-after-withdrawal assertion. Final focused23 pass.
- Retained the failed full log/XML as intermediate evidence; final suite and
  package revalidation run after the probe fix, not inferred from the focused pass.

- Final whole-suite1363:1260 pass,100 exact original baseline failure identities,
  3 skip,29 warnings;430 runtime pass. Focused23 pass. No new/resolved failures.
  All7 changed Python files pass Ruff check/format; git diff check passes.
- Final offline wheel/SDist source bytes checked:29 runtime modules, shared DB,
  research store and updated test probe. Isolated packaged broker JSON-RPC computes
  200, preserves concession on peer close, retires/rejects stale attempt and opens
  missing source without creating a replacement. Source DB/bootstrap remain synthetic.
- Status/coverage/evidence/package results updated; no phase/scenario closed. The
  next implementation is the ownership-validated source closure projection above,
  followed by real managed enrollment, product launchers and all full-plan items
  already listed in the next brief. No user data/model/image/host service/deploy work.

## Current task: broker closure projection — base a45d047

- Previous goal turn was progress: f3c5d5b async transport and a45d047 existing-source
  opens committed. Revalidated tracked clean HEAD and full objective/next brief.
- Implement source-local closure from the broker's verified durable operations,
  using the concrete source registry cached only after actual global reservation.
  Derive all owned operations for owner shutdown, including births whose endpoint
  was never returned. No generic caller-provided closure boolean or second signal.
- Match DB origin, peer, attempt/fence, project/task and original namespace within
  the existing-source transaction. Preserve source events/idempotency. Refuse a
  changed namespace or copied/replaced source; global physical closure stays true.
- Integrate connected-peer and whole-attempt async cleanup. Physical/global Stop
  precedes local SQL, which uses the peer worker and cannot occupy the Stop worker.
  Missing/locked source is a visible incomplete projection, never state genesis.
- Validate real two-peer/capacity release, cancellation before/after delivery, local
  SQL contention, source loss and changed binding. Whole-host enrollment, product
  launchers/inference profiles and the remaining full plan stay in scope/pending.

## Broker closure projection checkpoint — base a45d047

- Implemented PeerBroker.project_closed using the verified global grant and actual
  source registry. Checks original physical origin/peer/attempt/fence/project/task/
  protocol/namespace; source peer rows and peer.closed events commit together.
  Repeat projection is event-idempotent; no call to close_namespace/registry.close
  in projection, no new G or task acceptance.
- Connected-peer cleanup now closes globally then projects its source receipt on
  the peer worker. Owner cleanup physically retires globally before waiting for
  source SQL, drains constructors/workers and derives every reserved operation,
  including a cancelled bind whose endpoint never returned. Nine sequential real
  RPC jobs prove local capacity is released; a sibling remains usable on peer close.
- Real source writer contention leaves Stop able to remove its domain first.
  Missing source yields visible projection error with global retirement/release
  preserved and no new DB. Existing copied source and altered fence/namespace are
  rejected; one invalid row rolls back all local rows/events.
- Initial four projection cases observed RED→GREEN. Async integration assertions
  failed on local bound/prepared state before wiring, then passed. Erased-binding
  test initially violated the schema bound/non-null constraint; corrected to a
  valid prepared state as an old restore could leave. A controlled removal of
  the binding guard then produced DID NOT RAISE; restored guard passes. Retained
  the setup-failure logs rather than describing them as proof of the guard.
- Lost committed reservation acknowledgement test RED exposed dependence on live
  source cache. Added absolute source_database locator to new grant metadata via
  concrete PeerRegistry.admission. It only locates: projection rechecks original
  DB identity and rows. The lost-ack case now closes the original prepared peer
  without a birth/G. No new source is inferred from a missing filename.
- Separate-process projection test RED exposed missing recovery API. Added
  project_recovered only for verified retired grants with removed domain; actual
  -I subprocess projects from the journal/locator, no live broker cache. Active
  grant is rejected. Historical grant without locator stays uncertain in recovery;
  current owner can still use its retained original registry.
- Final focused61 pass. Whole bare suite1376:1273 pass,100 exact original baseline
  failure identities,3 skip,29 warnings;443 runtime pass. New/resolved failure sets
  empty. All5 changed Python files pass Ruff check/format; git diff check passes.
- Offline wheel/SDist build passed. All29 runtime Python bytes match extracted
  wheel; isolated -I -S process computes137+63=200 via broker JSON-RPC, verifies
  source peer closure, reprojects retired grant without cache, retries receipt-only,
  retires/rejects stale attempt and does not recreate missing source. Only synthetic
  migrated source and provisioned exact private cgroup/journal were used. The known
  blocked urllib3 IPv6 probe occurs in legacy migration-helper preparation, not inference.
- Ruling: project local closure directly after verified global proof, without
  signalling from source DB rows — a changed binding must not kill a sibling —
  cost: temporary host-infrastructure coupling to concrete PeerRegistry storage
  helpers remains until the larger product adapter boundary is migrated.
- Ruling: persist a source locator as additive optional grant metadata — lost-ack/
  recovery tests demonstrated that a live cache is insufficient — cost: historical
  grants without locator need the retained verified source or explicit reconciled
  enrollment; no guessed path or automatic alias/restore adoption.
- Ruling: keep global retirement separate from the atomic local projection — source
  loss/SQL cannot delay physical Stop — cost: local projection may need explicit
  reconciliation after repair; a closed peer is not a completed run/task.
- Ken recall/blast-radius again have no indexed worktree runtime files; direct
  known callers/tests were read. Prior Ken remember rejection for evidence outside
  its original-checkout root still applies; findings remain anchored in this
  architecture/evidence/ledger rather than an unrelated original path.
- Status/coverage/evidence/package reports updated; no phase/scenario marked done.
  No new model/image turns, user DB migration, account/service install, shared-parent
  cgroup changes, push/merge/deploy. Whole modernization objective remains active.

## Next brief after broker closure projection

Continue FULL plan. Do not redo the existing-source guard, async transport/closure,
source projection, journal/kernel/gate primitives, input/chat/tasks pilots or the8
concept assets. Adopt these actual components into managed host composition and
RuntimeService/CommandJobs with authenticated admission, external origin/complete
actor-domain proof and non-reused provisioned generations. Implement real Codex
subscription/Ken/business/development profiles and runtime/assets manifests; the
current socket-denied analysis capsule is not an inference profile. Bind durable
bounded outputs, wall/CPU/lease controls and run business-state reconciliation to
actual broker receipts. Published Ken and subscription must pass through that final
product path before mutable capabilities are enabled.
Removal-before-durable-retirement/parent-generation proof, alias/transfer/restore/
handoff, uncertain budgets, all71 tools/11 categories, engine/autonomy/roles/flows/
agent communication, exact Git candidate/review/CI, full prompts/book-skills/evals/
human comprehension, data/backup/bootstrap/CLI/TUI/clean install, dependency updates/
18 npm advisories and100 baseline failures remain. UI still6/36 desktop+2/12 mobile
concepts,2 pilots,0/12 accepted pages;30+10 concepts/10 routes and all12 acceptance
remain. Final fresh independent whole-branch review required; keep full goal active.

## Current task: contained Codex native transport — base bb745b5

- Previous goal turn was progress: actual source closure projection committed and
  verified. Revalidated tracked-clean branch; preserve FULL plan and all remaining
  capabilities/UI/prompts/legacy removal, not just this native launcher increment.
- Read current NativeRuntime/command launchers and actual Codex0.166.0 CLI metadata.
  Native inference still launches through registered old peer_guard. Analysis
  capsule cannot be reused as inference: it denies every socket and only mounts
  stdlib/source. New native launch must use a distinct concrete profile/asset.
- Implement pinned explicit Codex asset, separate minimal native capsule, actual
  PeerBroker native birth/publication/bind/G and shared AsyncPeerBroker/JsonRpcClient.
  Verify real App Server initialize/account/config metadata without any model turn
  or credential mounting, source writes, arbitrary host launcher or fake CLI command.
- Native profile keeps source readonly, private HOME/CODEX_HOME, host controls and
  credentials absent, bounded domain, namespace/control denial. Its networking is
  a distinct policy; it must not weaken analysis socket denial. Record actual
  binary/profile hashes in intent and preserve receipt-only retries/projection.
- Official App Server docs describe experimental chatgptAuthTokens via RPC and
  host-owned refresh. The pinned binary/protocol must verify support before auth
  migration. Do not switch providers or use a metered key. Full subscription/Ken/
  business/code-mode profile integration and managed complete actor enrollment are
  still required before this is accepted as production inference.

## Contained native transport checkpoint — base bb745b5

- Previous turn was progress; tracked-clean bb745b5 revalidated. Inspected actual
  product launcher/factory/command consumers and bootstrap design before editing.
  Ken recall/related still lack these worktree modules; existing source-evidence
  restriction prevents saving misleading memories against the original checkout.
- Added CodexAsset bounded executable identity/content measurement and recheck on
  an opened FD; source-owned/changed/untrusted-mode assets reject before G. No
  host execution is used to identify an asset. Native manifest records selected
  binary identity/hash and actual profile/gate source hashes in durable operation.
- Added distinct NativeCapsule and run_native through the existing global/local/G
  operation, not another launcher/LLM loop. Shared minimal mount/gate handling with
  analysis while keeping its socket-denying filter unchanged. Native gets private
  HOME/CODEX_HOME, RO source, pinned binary without its parent tree, fixed features/
  ChatGPT/OpenAI settings, explicit untrusted logical source and bounded threads.
- AsyncPeerBroker.native connects the same protocol client. Operations now record
  kind; closure projection accepts the exact registered native/command kind, with
  historical analysis fallback. Same-key native retry produces no transport/write.
- Initial missing-feature tests RED. Real Codex0.166.0 initially exited at startup;
  controlled fresh-home/no-auth stderr proved CODEX_HOME directory was absent.
  Creating that directory only inside the capsule made real initialize/account/
  config pass. Synthetic host auth.json/env key and invalid source configuration
  are not inherited; account remains null, no model turn is sent.
- Controlled ELF policy test, clearly separate from actual Codex, RED exposed
  addressed Unix sockets under the first native filter. Restrict socket to AF_INET/
  AF_INET6, deny bind/listen/accept and namespace/control calls. Probe now confirms
  Internet socket availability but Unix socket/bind/source write/cgroup visibility/
  unshare/key inheritance absent. Native socketpair remains private; no OpenAI-only
  destination/egress or real inference-network claim is made.
- Effective-config test RED exposed quoted project path preserved literally by
  dotted CLI override. Controlled config diagnostic showed the exact bad key;
  replacing it with a full inline TOML projects table preserves the required path.
- Manifest test RED exposed opaque intent without audit data; new operations now
  persist readable runtime_manifest with the native measurements before launch.
- Generated experimental JSON schema from the actual pinned binary in an empty
  host metadata home. It declares chatgptAuthTokens accessToken/account/plan and
  refresh request/response fields, matching official App Server docs. No real token,
  login or inference sent; current factory auth/provider was not silently changed.
- Final focused61 pass. Full bare suite1380:1277 pass,100 exact original baseline
  failure identities,3 skip,29 warnings;447 runtime pass,4 native cases. New/resolved
  failures empty. Changed Python Ruff check/format and git diff check pass.
- Offline wheel/SDist build passed; all29 runtime Python sources/native C match.
  Extracted-wheel -I -S process starts actual Codex0.166.0 and analysis siblings
  through one broker; analysis computes200, its close preserves native account/read,
  both local peers project closed, retirement/recovered projection/receipt retry/
  stale rejection/missing-source non-recreation pass. Synthetic source/bootstrap
  only; known blocked urllib3 localhost capability probe is preparation, not inference.
- Ruling: keep native transport separate from analysis and do not activate it as
  productive inference yet — real subscription/auth refresh, TLS/DNS/egress, mandatory
  Ken/business/code-mode and runtime/catalog/state manifests remain unproved — cost:
  existing product launchers stay to migrate; no configuration flag can close that gap.
- Ruling: native socket policy is Internet-client families, not blanket networking
  and not OpenAI-only egress — actual Unix-socket probe demonstrated a control
  channel to exclude — cost: future OAuth/browser/MCP/code-mode integrations must
  use compatible host-mediated channels instead of reopening host control sockets.
- Ruling: persist additive native kind/manifest while preserving analysis intent
  hash and historical kind fallback — old receipts must not be replayed after an
  upgrade — cost: native profile/asset changes conflict with prior intent and need
  explicit reconciliation/new admission. Full toolchain/assets catalog still pending.
- Status/architecture/coverage/evidence/package updated. No phase/scenario closed,
  no new model/image generation, user DB migration, host account/service install,
  shared-parent cgroup change, push/merge/deploy. Full goal remains active.

## Next brief after contained native transport

Continue FULL modernization. Existing real native metadata transport is done; do
not reimplement broker/domain/journal/gate/source projection or the8 concept assets.
Complete the actual product composition: isolated persistent native state with no
managed credential directory mount; host-mediated subscription RPC/auth refresh
verified against pinned schema; TLS/DNS and destination policy; actual mandatory
published Ken and business adapters through broker-owned peers, compatible code-mode
execution in its own profile, and runtime/toolchain/assets/catalog version binding.
Test bounded real subscription+Ken turns through that integrated path before
enabling mutable tooling. NativeCapsule currently disables code-mode/shell/plugins
and has no credentials; metadata success does not prove inference or entitlement.
Adopt actual RuntimeService/CodexRuntime/CommandJobs launchers with managed external
origin/enrollment/authentication/non-reused generation proof and all actor control.
Durable bounded outputs, wall/CPU/lease and run business-state reconciliation still
required. Missing state is not genesis; no flags masquerade as enrollment.
Keep all71 tools/11 categories, engine/autonomy/roles/flows/agent communication, exact
Git candidate/review/CI, prompt/book-skills/evals/human comprehension, historical
data/backup/restore/bootstrap/CLI/TUI/install, alias/transfer/handoff/budgets,
dependency upgrades/18 npm advisories and100 baseline failures in scope. UI remains
6/36 desktop+2/12 mobile concepts,2 pilots,0/12 accepted;30+10 concepts/10 routes and
all12 acceptance remain. Final fresh independent whole-branch review required.

## Current task: host subscription RPC authentication — base53f1384

- Previous turn was progress:53f1384 real native transport committed and verified.
  Tracked-clean branch and full next brief revalidated; whole objective unchanged.
- Official docs describe experimental externally managed ChatGPT RPC tokens and
  host refresh. Pinned generated schema includes the fields but retains an
  internal/unstable description; record compatibility discrepancy, verify actual
  pinned behavior with synthetic credentials/offline network before real use.
- Implement redacted access-token/account snapshot, secure bounded read-only managed
  auth-file adapter, connection-scoped external authentication and refresh handling,
  and CodexSession integration before account/thread admission. No refresh token or
  API key is forwarded; no credential HOME is mounted into native.
- Refresh requests have no guaranteed threadId and can precede a pending RPC receipt.
  Add explicitly registered bounded private connection request handlers so they
  cannot deadlock turn/login/thread admission or enter model/human event callbacks.
  Stop physically closes before draining/cancelling private work; failures redact
  sensitive details and never switch account/provider or replay a host turn.
- Test missing/unsafe/malformed files, account change, unchanged refreshed token,
  startup/turn refresh without receipt, private backpressure/cancellation/redaction,
  and actual native RPC with synthetic tokens in a private network namespace.
- Managed file adapter reads tokens; successful real OAuth rotation needs a host
  lifecycle provider. Do not pretend rereading the same stale token renews it.
  Full product auth lifecycle, persistent native state, TLS/DNS/egress, mandatory
  published Ken/business/code-mode and managed host enrollment remain in scope.

## Host subscription RPC authentication checkpoint — base53f1384

- Prior continuation: progress (implementation plus source/native/compatibility tests);
  intervening user status request was read-only evidence, not implementation progress.
- RED→GREEN sources/private RPC/session/write guard/cancel confirmed in saved logs.
  Full-suite extra regression in ReplyObservedClient.request_ordered was diagnosed:
  _guard=None must not be forwarded to legacy subclasses. Production default-call
  compatibility fixed; command output receipt ordering test now passes unchanged.
- Full suite1403:1300 pass,100 exact baseline failures,3 skip,29 warnings;470 runtime.
  Focused84 pass. Current build succeeded; wheel30 runtime byte matches and isolated
  actual account-free Codex+analysis sibling / deterministic-auth smoke passed.
  Raw logs/hashes and limitations recorded in subscription-evidence/results/package.
- Ruling: managed read-only snapshot is not OAuth renewal or entitlement — actual
  host lifecycle provider remains required — cost: expired tokens currently fail
  rather than silently using a different account/provider or pretending renewal.
- Ruling: private connection control is bounded and excluded from model/user queues;
  authority is checked at actual write, including after the writer lock — queued
  credentials must not leave after withdrawal — cost: failure retires the connection.
- Ruling: preserve unguarded RPC subclass call signatures — only guarded calls pass
  the internal argument — cost: guarded adapters must explicitly support that port.
- Ruling: retain actual SDK offline routing failure as a negative test, not a remote
  entitlement success — local login ACK and remote account acceptance differ — cost:
  real isolated subscription/inference integration is still unproven.
- No new actual model/image generation or real token use; no user DB migration, host
  service/account install, shared-parent cgroup changes, push/merge/deploy. No full
  phase/scenario closed. Whole modernization objective remains active.

## Next brief after host subscription RPC checkpoint

Continue FULL plan. Do not repeat completed broker/journal/domain/projection/auth
components or8 concept assets. Next integrate a host-owned credential lifecycle
with per-account renewal coordination, isolated persistent native state and actual
TLS/DNS/destination policy. Compose mandatory published Ken/business/code-mode and
move product factories to broker-owned peers only once enrollment/all-actor origin
contracts are real. Test bounded actual subscription+Ken through that integrated
path; no API key fallback. Snapshot reread is not renewal. All71 tools/11 categories,
engine/autonomy/roles/flows/agent communication, exact Git candidate/review/CI, prompts
/book-skills/evals/human comprehension, data/restore/bootstrap/CLI/TUI/install,
alias/transfer/budgets, dependencies/18 npm advisories and100 baseline failures stay
in scope. UI6/36 desktop+2/12 mobile,2 pilots,0/12 accepted:30+10 concepts/10 routes
and all12 acceptance remain. Final fresh independent whole-branch review required.

## Current task: managed host subscription coordinator — basef0e258f

- Add an owned managed-mode RPC coordinator using account/read refreshToken=true,
  delegating actual OAuth to the SDK. The host supplies the trusted unopened RPC
  endpoint and existing private managed source; no managed HOME/token is exposed
  to the isolated inference peer. No new ad-hoc OAuth HTTP client or API fallback.
- Serialize shared refreshes under one host owner; each native connection tracks
  its last snapshot so a new on-disk token is reused without another forced refresh.
  Cancellation of a consumer must not release the host rotation lock mid-flight.
- Bound pending resolutions and deadlines; retire/physically close on uncertain
  managed refresh, account change or unchanged token. Source and RPC exceptions
  remain redacted. No product factory/enrollment claim from an injected endpoint.
- Deterministic tests exercise real JSON-RPC and two native sessions, shared rotation,
  consumer cancellation, stale/switch/error, external rotation, missing source and
  timeout. Ordinary suite remains offline; real subscription proof remains separate.

## Managed host subscription coordinator checkpoint — basef0e258f

- RED8 missing provider cases confirmed. Initial integration7 pass1 failure was a
  test orchestration error: waiting for the native abort's2s reconciliation before
  releasing a1s host refresh. Release now follows observed physical client close,
  then awaits reconciliation; no product timeout was weakened.
- Queued-withdrawal RED1 failed8 pass exposed generic error poisoning the shared
  account. Dedicated consumer withdrawal now leaves the host owner available.
- Host-close RED proved callback cancellation silently dropped the native refresh
  response. Distinguish cancellation of the owned resolution from cancellation of
  its waiter; the former becomes prompt sanitized connection failure.
- Cancelled-close RED proved callback drain ran before delayed physical closure.
  Shield one host-owned shutdown and preserve physical-before-drain ordering.
- GREEN43 focused includes12 provider cases. Full1415:1312 pass,100 exact original
  baseline failure identities,3 skip,29 warnings;482 runtime pass. Offline build
  succeeded; wheel31 runtime bytes match, isolated -I -S two-client managed RPC
  coordination plus existing real account-free native/analysis broker smoke passed.
- Ruling: reuse the official managed account/read refreshToken=true RPC — SDK owns
  OAuth and storage — rather than invent HTTP refresh semantics — cost: requires
  a trusted enrolled managed endpoint and real OAuth acceptance before adoption.
- Ruling: coordinate per host owner and reuse a changed same-account snapshot —
  avoids duplicate refresh races between its sessions — cost: does not serialize
  external CLI/apps; cross-process account authority/coexistence remains required.
- Ruling: host owns a rotation after admission even if its consumer disappears;
  client credential delivery still requires active authority — cost: one bounded
  account-maintenance operation can finish after its initiating session stops.
- Ruling: uncertain refresh/unchanged token/account change retires this provider
  without replay; queued withdrawal/capacity rejection retires only its consumer —
  cost: real credential/provider failure needs explicit host reconciliation/reopen.
- No actual credential use/model/image generation, user DB migration, host install,
  parent cgroup change, push/merge/deploy. No full phase/scenario closed.

## Next brief after managed subscription coordinator

Continue FULL plan. HostSubscription coordinates managed RPC but does not launch
its trusted enrolled endpoint or prove real OAuth. Compose account ownership across
processes/coexistence with user CLI, persistent isolated native state, TLS/DNS and
destination policy, then mandatory published Ken/business/code-mode through owned
peers. Adopt RuntimeService/CodexRuntime/CommandJobs with actual deployment origin,
enrollment/non-reused generation/all actor proof; do not claim these from a flag
or injected RPC. Run bounded actual subscription+Ken through the integrated path
before mutable tooling. Do not repeat completed source/broker/journal/domain/auth.
All71 tools/11 categories, engine/autonomy/roles/flows/agent communication, exact
Git/review/CI, prompts/books/evals/human comprehension, data/restore/bootstrap/CLI/
TUI/install, aliases/transfer/budgets, dependency upgrades/18 npm advisories and100
baseline failures remain. Independent UI work can proceed:6/36 desktop+2/12 mobile
concepts,2 pilots,0/12 accepted;30+10 concepts/10 routes and all12 acceptance remain.
Final fresh independent whole-branch review required. Full objective stays active.

## Current task: pinned native DNS/TLS material — basea89c917

- Previous goal turn was progress: f0e258f/a89c917 implementation, tests, wheel and
  evidence committed. Full objective unchanged; source checkout untouched.
- Product runtime still exposes managed HOME to its trusted native process; do
  not pretend the credential-free broker transport already replaces that factory.
- Before real credentials in the new capsule, admit explicit public resolver/CA
  files outside the source, validate/bound/pin their identities and bytes, retain
  their manifests in the broker operation and mount sealed snapshots read-only.
  No host HOME/proxy/API-key environment inheritance. Keep analysis profile offline.
- Test changed/unsafe/malformed inputs, gate-before-change rejection, immutable
  mounts, local real TLS trust/hostname failures, actual account-free Codex and
  receipt-only retry. Ordinary tests use local endpoints; any real DNS/TLS probe
  is separate, credential-free and bounded. Destination restriction remains needed
  before introducing real credentials; public CA assets alone do not enforce it.

## Pinned native DNS/TLS checkpoint — basea89c917

- RED8 missing public inputs and RED4 missing network broker port confirmed. Initial
  validation rejected Unicode comments in real public CA bundle; line-wise UTF8
  comments/public PEM validation now accepts it and rejects non-certificate blobs.
- Actual SDK trusted local TLS reached HTTP then rejected {} for missing workspace;
  expected error now distinguishes that result from TLS/discovery failure. Unknown
  CA/wrong hostname reject before HTTP. No real credentials or external SDK routing.
- Trusted TLS case mutates both original inputs after sealing/before spawn; actual
  SDK still uses admitted copies. Source-controlled assets and changed inputs reject
  before G; changed-manifest same-key conflicts and original retry stays receipt-only.
- Separate bounded controlled diagnostic ELF/Python resolves learn.chatgpt.com and
  validates TLS1.3 hostname/cert, HEAD /docs/app-server returns200, domain retired.
  First attempts had diagnostic argv0/CPython-prefix and embedded newline errors;
  fixed full argv0/raw source/compile-before-C. Failed domains retired; no paid calls.
- GREEN45 focused,15 network cases,3 real SDK local TLS cases. Full1430:1327 pass,
  100 exact baseline failures,3 skip,29 warnings;497 runtime pass. Current offline
  wheel32 runtime bytes match and isolated account-free native public-network
  manifest + prior broker/analysis/managed-refresh/recovery smoke passed.
- Ruling: explicit inspected public inputs and sealed copies, no host /etc/HOME bind
  or inherited proxy/CA settings — changes cannot alter an already admitted mount —
  cost: host must choose valid assets again after their measured identity changes.
- Ruling: preserve omitted-network native manifests/analysis behavior, attach network
  and validator hashes only when explicitly admitted — no invented authority from
  a DNS/TLS flag — cost: these inputs are an optional transport capability until
  product composition supplies actual managed lifecycle and destination controls.
- Ruling: distinguish local SDK TLS, public diagnostic connectivity and actual OAuth/
  entitlement/inference — different observables — cost: none substitutes the pending
  integrated subscription+Ken/code-mode acceptance trial.
- No real credentials read/sent, new model/image generation, user DB migration, host
  install, parent cgroup changes, push/merge/deploy. No full phase/scenario closed.

## Next brief after pinned native DNS/TLS

Continue FULL modernization. Network inputs now make DNS/TLS usable in the new
profile; do not repeat this or completed broker/journal/domain/projection/auth.
Implement actual destination policy (including DNS/rebinding/loopback/redirects/
WebSocket/proxy interaction) before real credentials. Compose enrolled managed
credential endpoint and account ownership/coexistence across processes, persistent
isolated native state, mandatory published Ken/business/code-mode, then adopt
RuntimeService/CodexRuntime/CommandJobs with real origin/generation/all-actor proof.
Product factory currently still uses its old managed HOME launcher; new transport
metadata/TLS success is not migration. Test bounded actual subscription+Ken only
through the integrated path. All71 tools/11 categories, engine/autonomy/roles/flows/
agent communication, exact Git/review/CI, prompts/books/evals/human comprehension,
data/restore/bootstrap/CLI/TUI/install, aliases/transfer/budgets, dependency upgrades/
18 npm advisories and100 baseline failures remain. Independent frontend progress
can proceed:6/36 desktop+2/12 mobile concepts,2 pilots,0/12 accepted;30+10 concepts/
10 routes/all12 acceptance still required. Final fresh whole-branch review remains.

## Current task: bounded host CONNECT gate — base5351c9f

- Previous goal turn was progress:5351c9f native DNS/TLS implemented, actual SDK
  local TLS and separate public DNS/TLS diagnostic, suite/build/package committed.
- Host egress requires exact DNS-host allowlist/443, all resolved addresses public,
  numeric pinned dial, no HTTP forwarding/redirect following, finite headers/wall/
  idle/bytes/concurrency/total connections, redacted receipts and immediate socket
  withdrawal before SQL. TLS remains end-to-end in the actual native SDK.
- Reuse public IP/DNS validation currently embedded in research.web_fetcher by
  extracting transport-only helpers with domain-error mapping in the research
  adapter. Direct runtime import of a research adapter couples unrelated use cases.
- Test real connected socket pairs at the network seam, strict CONNECT parsing,
  mixed/private/transition DNS rejection, byte/idle/wall budgets, blocked writes,
  late dial after Stop, saturation and safe failure without payload/secret logging.
- This gate must next be fed only by an owned private-network helper; adding a
  CONNECT proxy while leaving native host networking would not enforce egress.
  No real credentials until private NET/no-bypass/Stop and actual SDK accepted.
  Global managed enrollment/all-actor account ownership remain pending.

## Bounded host CONNECT gate checkpoint — base5351c9f

- Initial pytest reserved-name collection issue corrected before RED21 missing
  proxy. RED4 missing channel. RED header-wall test proved intake exceeded total
  wall budget; min(header,wall) now enforces admission's total deadline.
- GREEN59 focused includes34 host gate/FD channel cases plus existing web/TLS.
  Full1464:1361 pass,100 exact original baseline failures,3 skip,29 warnings;
  531 runtime pass. Offline wheel34 runtime + shared helper/research adapter bytes
  match; isolated -I -S real SCM_RIGHTS/CONNECT/byte/EOF smoke and prior native/
  analysis/auth/recovery smokes pass. No new model or external provider calls.
- pytest-socket classified socket(fileno=...) as INET despite transferred Unix FD;
  channel tests allow loopback only and retain non-loopback connect blocking.
- Ruling: share transport-only DNS/IP primitives without runtime importing research
  adapter — same numeric pinning policy, acyclic dependencies — cost: DNS child
  remains host-owned/bounded rather than enrolled in native cgroup, still pending.
- Ruling: exact CONNECT/443, all resolved answers public, numeric dial and no
  automatic retry/redirect — no re-resolving a vetted hostname — cost: unusual
  proxies, ports/headers and mixed private DNS fail closed.
- Ruling: check shared byte budget/withdrawal at nonblocking payload writes under
  short lock; no lock over DNS/remote wait — Stop independent — cost: metadata-only
  receipts describe bytes/outcome, not application success or unseen usage.
- Ruling: inherited SEQPACKET, one SCM_RIGHTS stream, stable duplicated child FD —
  no host TCP proxy listener — cost: launcher must close its copies and prevent
  untrusted client access to the channel; that profile remains to be implemented.
- Ruling: host gate is not egress enforcement until private NET removes bypass;
  opaque TLS tunnel is not L7/domain-fronting firewall — cost: real subscription/
  product migration stays incomplete, not enabled on proxy env alone.
- Final RED global IPv6 + scope_id proved classification accepted a scoped global
  address. Shared validator now rejects every IPv6 scope; final59 focused, full
  suite/build/current wheel rerun and passed with exact100 original failures.
- Ruling: globally routable IPv6 does not authorize interface scope identifiers —
  DNS must supply ordinary numeric destinations — cost: scoped IPv6 configurations
  are rejected in both host gate and source acquisition.
- No actual credentials/model/image generation, user DB migration, host install,
  parent cgroup change, push/merge/deploy. No full phase/scenario closed.

## Next brief after host gate — full objective unchanged

Implement actual private-NET native profile/broker composition next. Do not redo
completed host gate/shared DNS/public TLS/auth/journal/domain. Proposed design:
- New NativeProxyCapsule omits --share-net. Sealed trusted proxy_payload runs after
  G, closes extra FDs, sets nondumpable, creates loopback listener, forks native.
  Child closes listener/channel, installs strict native seccomp (also deny ptrace,
  process_vm and pidfd_getfd), execs measured Codex. Trusted helper setup may allow
  bind/listen/accept; untrusted/native child must not retain that setup authority.
- Helper supplies accepted sockets as F + SCM_RIGHTS via inherited EgressChannel.
  Pin channel.duplicate_child() in capsule through spawn, close parent child-end
  after spawn. bwrap --preserve-fds contiguous range may be needed: close all extra
  original source/control FDs in trusted helper before native exec; prove no leaks.
- Fixed HTTP_PROXY/HTTPS_PROXY/ALL_PROXY loopback URL and empty NO_PROXY; preserve
  sealed CA env, no user proxy credentials. Verify bwrap loopback is up. Helper
  watches native exit/host EOF, closes accepted local copies and kills/reaps native
  on host loss. All helper/native actors remain in original kernel domain.
- Broker reserves before channel creation, registers under decision lock before G;
  withdraw closes socket/channel before SQL. close_peer/revoke drain before receipt.
  Record policy and helper/host gate/shared validator hashes, require NativeNetwork,
  retain same-key conflict semantics. No model-selected policy or direct-net fallback.
- Actual SDK local TLS/proxy test uses controlled DNS-host cert and dial seam mapping
  a validated public numeric IP only to the test endpoint. Verify unknown CA/name,
  redirected/new disallowed CONNECT, direct host/public/Unix/control bypass, helper/
  owner loss, Stop under SQL/backpressure, FD cleanup. WebSocket needs its own trial.
Default DNS subprocess/all trusted host actor origin still require managed enrollment;
then account coexistence, persistent native state, subscription+Ken/business/code-mode
and product factory adoption. All71 tools/11 categories, engine/autonomy/roles/flows/
agent communication, exact Git/review/CI, prompts/books/evals/human comprehension,
data/restore/bootstrap/CLI/TUI/install, aliases/transfer/budgets/dependencies/18 npm
advisories and100 baseline failures remain. Independent UI work:6/36 desktop+2/12
mobile concepts,2 pilots,0/12 accepted;30+10 concepts/10 routes/all12 acceptance.
Final fresh whole-branch review still required. Full objective remains active.
