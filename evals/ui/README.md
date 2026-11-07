# Owner workspace browser checks

These checks create a fresh account-free native command and copy only its closed
synthetic database for inspection. They
pair a real local owner session over HTTP, open the built UI in sandboxed Chromium,
and read Tasks, command receipts/output, and Conversation. They never submit model
turns or product mutations. The login form itself is outside this flow.

From the repository root, build the frontend, then run (replace tool paths with
your installed pinned Node and Playwright browser directory):

```sh
python evals/ui/run_owner_capture.py \
  --codex-binary /absolute/path/to/codex \
  --cgroup-parent /sys/fs/cgroup/delegated-parent \
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

No `--source-root` or previous trial is required. `owner_trial.py` creates the
ALPHA/BETA projects, task1001 and actual calculation output, then closes all native
actors before HTTP starts. The browser checks the exact output bytes/text supplied
by that fresh fixture; the byte count is not hard-coded. No runtime inference is
configured. This requires preinstalled tools, native extension and a built web UI;
it is not a clean-install or all-page acceptance suite. Nine runtime-table
fingerprints do not compare every database table. Pairing occurs before browser
capture, so zero browser mutations excludes that initial pairing.

Current 17-state desktop/mobile run and selected visual review:
[fresh owner fixture audit](../../docs/design/audits/native-owner-fixture/report.md).
Historical captures and findings:
[owner workspace audit](../../docs/design/audits/2026-11-01-owner-workspace/report.md).
