"""Reverse only an unused attachment-operation schema; original file intents are retained history."""


def restore_reference_operations_schema(conn):
    """Restore schema65 only when no operation has been admitted and no newer schema exists."""
    if conn.in_transaction:
        raise RuntimeError('Reference operation inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>66 LIMIT 1').fetchone():
            raise RuntimeError('Reference operation inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=66').fetchone():
            conn.rollback()
            return
        if conn.execute('SELECT 1 FROM reference_file_operations LIMIT 1').fetchone():
            raise RuntimeError('Reference operation inverse refuses recorded history')
        conn.execute('DROP TABLE reference_file_operations')
        conn.execute('DELETE FROM schema_migrations WHERE version=66')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
