"""Distinguish current local calculation permission from copied history without claiming original host closure."""

import time

from backend.runtime.peer_registry import PeerRegistry
from backend.runtime.sqlite_runs import SQLiteRunStore


def database_origin(runs):
    """Reuse the peer registry's canonical path/device/inode identity for this actual SQLite database."""
    return PeerRegistry(runs)._database_identity()


def current_operation(conn, runs, project_id, root_id):
    """Select recorded results or a current permission, ignoring unconsumed permissions copied from another database."""
    row=conn.execute('''SELECT c.successor_operation_id FROM runtime_auxiliary_continuations c
        WHERE c.project_id=? AND c.root_operation_id=? AND (c.origin_database=? OR EXISTS(
            SELECT 1 FROM runtime_auxiliary_work w WHERE w.project_id=c.project_id AND w.operation_id=c.successor_operation_id))
        ORDER BY c.generation DESC LIMIT 1''',(project_id,root_id,database_origin(runs))).fetchone()
    return row['successor_operation_id'] if row else root_id


def archive_local_work(conn, database, snapshot_id):
    """Attach copied calculations to verified enrollment in its owning transaction; preserve all original work and permissions."""
    if not conn.in_transaction:raise RuntimeError('Local archival requires the enrollment transaction')
    current=database_origin(SQLiteRunStore(database))
    count=conn.execute('''INSERT INTO runtime_auxiliary_archives(project_id,operation_id,database_identity,snapshot_id,archived_at)
        SELECT project_id,operation_id,?,?,? FROM runtime_auxiliary_work''',(current,snapshot_id,time.time())).rowcount
    return count
