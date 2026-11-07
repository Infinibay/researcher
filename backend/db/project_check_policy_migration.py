"""Reverse an unused check policy migration without removing owner decisions."""


def restore_project_check_policy_schema(conn):
    """Remove latest migration65 only before any project policy was recorded."""
    if conn.in_transaction:
        raise RuntimeError('Check policy inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>65 LIMIT 1').fetchone():
            raise RuntimeError('Check policy inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=65').fetchone():
            conn.rollback()
            return
        if conn.execute('SELECT 1 FROM runtime_project_check_policies LIMIT 1').fetchone() or conn.execute('SELECT 1 FROM runtime_project_check_policy_changes LIMIT 1').fetchone():
            raise RuntimeError('Check policy inverse refuses recorded owner history')
        conn.execute('DROP TABLE runtime_project_check_policy_changes')
        conn.execute('DROP TABLE runtime_project_check_policies')
        conn.execute('DELETE FROM schema_migrations WHERE version=65')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
