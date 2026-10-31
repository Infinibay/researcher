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
A further trial uses equal wall/tool/observed-token limits and a larger defensive
call fuse; it must be assessed before drawing comparative conclusions.

Raw process logs, transcripts and harnesses currently live under this plan's
`.superpowers/sdd/2026-10-31-actualizacion-proyecto/` scratch workspace.
Sanitized, durable result excerpts are being collected alongside this report.
The official native protocol source is [Codex App Server](https://learn.chatgpt.com/docs/app-server),
checked against schemas generated by the installed CLI.

## Required remaining scenarios

- [ ] Repeat explain/code-change trials and compare verifiable outcomes.
- [ ] Both candidates: implement the same small correction and pass real tests.
- [ ] Research from attachment plus web source to a durable finding and report
  recoverable through Researcher's `/reports` flow.
- [ ] Correct an active premise; distinguish delivery receipt from applied context.
- [ ] Cancel during generation and a slow tool; reconcile actual effects.
- [ ] Restart and resume native identity without replaying the original request.
- [ ] Two projects with homonymous files/tasks, separate settings and sessions.
- [ ] Quota/auth/Ken failures reported clearly, with no metered fallback.
- [ ] Complete capability matrix and inference inventory, then record the runtime
  decision with limitations and pinned versions.
