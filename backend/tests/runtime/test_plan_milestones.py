"""Native milestones remain explicit plan content, with scoped grouping and atomic owner acceptance."""

from copy import deepcopy

import pytest

from backend.tests.runtime.test_project_planning import draft, planning_state


def milestone_draft():
    """Extend the historical draft with one bounded delivery group and an explicit proposed date."""
    result = draft()
    result["milestones"] = [{"key":"evidence", "epic_key":"work", "title":"Evidence ready",
        "description":"A cited explanation before implementation.", "due_date":"2027-01-15"}]
    result["tasks"][0]["milestone_key"] = "evidence"
    return result


def test_optional_milestones_preserve_old_drafts_and_reject_invalid_grouping():
    """Keep historical proposal shapes exact while refusing foreign graph keys, invented dates and authority fields."""
    from backend.planning.models import validate_plan

    sources = {"owner_request":"Investigate the issue and propose a plan."}
    old = draft()
    assert validate_plan(old, sources) == old
    assert "milestones" not in old and "milestone_key" not in old["tasks"][0]
    assert validate_plan(milestone_draft(), sources)["milestones"][0]["due_date"] == "2027-01-15"
    for case in ("missing_epic", "missing_milestone", "other_epic", "duplicate", "invalid_date", "authority"):
        value = deepcopy(milestone_draft())
        if case == "missing_epic": value["milestones"][0]["epic_key"] = "unknown"
        elif case == "missing_milestone": value["tasks"][0]["milestone_key"] = "unknown"
        elif case == "other_epic":
            value["epics"].append({"key":"other", "title":"Other", "description":"Separate scope."})
            value["milestones"][0]["epic_key"] = "other"
        elif case == "duplicate": value["milestones"].append(deepcopy(value["milestones"][0]))
        elif case == "invalid_date": value["milestones"][0]["due_date"] = "2027-02-30"
        else: value["milestones"][0]["approved"] = True
        with pytest.raises(ValueError):
            validate_plan(value, sources)


def test_owner_acceptance_materializes_milestones_atomically_once(service_setup):
    """Create the hierarchy once or roll it back; separately authorized delivery preserves the exact proposed grouping."""
    import sqlite3

    from backend.planning.store import ProjectPlans

    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    before = s.c.conn.execute("SELECT count(*) FROM tasks").fetchone()[0]
    proposal = plans.propose(lease, "milestone-proposal", milestone_draft())
    assert s.c.conn.execute("SELECT count(*) FROM milestones").fetchone()[0] == 0
    for peer in peers.ids.values(): peers.registry.close(peer)
    s.c.store.finish(lease, native_status="completed", summary="Proposed task grouping for owner review.")
    command = {"operation_key":"accept-milestones", "proposal_sha256":proposal["proposal_sha256"], "context_version":lease.context_version}
    s.c.conn.execute("CREATE TRIGGER reject_plan_acceptance BEFORE INSERT ON runtime_project_plan_acceptances BEGIN SELECT RAISE(ABORT,'injected plan receipt failure'); END")
    s.c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected plan receipt"):
        plans.accept(101, run.run_id, **command)
    assert s.c.conn.execute("SELECT count(*) FROM epics").fetchone()[0] == 0
    assert s.c.conn.execute("SELECT count(*) FROM milestones").fetchone()[0] == 0
    assert s.c.conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == before
    s.c.conn.execute("DROP TRIGGER reject_plan_acceptance")
    s.c.conn.commit()
    result = plans.accept(101, run.run_id, **command)
    assert plans.accept(101, run.run_id, **command) == result
    mid = result["milestones"]["evidence"]
    row = s.c.conn.execute("SELECT * FROM milestones WHERE id=?", (mid,)).fetchone()
    assert row["project_id"] == 101 and row["epic_id"] == result["epics"]["work"]
    assert row["due_date"] == "2027-01-15" and row["status"] == "open"
    task = s.c.conn.execute("SELECT milestone_id,status FROM tasks WHERE id=?", (result["tasks"]["learn"],)).fetchone()
    assert task["milestone_id"] == mid and task["status"] == "pending"
    assert s.c.conn.execute("SELECT milestone_id FROM tasks WHERE id=?", (result["tasks"]["change"],)).fetchone()[0] is None
    assert result["execution_started"] is False
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []

    from backend.tests.runtime.test_plan_execution import authorize

    executions, execution = authorize(s, run)
    executions.prepare(execution["execution_id"], result["tasks"]["learn"])
    handoff = executions.state(101, run.run_id)["execution"]["deliveries"][0]["handoff"]
    assert handoff["plan_context"]["accepted_plan"] == milestone_draft()


async def test_planning_wire_retains_milestone_grouping_without_creating_rows(service_setup):
    """The native host schema carries exact local milestone references; proposing does not accept or execute them."""
    import asyncio
    import json

    from backend.planning.store import ProjectPlans
    from backend.planning.tools import PlanningTools

    s, run, lease, _peers = planning_state(service_setup)
    async def settled(function, *args, **kwargs):
        """Use the actual storage operation through the same awaited host worker seam."""
        return await asyncio.to_thread(function, *args, **kwargs)

    tools = PlanningTools(ProjectPlans(s.c.store), lease, active=lambda: True, settled=settled)
    reply = await tools.call({"tool":"researcher_plan_propose", "arguments":{"operation_key":"wire-milestones", "plan":milestone_draft()}})
    assert reply["success"] is True, reply
    receipt = json.loads(reply["contentItems"][0]["text"])
    state = ProjectPlans(s.c.store).state(101, run.run_id)
    assert state["proposal"]["proposal_sha256"] == receipt["proposal_sha256"]
    assert state["proposal"]["draft"] == milestone_draft()
    assert s.c.conn.execute("SELECT count(*) FROM milestones").fetchone()[0] == 0
    await tools.aclose()
