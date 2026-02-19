"""SQLite database layer with retry logic and connection management."""

import logging
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Callable, TypeVar

from backend.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_DB_PATH = "/research/pabada.db"


def get_db_path() -> str:
    """Get database path from environment or default."""
    return os.environ.get("PABADA_DB", DEFAULT_DB_PATH)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection with required pragmas. Caller must close it."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -8000")
    return conn


def execute_with_retry(
    fn: Callable[[sqlite3.Connection], T],
    db_path: str | None = None,
    max_retries: int | None = None,
    base_delay: float | None = None,
) -> T:
    """Execute fn(conn) with exponential backoff retry on SQLITE_BUSY/LOCKED."""
    if db_path is None:
        db_path = get_db_path()
    if max_retries is None:
        max_retries = settings.MAX_RETRIES
    if base_delay is None:
        base_delay = settings.RETRY_BASE_DELAY

    last_error: Exception | None = None
    for attempt in range(max_retries):
        conn = get_connection(db_path)
        try:
            result = fn(conn)
            conn.close()
            return result
        except sqlite3.OperationalError as e:
            conn.close()
            last_error = e
            err_msg = str(e).lower()
            if ("locked" in err_msg or "busy" in err_msg) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(
                    "DB busy/locked (attempt %d/%d), retrying in %.2fs: %s",
                    attempt + 1, max_retries, delay, e,
                )
                time.sleep(delay)
                continue
            raise
    raise sqlite3.OperationalError(
        f"Database busy after {max_retries} retries: {last_error}"
    )


class DBConnection:
    """Context manager for database connections with transaction support.

    Usage:
        with DBConnection() as conn:
            conn.execute("INSERT INTO ...")
            # auto-commits on success, rolls back on exception
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or get_db_path()
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = get_connection(self._db_path)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is None:
            return False
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
                logger.error("DB transaction rolled back: %s", exc_val)
        finally:
            self._conn.close()
            self._conn = None
        return False


@contextmanager
def db_transaction(db_path: str | None = None):
    """Convenience context manager wrapping DBConnection."""
    with DBConnection(db_path) as conn:
        yield conn
