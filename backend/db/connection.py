"""One SQLite connection policy shared by legacy and new adapters."""

import sqlite3
from pathlib import Path
from urllib.parse import quote


def connect(database: str, *, existing_only: bool = False) -> sqlite3.Connection:
    """Bootstrap may create; runtime transactions require an existing file.

    mode=rw makes absence fail at SQLite open, without a check/create race.
    URI encoding preserves literal filenames; it does not prove origin/ownership.
    """
    if existing_only:
        database = (
            "file:" + quote(str(Path(database).absolute()), safe="/") + "?mode=rw"
        )
    conn = sqlite3.connect(database, uri=existing_only)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -8000")
    return conn
