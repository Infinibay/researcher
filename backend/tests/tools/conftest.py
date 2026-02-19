"""Shared test fixtures for tool tests."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from backend.tools.base.context import set_context
from backend.tools.base.db import get_connection


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def test_db(tmp_dir):
    """Create a test SQLite database with the full schema."""
    db_path = os.path.join(tmp_dir, "test.db")

    # Read and execute the schema
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "db", "schema.sql"
    )
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)

    # Seed minimal data
    conn.execute(
        """INSERT INTO projects (id, name, description, status)
           VALUES (1, 'Test Project', 'A test project', 'executing')"""
    )
    conn.execute(
        """INSERT INTO roster (agent_id, name, role, status)
           VALUES ('agent-1', 'Test Agent', 'developer', 'active')"""
    )
    conn.execute(
        """INSERT INTO roster (agent_id, name, role, status)
           VALUES ('lead-1', 'Team Lead', 'team_lead', 'active')"""
    )
    conn.execute(
        """INSERT INTO epics (id, project_id, title, description, status)
           VALUES (1, 1, 'Test Epic', 'Epic description', 'open')"""
    )
    conn.execute(
        """INSERT INTO milestones (id, project_id, epic_id, title, description, status)
           VALUES (1, 1, 1, 'Test Milestone', 'Milestone description', 'open')"""
    )
    conn.commit()
    conn.close()

    # Set environment for tools to use this DB
    os.environ["PABADA_DB"] = db_path
    yield db_path

    # Cleanup
    if "PABADA_DB" in os.environ:
        del os.environ["PABADA_DB"]


@pytest.fixture
def agent_context(test_db):
    """Set up agent context for tests."""
    set_context(project_id=1, agent_id="agent-1", agent_run_id="run-1", task_id=None)
    yield
    # Reset context
    set_context(project_id=None, agent_id=None, agent_run_id=None, task_id=None)


@pytest.fixture
def sandbox_dir(tmp_dir):
    """Create a sandboxed directory for file operations."""
    sandbox = os.path.join(tmp_dir, "research")
    os.makedirs(sandbox)

    # Temporarily override settings
    from backend.config.settings import settings
    original = settings.ALLOWED_BASE_DIRS[:]
    settings.ALLOWED_BASE_DIRS = [sandbox]
    yield sandbox
    settings.ALLOWED_BASE_DIRS = original
