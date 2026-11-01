"""Execute one packaged SQL migration without executescript's implicit commit."""

import sqlite3
from pathlib import Path


def execute_resource(conn: sqlite3.Connection, path: Path) -> None:
    """Execute statements inside the caller's already-owned transaction."""
    if not conn.in_transaction:
        raise RuntimeError("SQL resource execution requires an owned transaction")
    statement = ""
    for line in path.read_text().splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise sqlite3.OperationalError("Incomplete migration SQL")


def apply_sql_resource(conn: sqlite3.Connection, path: Path) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        execute_resource(conn, path)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
