"""Shared test fixtures for all backend test packages.

Provides an isolated SQLite DB from schema.sql, a db_conn for direct queries,
and a seeded_project with minimal roster/epic/milestone data.
"""

import sqlite3
from pathlib import Path

import pytest


SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Create an isolated SQLite DB per test from schema.sql."""
    db_path = str(tmp_path / "test_infinibay.db")

    schema_sql = SCHEMA_FILE.read_text()

    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()

    monkeypatch.setenv("INFINIBAY_DB", db_path)
    yield db_path


@pytest.fixture()
def db_conn(_isolated_db):
    """Return a connection to the test database."""
    conn = sqlite3.connect(_isolated_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture()
def seeded_project(db_conn):
    """Insert a project with roster agents, epic, and milestone.

    Returns the project id (1).
    """
    db_conn.execute(
        """INSERT INTO projects (id, name, description, status, created_at)
           VALUES (1, 'Test Project', 'A test project', 'executing', CURRENT_TIMESTAMP)"""
    )
    db_conn.execute(
        """INSERT INTO roster (agent_id, name, role, status)
           VALUES ('agent-1', 'Developer', 'developer', 'active')"""
    )
    db_conn.execute(
        """INSERT INTO roster (agent_id, name, role, status)
           VALUES ('lead-1', 'Team Lead', 'team_lead', 'active')"""
    )
    db_conn.execute(
        """INSERT INTO epics (id, project_id, title, description, status, priority, created_at)
           VALUES (1, 1, 'Test Epic', 'Epic description', 'open', 1, CURRENT_TIMESTAMP)"""
    )
    db_conn.execute(
        """INSERT INTO milestones (id, project_id, epic_id, title, description, status, created_at)
           VALUES (1, 1, 1, 'Test Milestone', 'Milestone description', 'open', CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    return 1
