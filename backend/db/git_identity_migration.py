"""Reverse an unused Git identity schema without discarding recorded repository associations or colliding branch history."""

from pathlib import Path


def restore_git_identity_schema(conn):
    """Restore schema66 only with no branch/PR history and no later schema; populated installations use forward repair or backup."""
    if conn.in_transaction:
        raise RuntimeError('Git identity inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>67 LIMIT 1').fetchone():
            raise RuntimeError('Git identity inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=67').fetchone():
            conn.rollback()
            return
        if any(conn.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone() for table in ('branches','code_reviews')):
            raise RuntimeError('Git identity inverse refuses recorded branch or review history')
        for trigger in ('bind_review_repository','review_repository_scope_insert','review_repository_scope_update'):
            conn.execute(f'DROP TRIGGER {trigger}')
        conn.execute('DROP INDEX idx_code_reviews_repo')
        conn.execute('ALTER TABLE code_reviews DROP COLUMN repo_id')
        conn.execute('DROP TABLE branches')
        schema = Path(__file__).with_name('schema.sql').read_text()
        start = schema.index('CREATE TABLE IF NOT EXISTS branches (')
        end = schema.index('-- ---------------------------------------------------------------------------', start)
        import sqlite3
        statement = ''
        for line in schema[start:end].splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                conn.execute(statement)
                statement = ''
        conn.execute('DROP INDEX repository_project_identity')
        conn.execute('DELETE FROM schema_migrations WHERE version=67')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
