"""Protect original native planning identities and unused-schema rollback without starting an actor."""

import sqlite3
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from backend.planning.owner_records import OwnerPlanningRecords
from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_migration_chain import logical_snapshot
from backend.tests.runtime.test_plan_milestones import milestone_draft
from backend.tests.runtime.test_project_planning import planning_state
from backend.tests.runtime.test_installation_backup import installation

__all__ = ["installation"]


@pytest.mark.parametrize("kind", ["group", "milestone", "task"])
def test_accepted_plan_groups_cannot_be_removed_before_child_execution(service_setup, kind):
    """Pending child tasks still belong to an accepted plan whose original grouping must remain recoverable."""
    from backend.planning.store import ProjectPlans

    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    proposal = plans.propose(lease, "original-grouping", milestone_draft())
    for peer in peers.ids.values():
        peers.registry.close(peer)
    s.c.store.finish(lease, native_status="completed", summary="Synthetic plan fixture; no native generation.")
    accepted = plans.accept(101, run.run_id, operation_key="accept-original-grouping",
        proposal_sha256=proposal["proposal_sha256"], context_version=lease.context_version)
    records = OwnerPlanningRecords(s.c.store)
    group, milestone = accepted["epics"]["work"], accepted["milestones"]["evidence"]
    before = [tuple(row) for row in s.c.conn.execute("SELECT id,epic_id,milestone_id,status FROM tasks ORDER BY id")]
    with pytest.raises(RunConflict, match="plan aceptado"):
        if kind == 'task':
            records.delete_task(next(iter(accepted['tasks'].values())))
        elif kind == 'group':
            records.delete_group(group)
        else:
            records.delete_milestone(milestone)
    assert s.c.conn.execute("SELECT 1 FROM epics WHERE id=?", (group,)).fetchone()
    assert s.c.conn.execute("SELECT 1 FROM milestones WHERE id=?", (milestone,)).fetchone()
    assert [tuple(row) for row in s.c.conn.execute("SELECT id,epic_id,milestone_id,status FROM tasks ORDER BY id")] == before


def test_unused_planning_schema_roundtrip_preserves_existing_owner_records(tmp_path):
    """An explicit unused inverse returns to the exact prior schema and can be upgraded again without changing data."""
    from backend.db.planning_commands_migration import restore_planning_commands_schema
    from backend.tools.base.db import ensure_migrations

    database = tmp_path / "roundtrip.db"
    ensure_migrations(str(database), target_version=68)
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(1,'Retained owner project')")
        conn.execute("INSERT INTO epics(id,project_id,title) VALUES(1,1,'Retained group')")
    before = logical_snapshot(database)
    ensure_migrations(str(database), target_version=69)
    with closing(sqlite3.connect(database)) as conn:
        restore_planning_commands_schema(conn)
    assert logical_snapshot(database) == before
    with closing(sqlite3.connect(database)) as conn:
        assert conn.execute("SELECT id,project_id,title FROM epics").fetchall() == [(1, 1, "Retained group")]
    ensure_migrations(str(database), target_version=69)


@pytest.mark.parametrize('schema_target', [69])
def test_used_planning_schema_inverse_refuses_to_discard_receipts(coordination, schema_target):
    """An original owner receipt must survive an attempted inverse; it cannot be silently reissued later."""
    from backend.db.planning_commands_migration import restore_planning_commands_schema

    records = OwnerPlanningRecords(coordination.store)
    group = records.create_group(project_id=101, title="Original group", operation_key="retained-request")
    with closing(sqlite3.connect(coordination.database)) as conn:
        with pytest.raises(RuntimeError, match="recorded requests"):
            restore_planning_commands_schema(conn)
        assert conn.execute("SELECT resource_id FROM owner_planning_commands").fetchone()[0] == group["id"]
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 69


@pytest.mark.parametrize('schema_target', [69])
def test_inverse_failure_restores_dropped_table_and_receipt_trigger(coordination, schema_target):
    """Failure after transactional DROP must roll back the infrastructure rather than leave a schema prefix gap."""
    from backend.db.planning_commands_migration import restore_planning_commands_schema

    with closing(sqlite3.connect(coordination.database)) as conn:
        def reject_version_removal(action, table, *args):
            """Deny the final history write after DROP to exercise a real SQLite transactional rollback."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_DELETE and table == "schema_migrations" else sqlite3.SQLITE_OK

        conn.set_authorizer(reject_version_removal)
        with pytest.raises(sqlite3.DatabaseError):
            restore_planning_commands_schema(conn)
        conn.set_authorizer(None)
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='owner_planning_commands'").fetchone()
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='owner_planning_command_immutable'").fetchone()
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 69


def test_concurrent_identical_owner_deliveries_share_one_resource(coordination):
    """Two actual SQLite writers must converge on the same original resource and immutable receipt."""
    records = OwnerPlanningRecords(coordination.store)
    start = Barrier(2)
    def create(_):
        """Release two original writer requests together, then let SQLite serialize their receipt transaction."""
        start.wait(timeout=5)
        return records.create_group(project_id=101, title="Concurrent", operation_key="same-delivery")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, range(2)))
    assert results[0] == results[1]
    assert coordination.conn.execute("SELECT count(*) FROM epics WHERE project_id=101").fetchone()[0] == 1
    assert coordination.conn.execute("SELECT count(*) FROM owner_planning_commands").fetchone()[0] == 1


@pytest.mark.parametrize("first", ["admission", "deletion"])
def test_group_removal_and_native_admission_preserve_current_context_in_either_order(coordination, first):
    """Admission protects the grouping; an earlier deletion versions the inputs and rejects the old request without launching an actor."""
    c = coordination
    records = OwnerPlanningRecords(c.store)
    group = records.create_group(project_id=101, title="Original context", operation_key="context-group")["id"]
    c.conn.execute("UPDATE tasks SET status='pending',epic_id=? WHERE id=1001", (group,))
    c.conn.commit()
    spec = replace(c.spec, context_version=c.store.context_snapshot(101, 1001)["context_version"])
    if first == "admission":
        c.store.admit(spec)
        with pytest.raises(RunConflict):
            records.delete_group(group)
        assert c.conn.execute("SELECT epic_id FROM tasks WHERE id=1001").fetchone()[0] == group
    else:
        records.delete_group(group)
        with pytest.raises(RunConflict):
            c.store.admit(spec)
        assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0
        assert c.conn.execute("SELECT epic_id FROM tasks WHERE id=1001").fetchone()[0] is None


def test_product_backup_restoration_keeps_exact_planning_receipts(installation, tmp_path):
    """The actual backup/restore format must retain original identities without re-enrolling execution or recreating metadata."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.sqlite_runs import SQLiteRunStore

    original, _ = installation
    records = OwnerPlanningRecords(SQLiteRunStore(original / "source.db"))
    group_body = {"project_id": 101, "title": "Retained planning", "operation_key": "retained-group"}
    group = records.create_group(**group_body)
    milestone_body = {"project_id": 101, "epic_id": group["id"], "title": "Original milestone", "operation_key": "retained-milestone"}
    milestone = records.create_milestone(**milestone_body)
    backup, restored = tmp_path / "backup", tmp_path / "restored"
    backup_installation(original, backup)
    restore_installation(backup, restored)
    recovered = OwnerPlanningRecords(SQLiteRunStore(restored / "source.db"))
    assert recovered.create_group(**group_body) == group
    assert recovered.create_milestone(**milestone_body) == milestone
    with closing(sqlite3.connect(restored / "source.db")) as conn:
        assert conn.execute("SELECT count(*) FROM owner_planning_commands").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM epics WHERE title='Retained planning'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0
