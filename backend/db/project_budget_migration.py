"""Reverse only unused owner-budget revisions while retaining historical host policy and all recorded consumption."""


def restore_project_budget_schema(conn):
    """Remove latest migration60 only without owner decisions; used history requires forward repair or verified backup restore with the service stopped."""
    if conn.in_transaction:
        raise RuntimeError('Budget inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>60 LIMIT 1').fetchone():
            raise RuntimeError('Budget inverse refuses a newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=60').fetchone():
            conn.rollback();return
        if conn.execute('SELECT 1 FROM runtime_project_budget_changes LIMIT 1').fetchone() or conn.execute('SELECT 1 FROM runtime_project_budgets WHERE revision>0 LIMIT 1').fetchone():
            raise RuntimeError('Budget inverse refuses owner decision history')
        conn.execute('DROP TRIGGER project_budget_change_immutable')
        conn.execute('DROP TABLE runtime_project_budget_changes')
        conn.execute('ALTER TABLE runtime_project_budgets DROP COLUMN revision')
        conn.execute('DELETE FROM schema_migrations WHERE version=60')
        conn.commit()
    except BaseException:
        conn.rollback();raise
