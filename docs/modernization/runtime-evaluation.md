# Runtime evaluation — in progress

The runtime has not been selected. The current product still uses its legacy
orchestrator. This report separates native integration evidence from product
acceptance and preserves failed trials as findings.

## Environment and scope

- Researcher worktree: `codex/project-modernization`, based on `e7b5719`.
- Codex CLI/App Server: `0.166.0`; native `account/read` reports `chatgpt`.
- Infinidev: `0.30.0`, source commit
  `9045556ef7af2252b381ac9b1b9bd89479694487`, installed in a separate environment.
  Its resolved Python `ken-rank` dependency is `0.15.0`; both candidates' MCP
  subprocesses use the same separately installed published `ken-rank==0.18.0`.
- Synthetic Git repositories only; no production databases, services, remote
  repositories or user projects are modified. The fixture has an intentionally
  incorrect `total_due`, two unittest cases and an attached fictional policy.
- Model: `gpt-6.1-sol` through the existing ChatGPT subscription. Provider API
  keys/base-URL overrides are removed from child environments. Codex is forced
  to `chatgpt` login and `openai` provider. The Infinidev evaluation shim refuses
  any inference route except its `openai_subscription` endpoint.

## Limits demonstrated before live inference

`backend/tests/runtime/test_codex_session.py` uses a real subprocess speaking a
fake native protocol. Together with transport tests it covers bounded frames,
queues and writes; failed/malformed/late responses; managed-account admission;
silence or reasoning-only activity; wall, turn, tool and observed-token limits;
control correlation; native resume without replay; and explicit host decisions.

Cancellation during an unacknowledged start waits briefly for native identity,
then terminates the owned process if identity cannot be established. Duplicate
cancellation shares one interruption request. An interruption receipt is not
proof of finished work; native terminal status is tracked separately.

Live candidate limits: 150 seconds per task, 75 seconds without observable tool
completion, 35 observed tool calls and 180,000 observed tokens. The native
session also caps submitted turns. Infinidev additionally has a test-only
central completion-call fuse (initially 8, then 32 for the comparable trial).
This shim is not a product integration or a change to the candidate source.
Campaigns run serially under an OS file lock and own/reap their child processes.

These are operational fuses, not proof of semantic progress or hard pre-dispatch
quotas. A native tool may already have run when its event arrives. Token/quota
data not reported by a candidate remains **unknown**, not zero. Product-wide
budgets persisted across restarts remain to be implemented.

## Evidence so far

| Trial | Observed outcome | What it does not prove |
| --- | --- | --- |
| Native Codex metadata | initialize, managed ChatGPT account and catalog of eight models | Model-task acceptance or remaining subscription quota |
| Ken preparation | Published CLI indexed three synthetic files and seven owners | Complete project coverage or runtime isolation |
| Native Ken discovery and direct call | `mcpServerStatus/list` exposes the selected Ken tools; `mcpServer/tool/call` finds `total_due` with numbered source, `isError=false` | A model choosing and using the tool |
| Codex explanation, first two trials | Interrupted on an unhandled Ken MCP approval request; no permission was silently granted | Explanation success |
| Codex explanation with explicit scoped host consent | Completed; successful model-initiated `ken_find`, source inspection, actual unittest failures, correct numeric examples and evidence/interpretation distinction. 48.81 seconds, four observed tool items, 89,766 native reported total tokens | Repetition reliability, research persistence, correction, restart or two-project isolation |
| Infinidev HTTP preflight | Authenticated app serves `/api/info` and 55 tools; wrong bearer is rejected with 401; one workspace per process | Model behavior, tool invocation or comprehensive security |
| Infinidev explanation, initial 8-call fuse | Ended after the completion-call fuse; inspected source but did not invoke Ken or execute the tests before stopping. It returned `idle` with an agent message reporting engine failure | Candidate incapability under other bounds; `idle` is not task success |

Codex's successful explanation included one unsuccessful Ken call before a
successful call; the first tool error was generic. This is a diagnostic and
reliability limitation, not a hidden successful tool invocation. The failing
unittest command is expected evidence for this particular explanation task.

The initial Infinidev call fuse is not directly comparable to Codex's submitted
turn count: native internal model requests are not exposed by that count.
A follow-up with the same wall/tool/observed-token limits first exposed a
permission-policy defect in the evaluation: the fixture unittest command had
been denied. That trial is not a valid task comparison.

The subsequent trial explicitly warmed MCP before model admission and permitted
that exact unittest command. Infinidev then exposed 59 tools (including the four
selected Ken readers), invoked `ken_find` successfully and ran the actual tests.
It took 145.31 seconds and 23 intercepted subscription requests; token usage was
not reported. Its final reply did not explain the numeric discrepancy: it said
research was complete but the `done` closure was rejected because the requested
suite failed, even though fixing it was outside scope. Thus the explanation
acceptance criterion was not met. Source files were unchanged.

This reveals integration costs rather than a universal quality verdict:

- The web bootstrap does not warm MCP; tool discovery only reads already
  running servers. The evaluation shim had to call blocking discovery before
  admission. This must be part of a real Infinidev adapter if selected.
