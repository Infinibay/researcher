"""Reverse unused continuation metadata without discarding any physical execution or owner decision."""


def restore_auxiliary_continuation_schema(conn):
    """Allow reversal of latest migration62 only when both new tables are empty, preserving older work unchanged."""
    if conn.in_transaction:raise RuntimeError('Continuation inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>62 LIMIT 1').fetchone():raise RuntimeError('Continuation inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=62').fetchone():conn.rollback();return
        if conn.execute('SELECT 1 FROM runtime_auxiliary_executions LIMIT 1').fetchone() or conn.execute('SELECT 1 FROM runtime_auxiliary_continuations LIMIT 1').fetchone():raise RuntimeError('Continuation inverse refuses recorded execution or decision')
        conn.execute('DROP TRIGGER runtime_auxiliary_continuation_immutable')
        conn.execute('DROP TABLE runtime_auxiliary_continuations')
        conn.execute('DROP TABLE runtime_auxiliary_executions')
        conn.execute('DELETE FROM schema_migrations WHERE version=62');conn.commit()
    except BaseException:conn.rollback();raise
