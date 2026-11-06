"""Migrated task categories enter one native owner; old flow results or labels cannot claim, complete, clean up or publish their work."""

import importlib
import sqlite3
from dataclasses import replace

import pytest

TASK_KINDS = [
    ("code", "development"), ("bug_fix", "development"), ("test", "development"),
    ("design", "development"), ("integrate", "development"), ("documentation", "development"),
    ("experimentation", "development"), ("optimization", "development"),
    ("review", "research"), ("plan", "research"),
]


@pytest.mark.parametrize("task_type,kind", TASK_KINDS)
def test_every_old_development_category_has_a_native_profile_and_no_preadmission_legacy_claim(service_setup, task_type, kind):
    """Dropping a generic-flow category would strand old tasks or accidentally grant an auditor writable development permissions."""
    from backend.runtime.task_profiles import NATIVE_TASK_TYPES
    from backend.runtime.workspaces import WorkspaceRegistry

    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type=?,status='pending' WHERE id=1001", (task_type,))
    s.c.conn.commit()
    assert task_type in NATIVE_TASK_TYPES
    with pytest.raises(sqlite3.IntegrityError, match="native|Native|owner"):
        s.c.conn.execute("UPDATE tasks SET status='in_progress',assigned_to='old-developer' WHERE id=1001")
    s.c.conn.rollback()
    version = s.c.store.context_snapshot(101,1001)["context_version"]
    binding = WorkspaceRegistry(s.c.database,s.root).bind(101,11)
    run = s.c.store.admit(replace(s.c.spec,context_version=version),binding=binding)
    assert run.execution_kind == kind and run.status == "queued" and run.attempt_id is None
    assert s.c.conn.execute("SELECT assigned_to FROM tasks WHERE id=1001").fetchone()[0] is None


@pytest.mark.parametrize("module_name,class_name", [("development_flow","DevelopmentFlow"),("code_review_flow","CodeReviewFlow")])
def test_public_old_kickoff_preserves_scope_and_returns_owner_hint_without_work(service_setup, monkeypatch, module_name, class_name):
    """A compatibility entry must preserve old state/files and hand off before old agent creation, CI, inference or auto-merge."""
    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type='code',status='review_ready',branch_name='old-branch',assigned_to='old-author',reviewer='old-reviewer' WHERE id=1001")
    s.c.conn.commit()
    before = dict(s.c.conn.execute("SELECT * FROM tasks WHERE id=1001").fetchone())
    original = s.workspace / "old-code.txt"
    original.write_text("Preserve this partial result.")
    module = importlib.import_module("backend.flows."+module_name)

    def forbidden(*_args, **_kwargs):
        """Refuse the old billable provider/agent port if the obsolete loop is entered."""
        raise AssertionError("Old inference or agent construction must not run")

    monkeypatch.setattr(module,"get_engine",forbidden,raising=False)
    monkeypatch.setattr(module,"get_available_agent_by_role",forbidden,raising=False)
    flow = getattr(module,class_name)()
    result = flow.kickoff(inputs={"project_id":101,"task_id":1001,"branch_name":"caller-guess","developer_id":"caller-guess"})
    assert result["delivery"] == "native_owner_handoff" and result["task_id"] == 1001
    assert result["event_authorizes_work"] is False and result["inference_started_by_handoff"] is False
    assert dict(s.c.conn.execute("SELECT * FROM tasks WHERE id=1001").fetchone()) == before
    assert original.read_text() == "Preserve this partial result."
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0
    with pytest.raises(ValueError):
        flow.kickoff(inputs={"project_id":202,"task_id":1001})


@pytest.mark.parametrize("task_type", ["code","bug_fix","review","plan","documentation"])
def test_legacy_done_labels_cannot_replace_native_owner_acceptance(coordination, task_type):
    """Before first admission, an old approval string must not mark newly migrated work complete."""
    c = coordination
    c.conn.execute("UPDATE tasks SET type=?,status='review_ready' WHERE id=1001",(task_type,))
    c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError,match="native|Native|owner"):
        c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    c.conn.rollback()
    assert c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] == "review_ready"


