"""Shared fixtures for flow tests."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Create an isolated SQLite DB per test from schema.sql."""
    db_path = str(tmp_path / "test_infinibay.db")

    schema_file = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
    schema_sql = schema_file.read_text()

    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.close()

    monkeypatch.setenv("INFINIBAY_DB", db_path)
    yield db_path


@pytest.fixture(autouse=True)
def _disable_persistence(monkeypatch):
    """Disable @persist decorator to avoid 'id' field requirement in tests."""
    from crewai.flow.persistence import decorators as persist_mod

    original_persist = persist_mod.persist

    def noop_persist(persistence=None, verbose=False):
        """No-op persist decorator for tests."""
        def decorator(target):
            return target
        return decorator

    monkeypatch.setattr(persist_mod, "persist", noop_persist)
    yield


@pytest.fixture(autouse=True)
def _disable_autonomy(monkeypatch):
    """Disable autonomy layer so flow tests use the original centralized loop."""
    monkeypatch.setattr(
        "backend.config.settings.settings.AUTONOMY_ENABLED", False,
    )


@pytest.fixture(autouse=True)
def _reset_engine():
    """Reset the engine singleton between tests."""
    from backend.engine import reset_engine
    reset_engine()
    yield
    reset_engine()


@pytest.fixture()
def db_conn(_isolated_db):
    """Return a connection to the test database."""
    conn = sqlite3.connect(_isolated_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture()
def sample_project(db_conn):
    """Insert a sample project and return its id."""
    db_conn.execute(
        """INSERT INTO projects (name, description, status, created_at)
           VALUES ('Test Project', 'A test project', 'new', CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    row = db_conn.execute("SELECT last_insert_rowid() as id").fetchone()
    return row["id"]


@pytest.fixture()
def executing_project(db_conn):
    """Insert a project in executing state with sample tasks."""
    db_conn.execute(
        """INSERT INTO projects (name, description, status, created_at)
           VALUES ('Executing Project', 'In progress', 'executing', CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    row = db_conn.execute("SELECT last_insert_rowid() as id").fetchone()
    project_id = row["id"]

    # Create an epic
    db_conn.execute(
        """INSERT INTO epics (project_id, title, description, status, priority, created_at)
           VALUES (?, 'Test Epic', 'Test epic desc', 'open', 1, CURRENT_TIMESTAMP)""",
        (project_id,),
    )
    db_conn.commit()

    # Create some tasks
    # Task 1: pending (dev flow does pending → in_progress)
    # Task 2: pending (research flow does pending → in_progress)
    # Task 3: backlog (dependency tests)
    # Task 4: in_progress (code review flow does in_progress → review_ready)
    for i, (title, task_type, status) in enumerate([
        ("Implement feature A", "code", "pending"),
        ("Research algorithm B", "research", "pending"),
        ("Write tests for A", "test", "backlog"),
        ("Review feature C", "code", "in_progress"),
    ], start=1):
        db_conn.execute(
            """INSERT INTO tasks
                   (project_id, title, description, type, status, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (project_id, title, f"Description for {title}", task_type, status, i),
        )
    db_conn.commit()

    return project_id


def make_mock_crew(return_value="Mock crew result"):
    """Create a mock Crew that returns a given value on kickoff."""
    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = return_value
    return mock_crew


def make_mock_agent(role="developer", project_id=1):
    """Create a mock InfinibayAgent."""
    agent = MagicMock()
    agent.agent_id = f"{role}_p{project_id}"
    agent.role = role
    agent.project_id = project_id
    agent.crewai_agent = MagicMock()
    agent.create_agent_run.return_value = "test-run-id"
    return agent


def make_mock_engine(return_value="Mock engine result"):
    """Create a mock AgentEngine whose execute() returns a given value.

    Usage in tests::

        @patch("backend.engine.get_engine")
        def test_foo(self, mock_get_engine, ...):
            mock_get_engine.return_value = make_mock_engine("result text")
    """
    mock_engine = MagicMock()
    mock_engine.execute.return_value = return_value
    return mock_engine
