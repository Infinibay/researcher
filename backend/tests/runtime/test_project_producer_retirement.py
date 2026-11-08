"""Project policy prevents old producers before admission while native planning retains attributed historical context without replaying authority."""

import importlib
import json

import pytest




def test_legacy_project_entry_is_policy_not_fabricated_native_history(coordination):
    """The policy applies before admission while the evidence query still reports no native history."""
    from backend.runtime.legacy_handoff import (
        legacy_project_handoff,
        native_project_handoff,
    )
    from backend.runtime.lifecycle import NativeOwnerRequired, require_legacy_project

    c = coordination
    assert native_project_handoff(c.conn,101) is None
    hint = legacy_project_handoff(101)
    assert hint["native_admission_run_id"] is None
    with pytest.raises(NativeOwnerRequired):
        require_legacy_project(c.conn,101)
    run = c.store.admit(c.spec)
    assert legacy_project_handoff(101)["native_admission_run_id"] == run.run_id
    assert native_project_handoff(c.conn,202) is None


def test_flow_manager_does_not_clear_old_events_or_activate_before_admission(coordination, monkeypatch):
    """An old start preserves the data needed for native migration and does not construct a replacement legacy owner."""
    from backend.api.flow_manager import FlowManager

    c = coordination
    c.conn.execute("INSERT INTO agent_events(project_id,agent_id,event_type,source,status,payload_json) VALUES(101,'old-owner','user_message_received','old','pending','{}')")
    c.conn.commit()
    before = [tuple(row) for row in c.conn.execute("SELECT * FROM agent_events")]
    manager = FlowManager()
    hint = manager.start_project_flow(101)
    assert hint["native_admission_run_id"] is None
    assert not manager.is_project_running(101)
    assert not manager._threads and not manager._flows and not manager._listeners and not manager._autonomy
    assert [tuple(row) for row in c.conn.execute("SELECT * FROM agent_events")] == before


def test_native_plan_freezes_legacy_business_material_and_actual_task_inventory(service_setup):
    """Requirements/ideas and old status labels become original attributed data, never new instruction, task duplication or acceptance."""
    from backend.tests.runtime.test_project_planning import planning_state

    s = service_setup
    original = {"project_id":101,"requirements":"Inspect137units","plan":"First explain the count","selected_ideas":[{"text":"Compare two implementations"}],"thread_id":"old-untrusted-session","approved":True}
    s.c.conn.execute("INSERT INTO flow_snapshots(project_id,flow_name,current_step,state_json) VALUES(101,'main_project_flow','planning',?)",(json.dumps(original),))
    s.c.conn.execute("INSERT INTO flow_snapshots(project_id,flow_name,current_step,state_json) VALUES(202,'main_project_flow','planning',?)",(json.dumps({"requirements":"Foreign secret"}),))
    s.c.conn.commit()
    s, run, lease, peers = planning_state(s)
    from backend.planning.store import ProjectPlans

    plans = ProjectPlans(s.c.store)
    material = plans.material(lease,max_chars=24000)
    packet = json.loads(material["content"])
    history = packet["project_history"]
    key = next(key for key in packet["sources"] if key.endswith(":requirements"))
    assert packet["sources"][key] == "Inspect137units"
    assert packet["source_origins"][key] == "legacy_snapshot"
    assert history["task_inventory"]["total"] == 1
    assert history["task_inventory"]["complete"] is True
    assert "old-untrusted-session" not in material["content"] and "Foreign secret" not in material["content"]
    frozen = material["snapshot_sha256"]
    s.c.conn.execute("DELETE FROM flow_snapshots WHERE project_id=101")
    s.c.conn.execute("UPDATE tasks SET title='Changed later' WHERE id=1002")
    s.c.conn.commit()
    assert plans.material(lease,max_chars=24000)["snapshot_sha256"] == frozen
    assert plans.material(lease,max_chars=24000)["content"] == material["content"]
    assert s.c.conn.execute("SELECT count(*) FROM runtime_project_plan_acceptances").fetchone()[0] == 0






