"""Read-only serving checks for current migration history and retained data integrity."""

import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from backend.db.migration_catalog import LATEST_VERSION, validate_history


def verify_database(database, *, integrity=True):
    """Reject incomplete schemas before serving; optionally verify all data without repairing or creating it.

    Startup checks integrity and foreign keys before publishing owner access.
    Repeated readiness probes check the complete current history without scanning
    every business row. Neither check authorizes a migration or repair.
    """
    uri = 'file:' + quote(str(Path(database).absolute()), safe='/') + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.execute('BEGIN')
        applied = {row[0] for row in conn.execute('SELECT version FROM schema_migrations')}
        validate_history(applied, LATEST_VERSION)
        if max(applied, default=0) != LATEST_VERSION:
            raise RuntimeError('Database schema is not ready; complete the required migration before serving')
        if integrity:
            if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('Database integrity check failed; inspect or restore the original data')
            if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise RuntimeError('Database foreign-key relationships are invalid; inspect or restore the original data')
