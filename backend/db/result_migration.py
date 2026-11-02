"""Lossless downgrade of unused explicit result delivery and owner acceptance storage."""


def restore_result_schema(conn):
    """Remove unused migration 35 only after all live result authority is closed.

    Delivery and acceptance records are historical evidence. Once any exists,
    forward repair or an explicit backup restore is required instead of deletion.
    """
    if conn.in_transaction:
        raise RuntimeError("Result rollback requires an idle connection")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=35"
        ).fetchone():
            conn.rollback()
            return
        blocked = any(
            conn.execute(sql).fetchone()
            for sql in (
                "SELECT 1 FROM schema_migrations WHERE version>35 LIMIT 1",
                "SELECT 1 FROM runtime_result_proposals LIMIT 1",
                "SELECT 1 FROM runtime_result_acceptances LIMIT 1",
                "SELECT 1 FROM runtime_runs WHERE status IN ('queued','running','cancelling','reconciling','waiting_input') LIMIT 1",
                "SELECT 1 FROM runtime_peers WHERE state!='closed' LIMIT 1",
                "SELECT 1 FROM tool_grants g,json_each(g.permissions_json) p WHERE g.revoked_at IS NULL AND p.value='results.propose' LIMIT 1",
            )
        )
        if blocked:
            raise RuntimeError(
                "Result rollback refused: delivery history or live authority requires forward repair or explicit backup restore"
            )
        conn.execute("DROP TRIGGER reopen_changed_accepted_task")
        conn.execute("DROP TRIGGER tasks_fts_au")
        conn.execute("""CREATE TRIGGER tasks_fts_au AFTER UPDATE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts,rowid,title,description,acceptance_criteria)
            VALUES('delete',old.id,COALESCE(old.title,''),COALESCE(old.description,''),COALESCE(old.acceptance_criteria,''));
            INSERT INTO tasks_fts(rowid,title,description,acceptance_criteria)
            VALUES(new.id,new.title,COALESCE(new.description,''),COALESCE(new.acceptance_criteria,''));
        END""")
        conn.execute("DROP TRIGGER native_finding_status_requires_review")
        conn.execute("DROP TRIGGER native_task_done_requires_acceptance")
        conn.execute("DROP TRIGGER result_acceptance_immutable")
        conn.execute("DROP TRIGGER result_proposal_immutable")
        conn.execute("DROP TABLE runtime_result_acceptances")
        conn.execute("DROP TABLE runtime_result_proposals")
        conn.execute("DELETE FROM schema_migrations WHERE version=35")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
