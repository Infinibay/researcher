# BrainstormingFlow

**File:** `backend/flows/brainstorming_flow.py`
**State Model:** `BrainstormState`
**Purpose:** Time-limited ideation sessions with multi-agent participation for generating new tasks when project objectives are not yet fully met.

## State Model

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | str | Parent project ID |
| `participants` | list | Participating agent roles |
| `ideas` | list | Raw ideas from brainstorm rounds |
| `consolidated_ideas` | list | De-duplicated and ranked ideas |
| `selected_ideas` | list | Top ideas selected for implementation |
| `start_time` | float | Session start timestamp |
| `phase` | str | `BRAINSTORM` / `CONSOLIDATION` / `DECISION` / `PRESENTATION` / `COMPLETE` |
| `time_limit_brainstorm` | int | Brainstorm phase time limit (default: 900s = 15 min) |
| `time_limit_decision` | int | Decision phase time limit (default: 300s = 5 min) |
| `user_approved` | bool | Whether user approved selected ideas |
| `user_feedback` | str | User feedback on rejection |
| `round_count` | int | Current brainstorm round |
| `max_rounds` | int | Maximum brainstorm rounds (default: 5) |

## Flow Diagram

```mermaid
flowchart TD
    START(["START<br/>Called from MainProjectFlow<br/>or StagnationDetectedListener"]) --> start_session["start_session<br/>Configure participants:<br/>Team Lead, Developer, Researcher<br/>Phase → BRAINSTORM"]

    start_session -->|"session_started"| brainstorm["brainstorm_phase<br/>🤖 Team Lead proposes ideas<br/>🤖 Developer proposes ideas<br/>🤖 Researcher proposes ideas<br/>⏱️ Up to 5 rounds or 15 min"]

    brainstorm -->|"brainstorm_time_up"| consolidate["consolidate_ideas<br/>🤖 Team Lead<br/>De-duplicate and rank ideas<br/>Phase → CONSOLIDATION"]

    consolidate -->|"ideas_consolidated"| decision["decision_phase<br/>🤖 Team Lead<br/>Select top ideas<br/>Phase → DECISION<br/>⏱️ Max 5 min"]

    decision -->|"ideas_selected"| present["present_to_user<br/>🤖 Project Lead<br/>Present selected ideas to user<br/>Phase → PRESENTATION"]
    decision -->|"decision_time_up"| timeout["finalize_on_timeout<br/>Use top 3 consolidated ideas"]
    timeout --> present

    present --> user_router{"user_decision_router<br/>User approves or rejects"}

    user_router -->|"approved"| create_tasks["create_tasks_from_ideas<br/>🤖 Team Lead<br/>Create epics/milestones/tasks<br/>Phase → COMPLETE"]
    user_router -->|"rejected"| ask_why["ask_why_rejected<br/>Capture user feedback<br/>Reset ideas and rounds"]

    ask_why -->|"session_started<br/>(restart)"| brainstorm

    create_tasks --> END_DONE(["END - Tasks Created<br/>Returns to MainProjectFlow"])

    style START fill:#4CAF50,color:#fff
    style END_DONE fill:#2196F3,color:#fff
    style user_router fill:#FF9800,color:#fff
    style brainstorm fill:#E91E63,color:#fff
```

## Brainstorm Phase Detail

```mermaid
sequenceDiagram
    participant BF as BrainstormingFlow
    participant TL as Team Lead
    participant DEV as Developer
    participant RES as Researcher

    Note over BF: Phase = BRAINSTORM

    loop Up to 5 rounds (or 15 min)
        BF->>TL: Generate ideas
        TL-->>BF: Ideas (parsed)
        BF->>DEV: Generate ideas
        DEV-->>BF: Ideas (parsed)
        BF->>RES: Generate ideas
        RES-->>BF: Ideas (parsed)
        Note over BF: Check time limit
    end

    Note over BF: Time up → CONSOLIDATION
```

## Phase Progression

```mermaid
stateDiagram-v2
    [*] --> BRAINSTORM: Session starts
    BRAINSTORM --> CONSOLIDATION: Time up or max rounds
    CONSOLIDATION --> DECISION: Ideas ranked
    DECISION --> PRESENTATION: Ideas selected
    DECISION --> PRESENTATION: Timeout (use top 3)
    PRESENTATION --> COMPLETE: User approves
    PRESENTATION --> BRAINSTORM: User rejects (restart)
    COMPLETE --> [*]: Tasks created
```

## Time Constraints

```mermaid
gantt
    title Brainstorming Session Timeline
    dateFormat mm:ss
    axisFormat %M:%S

    section Brainstorm
    Idea generation (max 15 min)     :brainstorm, 00:00, 15m

    section Consolidation
    De-duplicate & rank              :consolidate, after brainstorm, 2m

    section Decision
    Select top ideas (max 5 min)     :decision, after consolidate, 5m

    section Presentation
    User review & approval           :present, after decision, 5m
```

## Key Decision Points

1. **Time/Round Limits** - Brainstorm phase ends after 5 rounds or 15 minutes, whichever comes first.
2. **Decision Timeout** - If Team Lead can't decide within 5 minutes, top 3 consolidated ideas are used.
3. **User Approval** - User must approve selected ideas. Rejection restarts the entire brainstorm with feedback.

## Agent Responsibilities

| Agent | Actions |
|-------|---------|
| **Team Lead** | Proposes ideas, consolidates/ranks, selects top ideas, creates tasks from approved ideas |
| **Developer** | Proposes ideas during brainstorm rounds |
| **Researcher** | Proposes ideas during brainstorm rounds |
| **Project Lead** | Presents selected ideas to user for approval |
