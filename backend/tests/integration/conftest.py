"""Shared fixtures for integration tests.

The shared _isolated_db and db_conn fixtures are inherited from
backend/tests/conftest.py.  Integration tests create their own
project and epic within each test body via _create_project_and_epic().
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_persistence(monkeypatch):
    """Disable @persist decorator to avoid 'id' field requirement in tests."""
    from crewai.flow.persistence import decorators as persist_mod

    def noop_persist(persistence=None, verbose=False):
        def decorator(target):
            return target
        return decorator

    monkeypatch.setattr(persist_mod, "persist", noop_persist)
    yield
