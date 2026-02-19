# Flows Usage Guide

## Starting MainProjectFlow

### New Project

```python
from backend.flows import MainProjectFlow, ProjectState

flow = MainProjectFlow()
result = flow.kickoff(inputs={
    "project_name": "My Research Project",
})
```

### Resume Existing Project

```python
from backend.flows import MainProjectFlow

flow = MainProjectFlow()
result = flow.kickoff(inputs={
    "project_id": 42,
})
```

The flow automatically detects the project status:
- `new` → starts from requirements gathering
- `planning` → restarts planning
- `executing` → resumes task execution
- `completed` → returns immediately

## Triggering Flows Manually

### DevelopmentFlow

```python
from backend.flows import DevelopmentFlow

flow = DevelopmentFlow()
flow.kickoff(inputs={
    "project_id": 1,
    "task_id": 10,
})
```

### CodeReviewFlow

```python
from backend.flows import CodeReviewFlow

flow = CodeReviewFlow()
flow.kickoff(inputs={
    "project_id": 1,
    "task_id": 10,
    "branch_name": "task-10-feature",
    "developer_id": "developer_p1",
})
```

### ResearchFlow

```python
from backend.flows import ResearchFlow

flow = ResearchFlow()
flow.kickoff(inputs={
    "project_id": 1,
    "task_id": 5,
})
```

### BrainstormingFlow

```python
from backend.flows import BrainstormingFlow

flow = BrainstormingFlow()
flow.kickoff(inputs={
    "project_id": 1,
})
```

## Monitoring Flow State

### Check Flow State After Execution

```python
flow = MainProjectFlow()
flow.kickoff(inputs={"project_id": 42})

# Access state after completion
print(f"Status: {flow.state.status}")
print(f"Completed tasks: {flow.state.completed_tasks}")
```

### Query Project State from DB

```python
from backend.flows.helpers import load_project_state, get_pending_tasks

state = load_project_state(project_id=42)
print(f"Project: {state['name']} ({state['status']})")
print(f"Task counts: {state['task_counts']}")

pending = get_pending_tasks(42)
print(f"Pending tasks: {len(pending)}")
```

## Event Listeners

### Start All Listeners for a Project

```python
from backend.flows import ListenerManager

manager = ListenerManager(project_id=42)
manager.start_all()

# Later...
manager.stop_all()
```

### Subscribe to Events

```python
from backend.flows import event_bus, FlowEvent

def on_task_done(event: FlowEvent):
    print(f"Task {event.entity_id} completed!")

event_bus.subscribe("task_done", on_task_done)
```

### Custom Event Listeners

```python
from backend.flows.event_listeners import BaseEventListener, FlowEvent

class MyListener(BaseEventListener):
    def check(self):
        # Query DB for your condition
        # If condition met, emit event:
        self.bus.emit(FlowEvent(
            event_type="my_custom_event",
            project_id=self.project_id,
            entity_type="project",
        ))

listener = MyListener(project_id=42, poll_interval=10.0)
listener.start()
```

## Troubleshooting

### Flow State Persistence

Flows use `@persist()` for automatic state persistence via CrewAI's
`SQLiteFlowPersistence`. Flow state is saved after each method execution.

If a flow crashes mid-execution, re-create the flow with the same inputs
to resume from the last persisted state.

### Agent Context

Every flow method that invokes an agent must call `agent.activate_context()`
before creating a Crew. This sets the `project_id`, `agent_id`, and optional
`task_id` in Python contextvars, which all tools read automatically.

```python
agent = get_agent_by_role("developer", project_id)
agent.activate_context(task_id=task_id)
run_id = agent.create_agent_run(task_id)
# ... create Crew and kickoff ...
agent.complete_agent_run(run_id, status="completed")
```

### Database Connection Issues

All DB operations use `execute_with_retry` with exponential backoff.
If SQLite reports `BUSY` or `LOCKED`, the system retries up to 5 times
with increasing delays. Ensure WAL mode is enabled (set by schema.sql pragmas).

### Event Listener Not Detecting Changes

- Verify the project exists and has `status = 'executing'`
- Check that `events_log` has trigger-generated rows (task/epic changes
  automatically log to `events_log` via SQLite triggers in schema.sql)
- Verify the listener's `_last_event_id` was not initialized past your events
- Check logs for poll errors (listeners catch and log exceptions)
