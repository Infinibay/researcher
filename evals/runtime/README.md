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

The current live harnesses are development probes retained in this plan's
scratch workspace; a portable automated live-evaluation runner is still pending.
Do not treat this directory as a completed benchmark or run its slow tool as part
of the common test suite. Live tasks require explicit invocation, subscription
access and the same external guards.

For code corrections, independently run `python -B -m unittest -v` and inspect
Git diff against the baseline; model claims are not verification. For
cancellation, `slow_tool.py` deliberately writes a marker before a 60-second wait
and a delayed effect. A PID inside that execution environment is not necessarily
a host PID. Correlate native identity and terminal status, retire the connection
and reconcile before another attempt; never replay solely because observation
expired. Researcher's product-level cancellation acceptance is broader than
this fixture.
