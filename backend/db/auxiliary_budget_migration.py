"""Permit reversal of unused local-accounting schema without discarding original work or owner policy."""


def restore_auxiliary_budget_schema(conn):
    """Reverse latest migration61 only before its first policy/work record; used installations require forward repair or verified restore."""
    if conn.in_transaction:raise RuntimeError('Auxiliary inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>61 LIMIT 1').fetchone():raise RuntimeError('Auxiliary inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=61').fetchone():conn.rollback();return
        if conn.execute('SELECT 1 FROM runtime_auxiliary_work LIMIT 1').fetchone() or conn.execute('SELECT 1 FROM runtime_auxiliary_policies LIMIT 1').fetchone():raise RuntimeError('Auxiliary inverse refuses recorded work/policy')
        conn.execute('DROP TRIGGER runtime_auxiliary_identity_immutable')
        conn.execute('DROP TABLE runtime_auxiliary_work')
        conn.execute('DROP TABLE runtime_auxiliary_policies')
        conn.execute('DELETE FROM schema_migrations WHERE version=61')
        conn.commit()
    except BaseException:conn.rollback();raise
