"""Task creation receipts serialize writers and preserve prior planning history across schema70."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
from threading import Barrier

import pytest

from backend.db.task_commands_migration import restore_task_commands_schema
from backend.planning.owner_records import OwnerPlanningRecords
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.tools.base.db import ensure_migrations


@pytest.fixture
def schema_target():
    """Keep schema70 inverse tests at their original historical boundary."""
    return 70


def test_concurrent_exact_task_creations_share_original_receipt(coordination):
    """Two SQLite writers converge on one task/dependency effect and identical immutable responses."""
    records = OwnerPlanningRecords(coordination.store)
    barrier = Barrier(2)

    def create(_):
        """Deliver the same owner intent concurrently through separate source-store transactions."""
        barrier.wait(timeout=5)
        return records.create_task(project_id=101, title='Concurrent task', depends_on=[1002], operation_key='same-task')

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, range(2)))
    assert results[0] == results[1]
    assert coordination.conn.execute("SELECT count(*) FROM tasks WHERE title='Concurrent task'").fetchone()[0] == 1
    assert coordination.conn.execute('SELECT count(*) FROM task_dependencies WHERE task_id=?', (results[0]['id'],)).fetchone()[0] == 1
    assert coordination.conn.execute("SELECT count(*) FROM owner_planning_commands WHERE kind='task.create'").fetchone()[0] == 1


def test_schema70_roundtrip_preserves_original_group_receipt(tmp_path):
    """Forward/inverse/forward retains original schema69 receipts and their immutability without new task effects."""
    database = tmp_path / 'planning.db'
    ensure_migrations(str(database), target_version=69)
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(1,'Retained')")
    records = OwnerPlanningRecords(SQLiteRunStore(database))
    group = records.create_group(project_id=1, title='Original', operation_key='retained-group')
    with closing(sqlite3.connect(database)) as conn:
        original = conn.execute('SELECT * FROM owner_planning_commands').fetchall()
    ensure_migrations(str(database), target_version=70)
    assert records.create_group(project_id=1, title='Original', operation_key='retained-group') == group
    with closing(sqlite3.connect(database)) as conn:
        restore_task_commands_schema(conn)
        assert conn.execute('SELECT * FROM owner_planning_commands').fetchall() == original
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 69
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            conn.execute("UPDATE owner_planning_commands SET resource_id=100")
    ensure_migrations(str(database), target_version=70)
    assert records.create_group(project_id=1, title='Original', operation_key='retained-group') == group


def test_task_receipt_inverse_refuses_recorded_task_or_newer_schema(coordination):
    """A used schema cannot discard an original task request, including when a later schema exists."""
    created = OwnerPlanningRecords(coordination.store).create_task(project_id=101, title='Retained task', operation_key='retained-task')
    with closing(sqlite3.connect(coordination.database)) as conn:
        with pytest.raises(RuntimeError, match='recorded task requests'):
            restore_task_commands_schema(conn)
        assert conn.execute("SELECT resource_id FROM owner_planning_commands WHERE kind='task.create'").fetchone()[0] == created['id']
        with conn:
            conn.execute("INSERT INTO schema_migrations(version,name) VALUES(71,'future fixture')")
        with pytest.raises(RuntimeError, match='newer schema'):
            restore_task_commands_schema(conn)


def test_inverse_rebuild_failure_rolls_back_original_receipts_and_trigger(coordination):
    """A real SQLite denial at the final history write restores the entire table rebuild and immutable trigger."""
    group = OwnerPlanningRecords(coordination.store).create_group(project_id=101, title='Retained group', operation_key='rollback-group')
    with closing(sqlite3.connect(coordination.database)) as conn:
        def reject_removal(action, table, *args):
            """Reject the inverse version removal after its actual table replacement."""
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_DELETE and table == 'schema_migrations' else sqlite3.SQLITE_OK

        conn.set_authorizer(reject_removal)
        with pytest.raises(sqlite3.DatabaseError):
            restore_task_commands_schema(conn)
        conn.set_authorizer(None)
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 70
        assert conn.execute('SELECT resource_id FROM owner_planning_commands').fetchone()[0] == group['id']
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            conn.execute('UPDATE owner_planning_commands SET resource_id=100')