def test_main_task_dispatch_hands_off_existing_work_without_reset_or_project_completion(service_setup):
    """Old in-progress assignments and a completed task list are historical data, not restart or project-completion authority."""
    from backend.flows.main_project_flow import MainProjectFlow

    s = service_setup
    s.c.conn.execute("UPDATE tasks SET type='code',assigned_to='old-author',branch_name='old-branch' WHERE id=1001")
    s.c.conn.commit()
    flow = MainProjectFlow()
    flow.state.project_id = 101
    before = dict(s.c.conn.execute("SELECT * FROM tasks WHERE id=1001").fetchone())
    assert flow._wait_for_autonomous_completion() == "native_owner_required"
    assert flow._launch_pending_tasks() == "native_owner_required"
    assert dict(s.c.conn.execute("SELECT * FROM tasks WHERE id=1001").fetchone()) == before
    assert s.c.conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 0
    assert s.c.conn.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0] == 0


def test_idle_scavenger_never_deletes_preserved_old_work_before_first_native_admission(service_setup, monkeypatch):
    """An old heartbeat must not garbage-collect the exact partial files the owner still needs to import."""
    from backend.autonomy.scavenger import Scavenger
    from backend.git.worktree_manager import WorktreeManager

    s = service_setup
    s.c.conn.execute("UPDATE projects SET status='executing' WHERE id=101")
    s.c.conn.commit()
    old = s.workspace / "old-result.txt"
    old.write_text("Unimported work.")

    def destructive_cleanup(_manager, _project_id):
        """Represent the old external Git cleanup port with a real observable effect on synthetic data."""
        old.unlink()
        return 1

    monkeypatch.setattr(WorktreeManager,"cleanup_stale_worktrees",destructive_cleanup)
    Scavenger("old-agent",101,"unknown-role").scavenge()
    assert old.read_text() == "Unimported work."


@pytest.mark.parametrize("task_type,_kind", TASK_KINDS)
def test_admission_alone_cannot_complete_any_migrated_task(coordination, task_type, _kind):
    """After admission, the original exact acceptance guard still rejects an old done label for every profile."""
    c = coordination
    c.conn.execute("UPDATE tasks SET type=?,status='review_ready' WHERE id=1001", (task_type,))
    c.conn.commit()
    version = c.store.context_snapshot(101, 1001)["context_version"]
    c.store.admit(replace(c.spec, context_version=version))
    with pytest.raises(sqlite3.IntegrityError, match="acceptance"):
        c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    c.conn.rollback()


def test_task_cutover_migration_is_atomic_repeatable_and_preserves_history(request, monkeypatch):
    """A failed schema54 install leaves schema53 and old work intact; retry adds guards without minting native proof."""
    from backend.db import migrations
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource

    def skip_cutover(conn, path):
        """Prepare the actual prior schema without modifying historical migration files."""
        if path.name != "native_task_cutover_schema.sql":
            apply(conn, path)

    monkeypatch.setattr(migrations, "apply_sql_resource", skip_cutover)
    c = request.getfixturevalue("coordination")
    assert c.conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 53
    c.conn.execute("UPDATE tasks SET type='code',status='done',assigned_to='old-author',branch_name='old-branch' WHERE id=1002")
    c.conn.commit()
    original = dict(c.conn.execute("SELECT * FROM tasks WHERE id=1002").fetchone())
    c.conn.execute("CREATE TRIGGER reject54 BEFORE INSERT ON schema_migrations WHEN new.version=54 BEGIN SELECT RAISE(ABORT,'injected cutover failure'); END")
    c.conn.commit()
    monkeypatch.setattr(migrations, "apply_sql_resource", apply)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        ensure_migrations(c.database)
    assert c.conn.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE 'task_cutover_%'").fetchone()[0] == 0
    assert c.conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 53
    c.conn.execute("DROP TRIGGER reject54")
    c.conn.commit()
    ensure_migrations(c.database)
    ensure_migrations(c.database)
    assert c.conn.execute("SELECT count(*) FROM schema_migrations WHERE version=54").fetchone()[0] == 1
    assert dict(c.conn.execute("SELECT * FROM tasks WHERE id=1002").fetchone()) == original
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0
    assert c.conn.execute("SELECT count(*) FROM runtime_code_acceptances").fetchone()[0] == 0


@pytest.mark.parametrize("task_type", [kind for kind, _ in TASK_KINDS if kind != "plan"])
def test_planner_catalog_and_domain_accept_each_nonrecursive_task_profile(task_type):
    """Typed tool arguments and graph policy agree on repository outcomes and read-only audit children."""
    from backend.planning.models import validate_plan
    from backend.planning.tools import TaskProposal
    from backend.tests.runtime.test_project_planning import draft

    packet = draft()
    packet["tasks"][1]["type"] = task_type
    assert TaskProposal.model_validate(packet["tasks"][1]).type == task_type
    validate_plan(packet, {"owner_request": "Investigate the issue"})
