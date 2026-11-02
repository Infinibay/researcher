"""Reverse unused native development structures without discarding execution evidence.

Each inverse owns one immediate transaction. Historical development roots,
retained preparations, live attempts and later schemas require forward repair
or an explicit backup restore. No copy, branch or source directory is deleted.
"""

from contextlib import contextmanager


@contextmanager
def _unused(conn, version):
    """Hold an idle connection's schema lock and reject live, historical or newer authority."""
    if conn.in_transaction:
        raise RuntimeError("Development rollback requires an idle connection")
    conn.execute("BEGIN IMMEDIATE")
    try:
        present = (
            conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
            ).fetchone()
            is not None
        )
        if present:
            blocked = (
                conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version>? LIMIT 1",
                    (version,),
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM runtime_runs WHERE execution_kind IN ('development','code_review') LIMIT 1"
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM runtime_runs WHERE status IN ('queued','running','cancelling','reconciling','waiting_input') LIMIT 1"
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM runtime_peers WHERE state!='closed' LIMIT 1"
                ).fetchone()
                or (
                    version == 37
                    and conn.execute(
                        "SELECT 1 FROM runtime_development_workspaces LIMIT 1"
                    ).fetchone()
                )
            )
            if blocked:
                raise RuntimeError(
                    "Development rollback refused: execution history or live authority requires forward repair or explicit backup restore"
                )
        yield present
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def restore_development_workspaces(conn):
    """Remove migration37 only before any preparation or development execution has been recorded."""
    with _unused(conn, 37) as present:
        if not present:
            return
        conn.execute("DROP TRIGGER development_workspace_ready_identity_immutable")
        conn.execute("DROP TRIGGER development_workspace_origin_immutable")
        conn.execute("DROP TABLE runtime_development_workspaces")
        conn.execute("DELETE FROM schema_migrations WHERE version=37")


def restore_development_kinds(conn):
    """Restore the two research kinds after unused later storage is explicitly removed."""
    with _unused(conn, 36) as present:
        if not present:
            return
        conn.execute("DROP INDEX idx_runtime_active_task")
        conn.execute("""ALTER TABLE runtime_runs ADD COLUMN next_execution_kind TEXT NOT NULL DEFAULT 'research'
            CHECK(next_execution_kind IN ('research','finding_review'))""")
        conn.execute("UPDATE runtime_runs SET next_execution_kind=execution_kind")
        conn.execute("ALTER TABLE runtime_runs DROP COLUMN execution_kind")
        conn.execute(
            "ALTER TABLE runtime_runs RENAME COLUMN next_execution_kind TO execution_kind"
        )
        conn.execute("""CREATE UNIQUE INDEX idx_runtime_active_task
            ON runtime_runs(project_id,task_id,execution_kind)
            WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')""")
        conn.execute("DELETE FROM schema_migrations WHERE version=36")
