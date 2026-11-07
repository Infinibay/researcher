"""Reverse only unused imported-reference provenance storage without losing source attribution."""


def restore_reference_provenance_schema(conn):
    """Remove unused latest migration58 with the service stopped; used history requires forward repair."""
    if conn.in_transaction:raise RuntimeError('Reference provenance inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>58 LIMIT 1').fetchone():
            raise RuntimeError('Reference provenance inverse refuses a newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=58').fetchone():
            conn.rollback();return
        if conn.execute('SELECT 1 FROM reference_import_provenance LIMIT 1').fetchone():
            raise RuntimeError('Reference provenance inverse refuses imported history; use forward repair or a verified backup restore')
        conn.execute('DROP TRIGGER reference_import_provenance_immutable')
        conn.execute('DROP TABLE reference_import_provenance')
        conn.execute('DELETE FROM schema_migrations WHERE version=58')
        conn.commit()
    except BaseException:
        conn.rollback();raise
