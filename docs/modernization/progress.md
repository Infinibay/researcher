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
