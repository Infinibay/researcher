"""Reverse unused preparation admission without erasing retained project capacity."""


def restore_preparation_budget_schema(conn):
    """Remove latest migration64 only before its first reservation; preserve historical dispatches."""
    if conn.in_transaction:
        raise RuntimeError('Preparation inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>64 LIMIT 1').fetchone():
            raise RuntimeError('Preparation inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=64').fetchone():
            conn.rollback()
            return
        if conn.execute('SELECT 1 FROM runtime_preparation_reservations LIMIT 1').fetchone():
            raise RuntimeError('Preparation inverse refuses recorded reservations')
        conn.execute('DROP TABLE runtime_preparation_reservations')
        conn.execute('DELETE FROM schema_migrations WHERE version=64')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
