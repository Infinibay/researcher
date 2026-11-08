"""Reverse unused causal invalidation infrastructure without losing recorded authority changes."""

from pathlib import Path
import sqlite3


def _restore_trigger(conn, resource, name):
    """Restore one exact historical trigger inside the caller's transaction, never replay its migration."""
    statement = ''
    for line in Path(__file__).with_name(resource).read_text().splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            if f'CREATE TRIGGER {name} ' in statement:
                conn.execute(statement)
                return
            statement = ''
    raise RuntimeError(f'Historical trigger resource missing: {name}')


def restore_context_causality_schema(conn):
    """Restore schema70 only before any causal change was recorded; retain all original history otherwise."""
    if conn.in_transaction:
        raise RuntimeError('Context causality inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>71 LIMIT 1').fetchone():
            raise RuntimeError('Context causality inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=71').fetchone():
            conn.rollback()
            return
        if conn.execute('SELECT 1 FROM runtime_context_causes LIMIT 1').fetchone():
            raise RuntimeError('Context causality inverse refuses recorded authority changes')
        if conn.execute('SELECT 1 FROM runtime_manual_prerequisites LIMIT 1').fetchone():
            raise RuntimeError('Context causality inverse refuses recorded prerequisite material')
        for name in ('capture_context_update','capture_first_context_change','apply_context_cause','context_cause_completed_immutable','context_affected_immutable','manual_prerequisites_immutable'):
            conn.execute(f'DROP TRIGGER {name}')
        conn.execute('DROP VIEW runtime_context_causal_edges')
        conn.execute('DROP TABLE runtime_context_affected')
        conn.execute('DROP TABLE runtime_context_causes')
        conn.execute('DROP TABLE runtime_manual_prerequisites')
        _restore_trigger(conn,'project_planning_schema.sql','version_children_of_changed_plan')
        _restore_trigger(conn,'plan_execution_schema.sql','invalidate_authorized_plan_context')
        conn.execute('DELETE FROM schema_migrations WHERE version=71')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
