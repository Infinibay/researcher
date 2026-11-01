# Owner workspace browser checks

These checks use an isolated copy of a prior **synthetic** analysis trial. They
pair a real local owner session over HTTP, open the built UI in sandboxed Chromium,
and read Tasks, command receipts/output, and Conversation. They never submit model
turns or product mutations. The login form itself is outside this flow.

From the repository root, build the frontend, then run (replace tool paths with
your installed pinned Node and Playwright browser directory):

```sh
.venv/bin/python evals/ui/run_owner_capture.py \
  --source-root .researcher/evaluations/analysis-inference-7792402f \
  --node /absolute/path/to/node \
  --browsers /absolute/path/to/playwright-browsers \
  --flow commands --keyboard --check
```

Repeat with `--viewport mobile`. Install the versions pinned in frontend's lock,
and install Chromium with `PLAYWRIGHT_BROWSERS_PATH` pointing to that directory.
Do not build concurrently with a capture: both consume `frontend/dist`. The wrapper
rejects an index change, uses a private temporary cookie handoff that is deleted,
and bounds the child to 90 seconds. Each run receives a new private evaluation root.

`--check` rejects axe findings, clipped mobile header controls, uncaught page
errors, failed assets, external dependencies and unexpected product mutations.
`--keyboard` verifies the first skip link, its main focus target and focus after
section navigation; it does not claim a complete keyboard audit. PNG, ARIA, header
layout, raw axe results and runtime fingerprints are saved with each run.

The source fixture must already exist beneath `.researcher/evaluations`. The
`commands` flow expects the real saved analysis trial's ALPHA project, task1001
and95 output bytes; it deliberately fails on another fixture. It is not yet a
self-contained clean-install E2E suite or coverage of every UI state. The nine
runtime-table fingerprints do not compare all database tables. Pairing is performed
by the HTTP helper, so zero browser mutations excludes that initial pairing.

Published captures and findings:
[owner workspace audit](../../docs/design/audits/2026-11-01-owner-workspace/report.md).
