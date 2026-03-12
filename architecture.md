# Architecture

An overview of how Infinibay Researcher works under the hood.

## Loop Engine

Agents execute tasks through a **plan-execute-summarize** cycle that replaces traditional ReAct loops. The key insight: rebuild the prompt from scratch every iteration, keeping only compact summaries of previous work.

**How it works:**

1. **Plan**: The agent creates 2-3 concrete steps based on the task. Plans grow dynamically — new steps are added as the agent discovers things.
2. **Execute**: One step at a time, a small amount of tool calls per step. The agent reads files, searches code, creates tasks, sends messages, etc.
3. **Summarize**: After each step, the agent produces a ~50-token summary. Raw tool output is discarded.

This separation means the context window never explodes. After 50 steps, the prompt contains 50 short summaries (~2500 tokens) instead of 50 full tool outputs (potentially hundreds of thousands of tokens).

**Two kinds of memory:**

- **Temporary** (per-task): Action summaries that live in the iteration prompt. Rebuilt fresh each iteration from stored metadata. Discarded when the task completes.
- **Permanent** (DB): Findings, wiki pages, reports, and session notes persist across tasks and agent restarts. Agents can search and retrieve these at any time.

## Prompt Structure

Every iteration prompt is built from XML sections:

```xml
<task>
  Research the feasibility of using WebSockets for real-time updates...
</task>

<plan>
  1. [done] Search for WebSocket libraries compatible with FastAPI
  2. [active] Read the starlette WebSocket documentation
  3. [pending] Compare with SSE approach
</plan>

<previous-actions>
  Step 1: Found 3 libraries: websockets, starlette built-in, socket.io.
  Starlette has native support, no extra dependency needed.
</previous-actions>

<current-action>
  Step 2: Read the starlette WebSocket documentation
</current-action>

<next-actions>
  Step 3: Compare with SSE approach
</next-actions>

<expected-output>
  A summary of findings with a recommendation.
</expected-output>
```

The system prompt is static per role — it defines the agent's identity, capabilities, team roster, and the execution protocol. Task prompts inject dynamic context: project state, dependencies, blockers, and conversation history.

## Semantic Deduplication

Before creating a task, epic, milestone, or finding, the system checks for semantic duplicates using embedding similarity.

- Embeds the new title and all existing titles in one batch using a lightweight model (all-MiniLM-L6-v2 via ChromaDB)
- Computes cosine similarity between the new item and every existing one
- If similarity exceeds **0.82**, the creation is blocked and the agent is told about the existing item

This prevents the common failure mode where agents create slight variations of the same work item ("Implement user auth", "Add user authentication", "Build login system").

Findings and wiki pages also store embeddings for semantic search — agents can query by meaning, not just keywords.

## Auto-Recovery

The system survives `Ctrl+C` and restarts without losing progress.

**On shutdown:**
1. The current flow state is serialized to a `flow_snapshots` table (step name, full state)
2. Each agent loop saves its current event ID to `agent_loop_state`
3. The loop engine checkpoints its internal state (plan, history, metrics) to `agent_events.progress_json`
4. In-progress tasks are reset to `pending` so they can be claimed again

**On restart:**
1. The flow snapshot is loaded and the flow resumes from the last step
2. Agent loops check for interrupted events and resume them with the saved checkpoint
3. Stale pending events from the previous session are cleared

The net effect: you can `Ctrl+C` mid-task, restart, and the agent picks up roughly where it left off.

## Event-Driven Autonomy

Agents don't receive instructions from a central controller. They autonomously poll for work, pick the most relevant event, and act on it.

**The event loop (per agent, runs in a background thread):**

```
1. POLL    → query pending events for this agent
2. SCORE   → role-specific evaluator ranks events by relevance
3. CLAIM   → atomic DB update prevents two agents from grabbing the same event
4. EXECUTE → dispatch to the appropriate handler (development flow, research flow, etc.)
5. IDLE    → if no events, exponential backoff (30s → 60s → 120s → 5min max)
6. SCAVENGE → after several idle polls, look for orphaned tasks to claim
```

**Event types include:** `task_available`, `review_ready`, `task_rejected`, `message_received`, `stagnation_detected`, `evaluate_progress`, and more.

**How agents interact:**

- The **team lead** creates tasks based on project goals and user input
- **Developers** and **researchers** independently claim tasks that match their role
- Agents communicate via messages — asking questions, requesting clarification, reporting blockers
- The **code reviewer** picks up tasks marked `review_ready` and provides feedback
- If a task is rejected, the original agent gets a `task_rejected` event with the reviewer's feedback

**Scavenger:** When an agent has been idle for a while, a scavenger process searches for orphaned work — tasks sitting in `pending` or `backlog` with no active event. It creates events so agents can discover and claim them.

**Watchdog:** A background thread monitors for zombie events (stuck in `in_progress` too long) and dead agents (no poll activity). It recovers by resetting events and tasks back to claimable state.

## Anti-Loop System

When agents communicate freely, they can get stuck in loops — asking the same question repeatedly, or two agents bouncing messages back and forth. A 5-layer guard prevents this:

1. **Circuit breaker**: If an agent has been blocked too many times recently, all its messages are held until a cooldown expires.
2. **Rate limiting**: Per-thread and global caps on messages per minute.
3. **Deduplication**: Exact hash + trigram-based similarity check against recent messages. Near-duplicates (>75% similar) are blocked.
4. **Ping-pong detection**: Detects strict alternation patterns (A→B→A→B→A) and breaks the cycle.
5. **Pair volume cap**: Limits total exchanges between any two agents within a time window, regardless of content.

A **question registry** prevents duplicate questions to the user. If one agent asks "What framework should we use?" and gets an answer, other agents with the same question get the cached answer automatically.

## Other Details

**Completion detection**: The system tracks project state — `ACTIVE` (tasks running), `WAITING_FOR_RESEARCH` (only research in progress), `IDLE_OBJECTIVES_MET` (all done), or `IDLE_OBJECTIVES_PENDING` (tasks done but goals remain). The team lead uses this to decide whether to create more work or wrap up.

**Tool context**: When an agent runs, thread-local context variables hold the agent ID, project ID, task ID, and event ID. Tools read these to know who's calling and what project they're working on — no parameters needed.

**DB access**: All database calls go through `execute_with_retry()` with exponential backoff for SQLite's WAL-mode contention. No raw sqlite3 connections anywhere in the codebase.
