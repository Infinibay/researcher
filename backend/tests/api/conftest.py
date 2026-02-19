"""Shared fixtures for API route tests.

The shared _isolated_db and db_conn fixtures are inherited from
backend/tests/conftest.py.  This module overrides seeded_project to
match API-specific needs (status='new', no roster entries).
"""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def test_app(_isolated_db):
    """Create the FastAPI test app with periodic tasks disabled."""
    with patch("backend.security.cleanup.cleanup_manager.schedule_periodic_cleanup"), \
         patch("backend.git.cleanup_service.schedule_periodic_cleanup"):
        from backend.api.main import create_app
        app = create_app()
    return app


@pytest.fixture()
def client(test_app):
    """Return a Starlette TestClient for the test app."""
    return TestClient(test_app)


@pytest.fixture()
def seeded_project(db_conn):
    """Insert a project, epic, milestone, and return the project id.

    Overrides the shared seeded_project: uses status='new' (not
    'executing') and omits roster entries because the API layer does
    not require them.
    """
    db_conn.execute(
        """INSERT INTO projects (id, name, description, status, created_at)
           VALUES (1, 'Test Project', 'A test project', 'new', CURRENT_TIMESTAMP)"""
    )
    db_conn.execute(
        """INSERT INTO epics (id, project_id, title, description, status, priority, created_at)
           VALUES (1, 1, 'Test Epic', 'Epic description', 'open', 1, CURRENT_TIMESTAMP)"""
    )
    db_conn.execute(
        """INSERT INTO milestones (id, project_id, epic_id, title, description, status, created_at)
           VALUES (1, 1, 1, 'Test Milestone', 'Milestone desc', 'open', CURRENT_TIMESTAMP)"""
    )
    db_conn.commit()
    return 1
