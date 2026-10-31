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
