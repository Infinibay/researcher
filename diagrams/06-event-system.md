# Event System & Flow Triggering

**File:** `backend/flows/event_listeners.py`
**Purpose:** Event-driven architecture that connects flows, agents, and external triggers through an EventBus with polling-based listeners.

## Event Listeners

```mermaid
flowchart TD
    subgraph Listeners["Polling Listeners (monitor DB)"]
        TSC["TaskStatusChangedListener"]
        NTC["NewTaskCreatedListener"]
        UML["UserMessageListener"]
        SDL["StagnationDetectedListener"]
        ATD["AllTasksDoneListener"]
        ECL["EpicCreatedListener"]
        AML["AgentMessageListener"]
        TCL["TicketCheckinListener"]
    end

    subgraph Events["Emitted Events"]
        e1["task_review_ready"]
        e2["task_done"]
        e3["task_failed"]
        e4["new_task_created"]
        e5["user_message_received"]
        e6["stagnation_detected"]
        e7["all_tasks_done"]
        e8["waiting_for_research"]
        e9["epic_created"]
        e10["agent_message_received"]
        e11["ticket_checkin_approved"]
    end

    subgraph Handlers["Flow Handlers"]
        h1["➡️ Start CodeReviewFlow"]
        h2["Notify developer"]
        h3["➡️ Start BrainstormingFlow<br/>(via BrainstormingCoordinator)"]
        h4["Prompt Project Lead<br/>for completion"]
        h5["Notify Project Lead"]
        h6["Dispatch message to<br/>agent in background thread"]
        h7["Signal DevelopmentFlow<br/>check-in gate"]
    end

    TSC --> e1 & e2 & e3
    NTC --> e4
    UML --> e5
    SDL --> e6
    ATD --> e7 & e8
    ECL --> e9
    AML --> e10
    TCL --> e11

    e1 -->|"task_review_ready"| h1
    e2 -->|"task_status_changed<br/>(rejected)"| h2
    e6 -->|"stagnation_detected"| h3
    e7 -->|"all_tasks_done"| h4
    e8 -->|"waiting_for_research"| h5
    e10 -->|"agent_message_received"| h6
    e11 -->|"ticket_checkin_approved"| h7
```

## Event Flow Connections

```mermaid
sequenceDiagram
    participant DB as Database
    participant EL as Event Listeners
    participant EB as EventBus
    participant LM as ListenerManager
    participant Flows as Flows

    loop Polling cycle
        EL->>DB: Check for state changes
        DB-->>EL: Changed records
        EL->>EB: Emit event(s)
        EB->>LM: Route to handler
        LM->>Flows: Start/signal flow
    end
```

## Listener Details

### TaskStatusChangedListener
Monitors task status changes and emits appropriate events.

```mermaid
flowchart LR
    task_change["Task status changed"] --> check{"New status?"}
    check -->|"review_ready"| e1["task_review_ready<br/>→ Start CodeReviewFlow"]
    check -->|"done"| e2["task_done"]
    check -->|"failed"| e3["task_failed"]
    check -->|"rejected"| e4["Notify developer"]
```

### StagnationDetectedListener
Detects when a project is stagnating (no progress over time).

```mermaid
flowchart LR
    stagnation["No progress detected"] --> emit["stagnation_detected"]
    emit --> coord["BrainstormingCoordinator"]
    coord --> bf["Start BrainstormingFlow"]
```

### AllTasksDoneListener
Checks if all tasks in the project are complete.

```mermaid
flowchart LR
    all_done["All tasks checked"] --> check{"Research pending?"}
    check -->|"No"| done["all_tasks_done<br/>→ Prompt Project Lead"]
    check -->|"Yes"| waiting["waiting_for_research<br/>→ Notify Project Lead"]
```

### TicketCheckinListener
Monitors check-in approvals for the DevelopmentFlow gate.

```mermaid
flowchart LR
    checkin["Team Lead approves check-in"] --> emit["ticket_checkin_approved"]
    emit --> gate["Unblock DevelopmentFlow<br/>check-in gate"]
```

## Event-to-Flow Mapping

| Event | Source Listener | Target Flow/Action |
|-------|----------------|-------------------|
| `task_review_ready` | TaskStatusChangedListener | Start **CodeReviewFlow** |
| `task_status_changed` (rejected) | TaskStatusChangedListener | Notify developer of rejection |
| `task_done` | TaskStatusChangedListener | (Tracked by MainProjectFlow) |
| `task_failed` | TaskStatusChangedListener | (Error handling) |
| `new_task_created` | NewTaskCreatedListener | (Tracked by MainProjectFlow) |
| `user_message_received` | UserMessageListener | Route to appropriate agent |
| `stagnation_detected` | StagnationDetectedListener | Start **BrainstormingFlow** |
| `all_tasks_done` | AllTasksDoneListener | Prompt Project Lead for completion |
| `waiting_for_research` | AllTasksDoneListener | Notify Project Lead |
| `epic_created` | EpicCreatedListener | (Tracked by MainProjectFlow) |
| `agent_message_received` | AgentMessageListener | Dispatch to agent in background |
| `ticket_checkin_approved` | TicketCheckinListener | Unblock **DevelopmentFlow** gate |

## Wiring (ListenerManager)

The `ListenerManager.wire_flow_handlers()` method connects events to flow handlers at startup. This is the central point where the reactive event system is configured.