- Multiple Ken calls failed with optional-argument validation errors (`cache_mb`,
  `rules`, `libraries`) before a fully specified call succeeded. The errors and
  arguments are retained in `infinidev-explain-evidence.json`; an isolated
  no-model reproduction is still needed to assign the exact schema/default
  defect to its owner.
- The candidate conflated expected test failures in an explanation task with
  inability to close the task. Researcher must own task-specific acceptance;
  a native `idle` or `completed` status cannot decide product success.

Codex also completed the code correction trial in 19.19 seconds, with eight
observed tool items and 109,235 native reported total tokens. An independent
parent-process unittest run passed both cases, and Git diff showed only
`invoice.py` changed. Its resume trial reopened that same native thread in a
new App Server process, recalled the correction and tests without using tools,
and preserved the source hash. A separate live steering trial changed the
requested example from 100/0.21 to 200/0.10 during execution; the native receipt
correlated with the active turn and the resulting `proposal.md` contained the
corrected 220.00 example. This demonstrates that bounded fixture interaction,
not durable correction propagation across product agents.

Infinidev also completed the same correction: 118.70 seconds and 26 intercepted
subscription requests, with token usage unknown. Independent unittest execution
passed both cases; Git diff showed only `invoice.py` changed. It disclosed the
incidental `__pycache__` generated by Python. Read-only shell approval policy
is an integration difference: a compound inspection command was denied, and
its file tools provided the necessary evidence instead. These timings are
single observations, not benchmarks of statistical performance.

Cancellation trials exposed two important observation boundaries. The native
execution PID comes from another PID namespace; it must not be inspected or
signalled as if it were a host PID. Native output-delta notifications were not
observed for the slow command in these trials. A fixture marker proved the
command had actually started. Cleanup after the first watchdog interruption
left the native turn `interrupted`, a failed command with exit code -1 in
`thread/read`, and no delayed write beyond the original 60-second tool deadline.
A later very early explicit interruption arrived before a command lifecycle
item was persisted; its delayed write was also absent after 76 seconds. That
case does not prove tool-terminal telemetry. A quoting-error trial never started
the slow tool and is excluded from cancellation acceptance. A further trial waited for the native command lifecycle identity, then sent
explicit interruption. The turn became `interrupted`, but polling `thread/read`
for three seconds did not recover a terminal command item. That trial therefore
failed the tool-terminal acceptance check; do not keep replaying it to obtain
a favorable result. The command and its marker must be reconciled first.

This is a release blocker for a claim of complete Stop support, not a reason
to infer success from the vanished App Server process. The RPC child ownership
proved by offline tests does not cover tools executed in another environment.
Next: inspect the pinned native tool lifecycle and evaluate explicit tool-job
ownership/cancellation in Researcher's MCP boundary. The generated schema says
`command/exec/terminate` applies to client-owned standalone command IDs; a
process ID observed in an agent's built-in shell item must not be treated as
one of those IDs. No product-level Stop acceptance is claimed.

**Policy change and verification:** the candidate adapter now retires its RPC
connection before returning an interrupted turn (or a turn raced by a cancel
request). A later attempt must reopen the durable thread. A new regression test
first failed because the peer remained alive, then passed after the change.
The final real fixture trial, run because this policy changed, confirmed native
`interrupted`, a reconciled failed command with exit -1, and no delayed effect
past the 60-second deadline. Cancellation through tool-terminal reconciliation
took 0.43 seconds in that one trial. This verifies the bounded fixture and
connection-retirement policy; durable product Stop, all tool types and crash
recovery remain open. See `codex-control-evidence.json`.


These are single observed trials. Do not infer causal prompting improvements,
statistical superiority or cross-project product guarantees from them.

Durable synthetic excerpts: `codex-explain-evidence.json`,
`codex-fix-evidence.json`, `infinidev-explain-evidence.json` and
`infinidev-fix-evidence.json`. Independent verification results are recorded
there separately from the agents' own reports.

Raw process logs, transcripts and harnesses currently live under this plan's
`.superpowers/sdd/2026-10-31-actualizacion-proyecto/` scratch workspace.
Sanitized, durable result excerpts are being collected alongside this report.
The official native protocol source is [Codex App Server](https://learn.chatgpt.com/docs/app-server),
checked against schemas generated by the installed CLI.

## Required remaining scenarios

- [ ] Repeat explain/code-change trials and compare verifiable outcomes.
- [x] Both candidates: implement the same small correction and pass real tests in the synthetic fixture (single trial each).
- [ ] Research from attachment plus web source to a durable finding and report
  recoverable through Researcher's `/reports` flow.
- [ ] Correct an active premise; distinguish delivery receipt from applied context.
- [ ] Cancel during generation and a slow tool; reconcile actual effects.
- [ ] Restart and resume native identity without replaying the original request.
- [ ] Two projects with homonymous files/tasks, separate settings and sessions.
- [ ] Quota/auth/Ken failures reported clearly, with no metered fallback.
- [ ] Complete capability matrix and inference inventory, then record the runtime
  decision with limitations and pinned versions.
