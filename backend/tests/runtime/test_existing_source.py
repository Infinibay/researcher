"""Losing runtime state cannot silently create another source database."""

import sqlite3
from pathlib import Path

import pytest


def test_first_runtime_read_never_creates_missing_source(tmp_path):
    from backend.runtime.sqlite_runs import SQLiteRunStore

    database = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        SQLiteRunStore(database).get(101, "unknown")
    assert not database.exists()
    assert not list(tmp_path.glob("missing.db*"))


def test_retirement_after_source_loss_never_recreates_database(service_setup):
    from backend.tests.runtime.test_peer_workspace_view import bound_peer

    registry, peer = bound_peer(service_setup, "command")
    database = Path(service_setup.c.database)
    database.unlink()
    with pytest.raises((sqlite3.OperationalError, FileNotFoundError)):
        registry.close(peer)
    assert not database.exists()


def test_existing_connection_preserves_literal_uri_characters(tmp_path):
    from backend.db.connection import connect

    database = tmp_path / "source?#percent% name.db"
    with sqlite3.connect(database) as setup:
        setup.execute("CREATE TABLE fact(value)")
        setup.execute("INSERT INTO fact VALUES(137)")
    conn = connect(str(database), existing_only=True)
    try:
        assert conn.execute("SELECT value FROM fact").fetchone()[0] == 137
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        conn.close()
    assert not (tmp_path / "source").exists()


@pytest.mark.parametrize("consumer", ["workspace", "owner", "research"])
def test_other_retained_adapters_never_create_missing_state(tmp_path, consumer):
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.views import OwnerRuntimeView
    from backend.runtime.workspaces import WorkspaceRegistry

    database = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        if consumer == "workspace":
            WorkspaceRegistry(database, tmp_path).bind(101)
        elif consumer == "owner":
            OwnerRuntimeView(database).question_inbox(101)
        else:
            SQLiteResearchStore(database).authorize("valid-length-test-token")
    assert not database.exists()
