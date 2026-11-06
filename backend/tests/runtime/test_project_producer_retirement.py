"""Project policy prevents old producers before admission while native planning retains attributed historical context without replaying authority."""

import importlib
import json

import pytest


@pytest.mark.parametrize("module_name,class_name", [("main_project_flow","MainProjectFlow"),("brainstorming_flow","BrainstormingFlow"),("ticket_creation_flow","TicketCreationFlow")])
def test_old_project_kickoff_is_a_scoped_readonly_policy_entry(coordination, monkeypatch, module_name, class_name):
    """Every direct old project flow must hand off without agents, inference, resets, task creation or inferred completion."""
    c = coordination
    module = importlib.import_module("backend.flows." + module_name)

    def forbidden(*_args, **_kwargs):
        """Expose any accidental execution of the old model or agent factory port."""
        pytest.fail("Legacy project work must not start")

    monkeypatch.setattr(module,"get_engine",forbidden,raising=False)
    monkeypatch.setattr(module,"get_agent_by_role",forbidden,raising=False)
    tasks = [tuple(row) for row in c.conn.execute("SELECT * FROM tasks ORDER BY id")]
    project = tuple(c.conn.execute("SELECT * FROM projects WHERE id=101").fetchone())
    flow = getattr(module,class_name)()
    hint = flow.kickoff({"project_id":101,"plan":"caller-supplied approval is not authority"})
    assert hint["delivery"] == "native_owner_handoff" and hint["scope"] == "project"
    assert hint["native_admission_run_id"] is None
    assert hint["event_authorizes_work"] is False
    assert hint["legacy_execution_closure"] == "not_assessed"
    assert [tuple(row) for row in c.conn.execute("SELECT * FROM tasks ORDER BY id")] == tasks
    assert tuple(c.conn.execute("SELECT * FROM projects WHERE id=101").fetchone()) == project
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0
    with pytest.raises(ValueError):
        flow.kickoff({"project_id":999999})


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


def test_direct_listener_start_returns_owner_entry_before_thread_creation(coordination, monkeypatch):
    """Calling a concrete old listener directly cannot bypass the retired manager's start policy."""
    from backend.flows.event_listeners import NewTaskCreatedListener

    listener = NewTaskCreatedListener(101)

    def forbidden(*_args, **_kwargs):
        """Reject accidental old poller construction without leaking a test worker."""
        pytest.fail("Legacy listener thread must not start")

    monkeypatch.setattr("backend.flows.listener_base.threading.Thread", forbidden)
    hint = listener.start()
    assert hint["native_admission_run_id"] is None
    assert not listener.is_running


@pytest.mark.parametrize("handler", ["MessageHandler", "HealthCheckHandler", "ProgressEvalHandler"])
def test_project_handlers_are_policy_hints_before_first_native_admission(coordination, handler):
    """Messages, stagnation and all-done labels never activate a project model or accept the project."""
    from backend.autonomy import handlers

    c = coordination
    before = tuple(c.conn.execute("SELECT * FROM projects WHERE id=101").fetchone())
    result = getattr(handlers, handler)().execute({"id":1,"project_id":101,"agent_id":"old-lead","event_type":"all_tasks_done","payload_json":"{}"})
    assert result["native_admission_run_id"] is None and result["event_authorizes_work"] is False
    assert tuple(c.conn.execute("SELECT * FROM projects WHERE id=101").fetchone()) == before


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
    assert name == 'researcher_plan_propose'
    validate_plan(body['plan'],sources)
    assert any(item['source'].endswith(':requirements') for item in body['plan']['basis']) is historic


def test_legacy_crew_helpers_cannot_construct_or_retry_models(coordination):
    """Retired auxiliary Crew entry points reject before touching an agent or invoking the supplied kickoff."""
    from types import SimpleNamespace

    from backend.flows.helpers.reporting import build_crew, kickoff_with_retry
    from backend.runtime.lifecycle import NativeOwnerRequired

    with pytest.raises(NativeOwnerRequired):
        build_crew(SimpleNamespace(project_id=101), ('old request','old output'))
    with pytest.raises(NativeOwnerRequired):
        kickoff_with_retry(SimpleNamespace())
