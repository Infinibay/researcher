"""Tests for backend.autonomy.scavenger — event starvation self-healing."""

from __future__ import annotations

import json

import pytest

from backend.autonomy.scavenger import Scavenger, _MAX_SCAVENGE_EVENTS
from backend.tests.autonomy.conftest import seed_roster, seed_task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_events(db_conn, project_id: int, agent_id: str | None = None) -> list[dict]:
    """Fetch all agent_events for a project, optionally filtered by agent."""
    if agent_id:
        rows = db_conn.execute(
            "SELECT * FROM agent_events WHERE project_id = ? AND agent_id = ?",
            (project_id, agent_id),
        ).fetchall()
    else:
        rows = db_conn.execute(
            "SELECT * FROM agent_events WHERE project_id = ?",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _insert_event(
    db_conn, agent_id: str, project_id: int, event_type: str, task_id: int,
    status: str = "pending",
):
    """Insert an agent_event row for dedup testing."""
    payload = json.dumps({"task_id": task_id, "source_reason": "test"})
    db_conn.execute(
        """INSERT INTO agent_events
               (agent_id, project_id, event_type, source, priority, status, payload_json)
           VALUES (?, ?, ?, 'test', 50, ?, ?)""",
        (agent_id, project_id, event_type, status, payload),
    )
    db_conn.commit()


def _add_dependency(db_conn, task_id: int, depends_on: int, dep_type: str = "blocks"):
    """Insert a task_dependencies row."""
    db_conn.execute(
        """INSERT INTO task_dependencies (task_id, depends_on_task_id, dependency_type)
           VALUES (?, ?, ?)""",
        (task_id, depends_on, dep_type),
    )
    db_conn.commit()


def _insert_agent_run(
    db_conn, project_id: int, task_id: int, agent_id: str, role: str,
    status: str = "running",
):
    """Insert an agent_runs row."""
    db_conn.execute(
        """INSERT INTO agent_runs
               (project_id, agent_run_id, agent_id, task_id, role, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (project_id, f"run-{task_id}-{agent_id}", agent_id, task_id, role, status),
    )
    db_conn.commit()


# ===========================================================================
# 1. Developer: finds pending tasks without events → creates task_available
# ===========================================================================


class TestDeveloperScavenger:
    def test_creates_events_for_pending_code_tasks(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        t1 = seed_task(db_conn, pid, title="Code task", task_type="code", status="pending")
        t2 = seed_task(db_conn, pid, title="Bug fix", task_type="bug_fix", status="backlog")

        created = Scavenger(agent_id, pid, "developer").scavenge()

        assert created == 2
        events = _get_events(db_conn, pid, agent_id)
        assert len(events) == 2
        types = {e["event_type"] for e in events}
        assert types == {"task_available"}
        assert all(e["source"] == "scavenger" for e in events)

    def test_no_duplicates_if_event_exists(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        t1 = seed_task(db_conn, pid, title="Code task", task_type="code", status="pending")
        # Pre-existing pending event
        _insert_event(db_conn, agent_id, pid, "task_available", t1)

        created = Scavenger(agent_id, pid, "developer").scavenge()

        assert created == 0
        events = _get_events(db_conn, pid, agent_id)
        assert len(events) == 1  # only the pre-existing one

    def test_skips_blocked_dependencies(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        blocker = seed_task(db_conn, pid, title="Blocker", task_type="code", status="in_progress")
        blocked = seed_task(db_conn, pid, title="Blocked", task_type="code", status="pending")
        _add_dependency(db_conn, blocked, blocker)

        created = Scavenger(agent_id, pid, "developer").scavenge()

        assert created == 0

    def test_unblocked_when_dependency_done(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        blocker = seed_task(db_conn, pid, title="Blocker", task_type="code", status="done")
        blocked = seed_task(db_conn, pid, title="Blocked", task_type="code", status="pending")
        _add_dependency(db_conn, blocked, blocker)

        created = Scavenger(agent_id, pid, "developer").scavenge()

        assert created == 1

    def test_finds_rejected_tasks_assigned_to_agent(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        t1 = seed_task(
            db_conn, pid, title="Rejected task", task_type="code",
            status="rejected", assigned_to=agent_id,
        )

        created = Scavenger(agent_id, pid, "developer").scavenge()

        assert created == 1
        events = _get_events(db_conn, pid, agent_id)
        assert events[0]["event_type"] == "task_rejected"

    def test_ignores_rejected_assigned_to_other(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        seed_task(
            db_conn, pid, title="Rejected task", task_type="code",
            status="rejected", assigned_to="other_agent",
        )

        created = Scavenger(agent_id, pid, "developer").scavenge()
        assert created == 0


# ===========================================================================
# 2. Researcher: only finds research tasks
# ===========================================================================


class TestResearcherScavenger:
    def test_finds_research_tasks_only(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"researcher_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "researcher")])

        seed_task(db_conn, pid, title="Research task", task_type="research", status="pending")
        seed_task(db_conn, pid, title="Code task", task_type="code", status="pending")

        created = Scavenger(agent_id, pid, "researcher").scavenge()

        assert created == 1
        events = _get_events(db_conn, pid, agent_id)
        assert events[0]["event_type"] == "task_available"

    def test_finds_rejected_research(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"researcher_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "researcher")])

        seed_task(
            db_conn, pid, title="Rejected research", task_type="research",
            status="rejected", assigned_to=agent_id,
        )

        created = Scavenger(agent_id, pid, "researcher").scavenge()
        assert created == 1
        events = _get_events(db_conn, pid, agent_id)
        assert events[0]["event_type"] == "task_rejected"


# ===========================================================================
# 3. Code reviewer: finds review_ready non-research tasks
# ===========================================================================


class TestCodeReviewerScavenger:
    def test_finds_review_ready_tasks(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"code_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        seed_task(db_conn, pid, title="Review code", task_type="code", status="review_ready")

        created = Scavenger(agent_id, pid, "code_reviewer").scavenge()

        assert created == 1
        events = _get_events(db_conn, pid, agent_id)
        assert events[0]["event_type"] == "review_ready"

    def test_ignores_research_tasks(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"code_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        seed_task(db_conn, pid, title="Research review", task_type="research", status="review_ready")

        created = Scavenger(agent_id, pid, "code_reviewer").scavenge()
        assert created == 0

    def test_skips_if_agent_run_running(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"code_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        t1 = seed_task(db_conn, pid, title="Review code", task_type="code", status="review_ready")
        _insert_agent_run(db_conn, pid, t1, agent_id, "code_reviewer", status="running")

        created = Scavenger(agent_id, pid, "code_reviewer").scavenge()
        assert created == 0


# ===========================================================================
# 4. Research reviewer: finds review_ready research tasks
# ===========================================================================


class TestResearchReviewerScavenger:
    def test_finds_research_review_ready(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"research_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "research_reviewer")])

        seed_task(db_conn, pid, title="Research review", task_type="research", status="review_ready")

        created = Scavenger(agent_id, pid, "research_reviewer").scavenge()

        assert created == 1
        events = _get_events(db_conn, pid, agent_id)
        assert events[0]["event_type"] == "review_ready"

    def test_ignores_code_tasks(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"research_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "research_reviewer")])

        seed_task(db_conn, pid, title="Code review", task_type="code", status="review_ready")

        created = Scavenger(agent_id, pid, "research_reviewer").scavenge()
        assert created == 0


# ===========================================================================
# 5. Team lead: detects stagnation (2+ tasks stuck >30min)
# ===========================================================================


class TestTeamLeadScavenger:
    def test_detects_stagnation(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"team_lead_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "team_lead")])

        # Create tasks that appear old (use raw SQL to backdate created_at)
        for i in range(3):
            tid = seed_task(
                db_conn, pid, title=f"Stuck task {i}", task_type="code",
                status="in_progress", assigned_to=f"dev_{i}",
            )
            db_conn.execute(
                "UPDATE tasks SET created_at = datetime('now', '-2 hours') WHERE id = ?",
                (tid,),
            )
        db_conn.commit()

        created = Scavenger(agent_id, pid, "team_lead").scavenge()

        assert created == 3
        events = _get_events(db_conn, pid, agent_id)
        assert all(e["event_type"] == "stagnation_detected" for e in events)

    def test_no_stagnation_with_single_task(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"team_lead_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "team_lead")])

        tid = seed_task(
            db_conn, pid, title="Stuck alone", task_type="code",
            status="in_progress", assigned_to="dev_1",
        )
        db_conn.execute(
            "UPDATE tasks SET created_at = datetime('now', '-2 hours') WHERE id = ?",
            (tid,),
        )
        db_conn.commit()

        created = Scavenger(agent_id, pid, "team_lead").scavenge()
        assert created == 0

    def test_no_stagnation_if_health_check_active(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"team_lead_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "team_lead")])

        for i in range(2):
            tid = seed_task(
                db_conn, pid, title=f"Stuck {i}", task_type="code",
                status="in_progress", assigned_to=f"dev_{i}",
            )
            db_conn.execute(
                "UPDATE tasks SET created_at = datetime('now', '-2 hours') WHERE id = ?",
                (tid,),
            )
            # Insert active health_check event for each task
            _insert_event(db_conn, agent_id, pid, "health_check", tid)
        db_conn.commit()

        created = Scavenger(agent_id, pid, "team_lead").scavenge()
        assert created == 0


# ===========================================================================
# 6. Project not executing → returns 0
# ===========================================================================


class TestProjectStateChecks:
    def test_non_executing_project_returns_zero(self, db_conn, new_project):
        pid = new_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])
        seed_task(db_conn, pid, title="Task", task_type="code", status="pending")

        created = Scavenger(agent_id, pid, "developer").scavenge()
        assert created == 0


# ===========================================================================
# 7. Respects _MAX_SCAVENGE_EVENTS limit
# ===========================================================================


class TestScavengeLimit:
    def test_respects_max_events_cap(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])

        # Create more tasks than the limit
        for i in range(_MAX_SCAVENGE_EVENTS + 5):
            seed_task(db_conn, pid, title=f"Task {i}", task_type="code", status="pending")

        created = Scavenger(agent_id, pid, "developer").scavenge()

        assert created == _MAX_SCAVENGE_EVENTS
        events = _get_events(db_conn, pid, agent_id)
        assert len(events) == _MAX_SCAVENGE_EVENTS


# ===========================================================================
# 8. Source tracking
# ===========================================================================


# ===========================================================================
# 8. Reviewer claim: scavenger skips tasks with reviewer already set
# ===========================================================================


class TestReviewerClaimSkip:
    def test_code_reviewer_skips_claimed_tasks(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"code_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        t1 = seed_task(db_conn, pid, title="Claimed review", task_type="code", status="review_ready")
        # Simulate another reviewer already claimed this task
        db_conn.execute("UPDATE tasks SET reviewer = 'other_reviewer' WHERE id = ?", (t1,))
        db_conn.commit()

        created = Scavenger(agent_id, pid, "code_reviewer").scavenge()
        assert created == 0

    def test_research_reviewer_skips_claimed_tasks(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"research_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "research_reviewer")])

        t1 = seed_task(db_conn, pid, title="Claimed research review", task_type="research", status="review_ready")
        db_conn.execute("UPDATE tasks SET reviewer = 'other_reviewer' WHERE id = ?", (t1,))
        db_conn.commit()

        created = Scavenger(agent_id, pid, "research_reviewer").scavenge()
        assert created == 0

    def test_code_reviewer_finds_unclaimed_tasks(self, db_conn, executing_project):
        """Unclaimed review_ready tasks should still be found."""
        pid = executing_project
        agent_id = f"code_reviewer_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "code_reviewer")])

        seed_task(db_conn, pid, title="Unclaimed review", task_type="code", status="review_ready")

        created = Scavenger(agent_id, pid, "code_reviewer").scavenge()
        assert created == 1


# ===========================================================================
# 9. Source tracking
# ===========================================================================


class TestSourceTracking:
    def test_events_have_scavenger_source(self, db_conn, executing_project):
        pid = executing_project
        agent_id = f"developer_1_p{pid}"
        seed_roster(db_conn, pid, [(agent_id, "developer")])
        seed_task(db_conn, pid, title="Task", task_type="code", status="pending")

        Scavenger(agent_id, pid, "developer").scavenge()

        events = _get_events(db_conn, pid, agent_id)
        assert len(events) == 1
        assert events[0]["source"] == "scavenger"
        payload = json.loads(events[0]["payload_json"])
        assert payload["source_reason"] == "scavenger"
