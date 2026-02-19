# Event System Reference

## Architecture

The PABADA event system uses DB-polling listeners that detect state changes
and emit `FlowEvent` objects through an `EventBus`. Flows and other components
can subscribe to events to react automatically.

```
DB Triggers → events_log table → EventListeners (poll) → EventBus → Handlers
```

SQLite triggers in `schema.sql` automatically log changes to `events_log`:
- Task created/updated/status changed
- Epic created/status changed
- Milestone created/status changed

Event listeners poll `events_log` and `chat_messages` at configurable intervals
(default 5-30 seconds depending on listener type).

## Event Types

### Task Events

| Event Type | Source | Description |
|---|---|---|
| `task_status_changed` | `TaskStatusChangedListener` | Any task status change. Data: `{new_status, old_status}` |
| `task_review_ready` | `TaskStatusChangedListener` | Task moved to `review_ready` |
| `task_done` | `TaskStatusChangedListener` | Task completed |
| `task_failed` | `TaskStatusChangedListener` | Task failed |
| `new_task_created` | `NewTaskCreatedListener` | New task inserted |

### Project Events

| Event Type | Source | Description |
|---|---|---|
| `stagnation_detected` | `StagnationDetectedListener` | No completions + stuck tasks |
| `all_tasks_done` | `AllTasksDoneListener` | All project tasks completed |
| `epic_created` | `EpicCreatedListener` | New epic inserted |

### Communication Events

| Event Type | Source | Description |
|---|---|---|
| `user_message_received` | `UserMessageListener` | User sent a message to an agent. Data: `{to_agent, to_role, content}` |

### Flow Events (logged to events_log)

These are emitted by flows using `log_flow_event()` and stored in the DB:

| Event Type | Source Flow | Description |
|---|---|---|
| `project_created` | MainProjectFlow | New project created |
| `flow_resumed` | MainProjectFlow | Existing project resumed |
| `requirements_gathered` | MainProjectFlow | Requirements collected |
| `plan_created` | MainProjectFlow | Plan created by Team Lead |
| `plan_approved` | MainProjectFlow | User approved the plan |
| `plan_rejected` | MainProjectFlow | User rejected the plan |
| `structure_created` | MainProjectFlow | Epics/milestones/tasks created |
| `project_completed` | MainProjectFlow | Project finished |
| `task_assigned` | DevelopmentFlow | Task assigned to developer |
| `implementation_done` | DevelopmentFlow | Code implementation complete |
| `review_approved` | DevelopmentFlow | Code review passed |
| `review_escalated` | DevelopmentFlow | Review escalated to Team Lead |
| `task_completed` | DevelopmentFlow | Task fully completed |
| `escalation_resolved` | DevelopmentFlow | Team Lead resolved escalation |
| `review_started` | CodeReviewFlow | Review cycle started |
| `review_rejected` | CodeReviewFlow | Code rejected by reviewer |
| `rework_completed` | CodeReviewFlow | Developer completed rework |
| `review_finalized` | CodeReviewFlow | Review approved and finalized |
| `review_escalated` | CodeReviewFlow | Escalated after max rejections |
| `research_assigned` | ResearchFlow | Research task assigned |
| `literature_reviewed` | ResearchFlow | Literature review done |
| `hypothesis_created` | ResearchFlow | Hypothesis formulated |
| `findings_recorded` | ResearchFlow | Research findings recorded |
| `report_written` | ResearchFlow | Research report written |
| `peer_review_done` | ResearchFlow | Peer review completed |
| `research_revised` | ResearchFlow | Research revised after rejection |
| `research_completed` | ResearchFlow | Research validated and completed |
| `brainstorm_started` | BrainstormingFlow | Session started |
| `ideas_consolidated` | BrainstormingFlow | Ideas consolidated |
| `ideas_selected` | BrainstormingFlow | Top ideas selected |
| `brainstorm_restarted` | BrainstormingFlow | Session restarted after rejection |
| `brainstorm_tasks_created` | BrainstormingFlow | Tasks created from ideas |

## Listeners

### TaskStatusChangedListener

Polls `events_log` for `task_status_changed` events.
Emits specific sub-events for `review_ready`, `done`, and `failed`.

- **Poll interval:** 5 seconds
- **Source:** SQLite trigger on `tasks` table

### NewTaskCreatedListener

Polls `events_log` for `task_created` events.

- **Poll interval:** 5 seconds
- **Source:** SQLite trigger on `tasks` table

### UserMessageListener

Polls `chat_messages` for new `user_to_agent` messages.

- **Poll interval:** 5 seconds
- **Source:** Direct table polling

### StagnationDetectedListener

Monitors for project stagnation:
- 0 tasks completed in the threshold period (default 30 min)
- 2+ tasks stuck in `in_progress` or `rejected`
- Only triggers for `executing` projects
- Emits once per stagnation period (resets when resolved)

- **Poll interval:** 30 seconds

### AllTasksDoneListener

Detects when all tasks in a project are `done` or `cancelled`.
Only triggers for `executing` projects. Emits once.

- **Poll interval:** 10 seconds

### EpicCreatedListener

Polls `events_log` for `epic_created` events.

- **Poll interval:** 5 seconds
- **Source:** SQLite trigger on `epics` table

## Creating Custom Listeners

```python
from backend.flows.event_listeners import BaseEventListener, FlowEvent

class DeadlineApproachingListener(BaseEventListener):
    """Detect milestones approaching their due date."""

    def check(self):
        from backend.tools.base.db import execute_with_retry

        def _query(conn):
            rows = conn.execute(
                \"\"\"SELECT id, title, due_date FROM milestones
                   WHERE project_id = ?
                     AND status != 'completed'
                     AND due_date <= datetime('now', '+2 days')
                     AND due_date > datetime('now')\"\"\",
                (self.project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        milestones = execute_with_retry(_query)

        for ms in milestones:
            self.bus.emit(FlowEvent(
                event_type="deadline_approaching",
                project_id=self.project_id,
                entity_type="milestone",
                entity_id=ms["id"],
                data={"title": ms["title"], "due_date": ms["due_date"]},
            ))
```

## Emitting Events from Tools

Tools can log events that listeners will pick up:

```python
from backend.flows.helpers import log_flow_event

log_flow_event(
    project_id=self.project_id,
    event_type="custom_event",
    event_source="my_tool",
    entity_type="task",
    entity_id=task_id,
    event_data={"key": "value"},
)
```

## ListenerManager

Use `ListenerManager` to manage all listeners for a project:

```python
from backend.flows import ListenerManager, event_bus

manager = ListenerManager(project_id=42)

# Start all default listeners
manager.start_all()

# Add custom listener
from my_listeners import DeadlineApproachingListener
manager.add_listener(DeadlineApproachingListener(42))

# Stop all
manager.stop_all()
```

## EventBus

The global `event_bus` singleton handles event routing:

```python
from backend.flows import event_bus, FlowEvent

# Subscribe to specific event
event_bus.subscribe("task_done", lambda e: print(f"Task {e.entity_id} done!"))

# Subscribe to all events (wildcard)
event_bus.subscribe("*", lambda e: print(f"Event: {e.event_type}"))

# Emit custom event
event_bus.emit(FlowEvent(
    event_type="my_event",
    project_id=1,
    entity_type="project",
))
```
