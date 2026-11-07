"""Reverse unused origin metadata without erasing an owner permission or restoration provenance."""

from pathlib import Path
import sqlite3


def restore_auxiliary_origin_schema(conn):
    """Remove latest migration63 only before any local permission or archival record; preserve migration62 execution metadata."""
    if conn.in_transaction:raise RuntimeError('Local origin inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>63 LIMIT 1').fetchone():raise RuntimeError('Local origin inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=63').fetchone():conn.rollback();return
        if conn.execute('SELECT 1 FROM runtime_auxiliary_continuations LIMIT 1').fetchone() or conn.execute('SELECT 1 FROM runtime_auxiliary_archives LIMIT 1').fetchone():raise RuntimeError('Local origin inverse refuses recorded permission or archival')
        conn.execute('DROP TRIGGER runtime_auxiliary_archive_immutable')
        conn.execute('DROP TABLE runtime_auxiliary_archives')
        conn.execute('DROP TRIGGER runtime_auxiliary_continuation_immutable')
        conn.execute('DROP TABLE runtime_auxiliary_continuations')
        source=Path(__file__).with_name('auxiliary_continuation_schema.sql').read_text()
        source=source[source.index('CREATE TABLE runtime_auxiliary_continuations'):source.index('INSERT INTO schema_migrations')]
        statement=''
        for line in source.splitlines(keepends=True):
            statement+=line
            if sqlite3.complete_statement(statement):conn.execute(statement);statement=''
        if statement.strip():raise RuntimeError('Original local permission schema is incomplete')
        conn.execute('DELETE FROM schema_migrations WHERE version=63');conn.commit()
    except BaseException:conn.rollback();raise
