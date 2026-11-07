# Project Budget Policy Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, preserving the authorized whole-project goal and deferring fine details.

**Goal:** Let the owner revise lifetime project admission limits without deleting consumption or starting work.

**Architecture:** Extend the existing policy with revision0 for historical/host defaults and immutable owner-change receipts. An explicit owner revision governs future reservations; existing attempts retain their frozen limits. Expected revision and operation identity protect concurrent edits and response recovery.

**Tech Stack:** Existing SQLite migrations, Python/FastAPI, React and TanStack Query. No new dependencies.

**Spec:** Parent modernization plan, E08 and human-control requirements; `docs/architecture/owner-history-budget.md` and the demonstrated gap in `docs/modernization/aggregate-budget-review.md`.

## Design decision and constraints

Use the existing budget panel with a small explicit edit form. Host configuration
continues to seed projects with no policy; it cannot overwrite an owner decision.
Changing host configuration alone remains a conflict for historical revision0.
A separate second policy store would duplicate admission ownership; silently
resetting accounting would lose evidence. The selected approach is an implementation
decision within the authorized plan, not a new preference attributed to the user.

New total limits may be below recorded usage: show zero remaining, retain the
excess and block future admissions. Already reserved work is not cancelled.
Integers use the shared browser-safe range1..9007199254740991. No model calls,
provider changes, automatic retries, resumption or hidden token refunds.

## Review focus

- Two editors at the same revision: exactly one change wins.
- Lost response/reload: recover the identical operation and original receipt.
- Consumption changes while editing: preserve it and calculate admission under the new total limits.
- Project switch: retain scope and reject stale/foreign receipts.
- Migration/crash: preserve old policies/dispatches, roll back interrupted writes and refuse destructive inverse after owner history.

## Task1: durable policy and admission

Files: new `backend/db/project_budget_schema.sql`, inverse helper and
`backend/runtime/project_budget.py`; migration catalog, `sqlite_runs.py`,
`history.py`; tests in `test_project_budget_policy.py`.

- [x] Write failing cases for create/update/replay/conflict, concurrent writes,
  decrease below usage, migration preservation/inverse and transactional rollback.
- [x] Add migration60, historical revision0, immutable change receipts.
- [x] Implement `ProjectBudgetPolicies.update(project_id, *, operation_key,
  expected_revision, turn_limit, token_limit, reason='') -> receipt` and
  `receipt(project_id, operation_key) -> receipt`; never dispatch.
- [x] Use explicit owner policy in subsequent admission without changing existing
  attempt limits; preserve historical host-policy mismatch detection.
- [x] Run directed pytest; retain source and installed evidence.

## Task2: owner API and existing budget panel

Files: `backend/api/routes/runs.py`, `frontend/src/api/history.ts`, new
`frontend/src/api/projectBudget.ts`, `WorkBudget.tsx`, and dedicated budget editor;
API/DOM tests plus browser evidence.

- [x] Add authenticated POST `/api/projects/{id}/work-budget` and GET
  `/api/projects/{id}/work-budget/changes/{operation_key}`; existing GET includes revision.
- [x] Add explicit total-limit form, optional reason, no-auto-start explanation,
  pending operation persisted before send and read-only receipt recovery.
- [x] Test owner authorization, lost response, stale version, reload and project isolation.
- [x] Verify a rendered desktop/mobile control using the existing visual language.
- [x] Build/install clean package, verify directed tests outside checkout, update
  dashboard/coverage and commit locally. Keep full modernization active.

Verification: [results](../../modernization/project-budget-policy-review.md). All scoped capabilities are implemented; mobile density/capture is DD108. Existing plan authorizations are unchanged and can use revised capacity in subsequent ordinary admissions. Full modernization remains active.
