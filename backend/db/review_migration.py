"""Refuse lossy rollback of admitted finding reviews and their original authority.

Application migrations add the packaged review SQL atomically. This inverse is
available only before any review admission; it preserves original runs, subjects,
evidence and owner schema objects or rolls the entire attempted downgrade back.
"""


def restore_review_schema(conn):
    """Remove unused review storage only; new requests require forward repair/restore."""
    if conn.in_transaction:
        raise RuntimeError("Review rollback requires an idle connection")
    if (
        conn.execute("SELECT 1 FROM schema_migrations WHERE version=34").fetchone()
        is None
    ):
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        if (
            conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version>34 LIMIT 1"
            ).fetchone()
            or conn.execute("SELECT 1 FROM finding_review_requests LIMIT 1").fetchone()
            or conn.execute("SELECT 1 FROM finding_review_decisions LIMIT 1").fetchone()
            or conn.execute("SELECT 1 FROM finding_review_evidence LIMIT 1").fetchone()
            or conn.execute(
                "SELECT 1 FROM runtime_runs WHERE execution_kind<>'research' LIMIT 1"
            ).fetchone()
        ):
            raise RuntimeError(
                "Review rollback refused: admitted reviews require forward repair or explicit backup restore"
            )
        conn.execute("DROP TABLE finding_review_evidence")
        conn.execute("DROP TABLE finding_review_decisions")
        conn.execute("DROP TABLE finding_review_requests")
        conn.execute("DROP INDEX idx_runtime_active_task")
        conn.execute("ALTER TABLE runtime_runs DROP COLUMN execution_kind")
        conn.execute(
            "CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(project_id,task_id) WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')"
        )
        conn.execute("DELETE FROM schema_migrations WHERE version=34")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
