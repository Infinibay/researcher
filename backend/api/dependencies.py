"""FastAPI dependency injection functions."""

from __future__ import annotations

import sqlite3

from fastapi import Query

from backend.tools.base.db import DBConnection, execute_with_retry, get_db_path


def get_db() -> sqlite3.Connection:
    """Return a database connection. Use as a FastAPI dependency."""
    conn = None
    try:
        from backend.tools.base.db import get_connection
        conn = get_connection()
        yield conn
    finally:
        if conn:
            conn.close()


def get_project_id(project_id: int = Query(..., description="Project ID")) -> int:
    """Extract project_id from query params."""
    return project_id
