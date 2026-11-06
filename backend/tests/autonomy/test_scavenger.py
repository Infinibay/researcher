"""An idle legacy scheduler cannot reconstruct task authority after the native task cutover."""

import pytest

from backend.autonomy.scavenger import Scavenger
from backend.runtime.task_profiles import NATIVE_TASK_TYPES
from backend.tests.autonomy.conftest import seed_roster, seed_task


@pytest.mark.parametrize("role", ["developer", "researcher", "code_reviewer", "research_reviewer", "team_lead", "unknown-role"])
def test_idle_recovery_preserves_every_task_category_before_first_admission(db_conn, executing_project, role):
    """Missing events and old assignments are not permission to dispatch, complete or clean up work."""
    project = executing_project
    agent = "historic-" + role
    seed_roster(db_conn, project, [(agent, role)])
    for task_type in NATIVE_TASK_TYPES:
        seed_task(db_conn, project, title=task_type, task_type=task_type, status="pending")
    before = [tuple(row) for row in db_conn.execute("SELECT * FROM tasks ORDER BY id")]
    scavenger = Scavenger(agent, project, role)
    assert scavenger.scavenge() == scavenger.scavenge() == 0
    assert [tuple(row) for row in db_conn.execute("SELECT * FROM tasks ORDER BY id")] == before
    assert db_conn.execute("SELECT count(*) FROM agent_events").fetchone()[0] == 0
    assert db_conn.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_runs'").fetchone() is None
