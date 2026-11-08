"""Atomic additive research migration, using one packaged SQL resource."""

import sqlite3
from pathlib import Path

from backend.db.migrations import apply_sql_resource


def apply_research_schema(conn: sqlite3.Connection) -> None:
    """Apply the bundled research schema using the shared immediate transaction and rollback boundary."""
    apply_sql_resource(conn, Path(__file__).with_name("research_schema.sql"))
