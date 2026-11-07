"""Reverse only unused retention infrastructure without discarding archive decisions or reopening quarantined work."""


def restore_workspace_retention_schema(conn):
    """Restore schema67 only before any retention intent exists; later or used installations require forward repair or backup."""
    if conn.in_transaction:raise RuntimeError('Retention inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>68 LIMIT 1').fetchone():raise RuntimeError('Retention inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=68').fetchone():conn.rollback();return
        if conn.execute('SELECT 1 FROM workspace_retention LIMIT 1').fetchone():raise RuntimeError('Retention inverse refuses recorded history')
        conn.execute('DROP TABLE workspace_retention_operations');conn.execute('DROP TABLE workspace_retention')
        conn.execute('DELETE FROM schema_migrations WHERE version=68');conn.commit()
    except BaseException:
        conn.rollback();raise
