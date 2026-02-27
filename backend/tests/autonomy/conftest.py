"""Shared fixtures for autonomy tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Create an isolated SQLite DB per test from schema.sql."""
    db_path = str(tmp_path / "test_pabada.db")

    schema_file = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
    schema_sql = schema_file.read_text()

    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()

    monkeypatch.setenv("PABADA_DB", db_path)
    yield db_path


@pytest.fixture()
def db_conn(_isolated_db):
    """Return a connection to the test database."""
    conn = sqlite3.connect(_isolated_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture()
def executing_project(db_conn):
    """Insert a project in 'executing' state and return its id."""
    db_conn.execute(
        """INSERT INTO projects (name, description, status, created_at)
           VALUES ('Test Project', 'Testing autonomy', 'executing', CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    row = db_conn.execute("SELECT last_insert_rowid() as id").fetchone()
    return row["id"]


@pytest.fixture()
def new_project(db_conn):
    """Insert a project in 'new' state and return its id."""
    db_conn.execute(
        """INSERT INTO projects (name, description, status, created_at)
           VALUES ('New Project', 'Not started', 'new', CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    row = db_conn.execute("SELECT last_insert_rowid() as id").fetchone()
    return row["id"]


def seed_roster(db_conn, project_id: int, agents: list[tuple[str, str]]) -> None:
    """Insert roster entries for the given agents.

    agents: list of (agent_id, role) tuples.
    """
    for agent_id, role in agents:
        db_conn.execute(
            """INSERT INTO roster (agent_id, name, role, status, created_at)
               VALUES (?, ?, ?, 'idle', CURRENT_TIMESTAMP)""",
            (agent_id, f"Agent-{agent_id}", role),
        )
    db_conn.commit()


def seed_task(
    db_conn,
    project_id: int,
    *,
    title: str = "Test Task",
    task_type: str = "code",
    status: str = "pending",
    assigned_to: str | None = None,
    priority: int = 2,
) -> int:
    """Insert a task and return its id."""
    db_conn.execute(
        """INSERT INTO tasks
               (project_id, title, description, type, status, assigned_to, priority, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (project_id, title, f"Desc for {title}", task_type, status, assigned_to, priority),
    )
    db_conn.commit()
    row = db_conn.execute("SELECT last_insert_rowid() as id").fetchone()
    return row["id"]