@pytest.mark.parametrize("material,reason", [('not JSON','invalid_json'), (json.dumps({'requirements':'x'*150000}),'excluded_size_limit'), (json.dumps({'requirements':'x'*70000,'plan':'Keep this smaller plan'}),'field_limit'), (json.dumps({'requirements':'\ud800','plan':'Keep this smaller plan'}),'invalid_utf8')])
def test_unreadable_history_is_explicit_and_does_not_destroy_other_material(service_setup, material, reason):
    """Invalid, oversized and undecodable old content remains preserved; a bounded native plan exposes uncertainty rather than truncation or replay."""
    from backend.planning.store import ProjectPlans
    from backend.tests.runtime.test_project_planning import planning_state

    s = service_setup
    s.c.conn.execute("INSERT INTO flow_snapshots(project_id,flow_name,current_step,state_json) VALUES(101,'main_project_flow','planning',?)", (material,))
    s.c.conn.commit()
    s, run, lease, peers = planning_state(s)
    packet = json.loads(ProjectPlans(s.c.store).material(lease,max_chars=24000)["content"])
    assert packet["project_history"]["limits"]
    if reason in ('invalid_json','excluded_size_limit'):
        assert packet["project_history"]["legacy_snapshot"]["state"] == reason
    else:
        assert any(key.endswith(':plan') and value=='Keep this smaller plan' for key,value in packet["sources"].items())
        assert not any(key.endswith(':requirements') for key in packet["sources"])
    assert s.c.conn.execute("SELECT state_json FROM flow_snapshots WHERE project_id=101").fetchone()[0] == material


def test_large_task_inventory_discloses_unexamined_work(service_setup):
    """The planner sees an explicit incomplete inventory instead of assuming all existing work was examined."""
    from backend.planning.store import ProjectPlans
    from backend.tests.runtime.test_project_planning import planning_state

    s = service_setup
    s.c.conn.executemany("INSERT INTO tasks(id,project_id,type,title,status) VALUES(?,101,'code','Existing work','pending')", [(20000+i,) for i in range(260)])
    s.c.conn.commit()
    s, run, lease, peers = planning_state(s)
    plans = ProjectPlans(s.c.store)
    # Read the actual complete frozen context through its existing bounded windows.
    chunks = []
    offset = 0
    while True:
        window = plans.material(lease,offset=offset,max_chars=24000)
        chunks.append(window["content"])
        if window["next_offset"] is None:
            break
        offset = window["next_offset"]
    packet = json.loads(''.join(chunks))
    inventory = packet["project_history"]["task_inventory"]
    assert inventory == {"total":261,"captured":256,"complete":False,"status_authority":"Observed labels are not proof of native acceptance or current execution."}
    assert len(json.loads(packet["sources"]["project_tasks"])) == 256
    assert packet["project_history"]["limits"]


@pytest.mark.parametrize("historic", [False, True])
def test_controlled_planner_fixture_cites_the_actual_supplied_history(historic):
    """Check the generation fixture's real proposal contract before spending a physical runtime trial."""
    import ast
    from pathlib import Path

    from backend.planning.models import validate_plan

    tree = ast.parse(Path(__file__).with_name('fake_owned_native.py').read_text())
    node = next(item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name=='next_planning_tool')
    sources = {"owner_request":"Investigate the issue"}
    if historic:
        sources['legacy_snapshot:1:requirements'] = 'Previously observed137units'
    calls = []
    namespace = {"steps":2,"plan_material":{"owner_request":sources['owner_request'],"sources":sources},"call":lambda name,body:calls.append((name,body))}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<controlled-planner>','exec'),namespace)
    namespace['next_planning_tool']()
    name, body = calls[0]
    assert name == 'researcher_plan_deliver'
    validate_plan(body['plan'],sources)
    assert any(item['source'].endswith(':requirements') for item in body['plan']['basis']) is historic


