"""Tests for the agent event creation and lifecycle helpers."""

from __future__ import annotations

import json

from backend.autonomy.events import (
    atomic_claim_event,
    cancel_pending_events,
    create_message_event,
    create_system_event,
    create_task_event,
    get_event_by_id,
    load_loop_state,
    poll_pending_events,
    save_loop_state,
    update_event_status,
)
from backend.tests.autonomy.conftest import seed_roster, seed_task


def test_create_task_event_for_agent(db_conn, executing_project):
    """Creating a task event for a specific agent inserts one row."""
    pid = executing_project
    seed_roster(db_conn, pid, [("dev_1_p1", "developer")])
    tid = seed_task(db_conn, pid, task_type="code")

    ids = create_task_event(pid, tid, "task_available", target_agent_id="dev_1_p1")
    assert len(ids) == 1

    event = get_event_by_id(ids[0])
    assert event is not None
    assert event["agent_id"] == "dev_1_p1"
    assert event["event_type"] == "task_available"
    assert event["status"] == "pending"
    payload = json.loads(event["payload_json"])
    assert payload["task_id"] == tid


def test_create_task_event_for_role(db_conn, executing_project):
    """Creating a task event for a role resolves all matching agents."""
    pid = executing_project
    seed_roster(db_conn, pid, [
        (f"developer_1_p{pid}", "developer"),
        (f"developer_2_p{pid}", "developer"),
    ])
    tid = seed_task(db_conn, pid)

    ids = create_task_event(pid, tid, "task_available", target_role="developer")
    assert len(ids) == 2


def test_create_message_event(db_conn, executing_project):
    """Message events are created for the target agent."""
    pid = executing_project
    seed_roster(db_conn, pid, [(f"team_lead_p{pid}", "team_lead")])

    ids = create_message_event(
        pid, "dev_1", None, "team_lead", "Need help with task 1",
    )
    assert len(ids) == 1

    event = get_event_by_id(ids[0])
    assert event["event_type"] == "message_received"
    payload = json.loads(event["payload_json"])
    assert payload["from_agent"] == "dev_1"
    assert "Need help" in payload["message"]


def test_create_system_event(db_conn, executing_project):
    """System events are created for a specific agent."""
    pid = executing_project
    eid = create_system_event(pid, "team_lead_p1", "health_check", {"stuck_tasks": 3})
    assert eid is not None

    event = get_event_by_id(eid)
    assert event["event_type"] == "health_check"


def test_poll_pending_events(db_conn, executing_project):
    """Polling returns pending events in priority order."""
    pid = executing_project
    agent = f"developer_1_p{pid}"
    seed_roster(db_conn, pid, [(agent, "developer")])

    create_system_event(pid, agent, "evaluate_progress", priority=80)
    create_system_event(pid, agent, "task_available", priority=20)

    events = poll_pending_events(agent)
    assert len(events) == 2
    assert events[0]["priority"] <= events[1]["priority"]


def test_atomic_claim_event(db_conn, executing_project):
    """Claiming an event atomically updates its status."""
    pid = executing_project
    agent = f"dev_p{pid}"
    eid = create_system_event(pid, agent, "task_available")

    assert atomic_claim_event(eid, agent) is True
    # Second claim should fail
    assert atomic_claim_event(eid, agent) is False

    event = get_event_by_id(eid)
    assert event["status"] == "claimed"


def test_update_event_status(db_conn, executing_project):
    """Updating event status tracks timestamps and errors."""
    pid = executing_project
    eid = create_system_event(pid, "agent_1", "test_event")

    update_event_status(eid, "in_progress")
    event = get_event_by_id(eid)
    assert event["status"] == "in_progress"
    assert event["started_at"] is not None

    update_event_status(eid, "failed", error="something broke")
    event = get_event_by_id(eid)
    assert event["status"] == "failed"
    assert event["error_message"] == "something broke"
    assert event["completed_at"] is not None


def test_cancel_pending_events(db_conn, executing_project):
    """Cancelling pending events marks them as cancelled."""
    pid = executing_project
    agent = "agent_1"
    create_system_event(pid, agent, "ev1")
    create_system_event(pid, agent, "ev2")

    cancelled = cancel_pending_events(agent, pid)
    assert cancelled == 2

    events = poll_pending_events(agent)
    assert len(events) == 0


def test_loop_state_save_load(db_conn, executing_project):
    """Saving and loading loop state works correctly."""
    pid = executing_project
    agent = "dev_1_p1"

    save_loop_state(agent, pid, None, "idle")
    state = load_loop_state(agent)
    assert state is not None
    assert state["status"] == "idle"
    assert state["current_event_id"] is None

    # Create a real event so the FK constraint is satisfied
    eid = create_system_event(pid, agent, "test_event")
    save_loop_state(agent, pid, eid, "processing")
    state = load_loop_state(agent)
    assert state["status"] == "processing"
    assert state["current_event_id"] == eid
