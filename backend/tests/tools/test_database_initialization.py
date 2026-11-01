"""A startup must establish a usable schema or report failure."""

import sqlite3

import pytest

from backend.tools.base import db


def test_fresh_database_is_initialized_and_second_start_preserves_data(tmp_path):
    path = tmp_path / "nested" / "infinibay.db"

    db.ensure_migrations(str(path))
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('Preserved project')")

    db.ensure_migrations(str(path))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM projects").fetchall() == [("Preserved project",)]
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_failed_migration_prevents_startup_and_does_not_record_success(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO schema_migrations VALUES (6, 'already applied')")

    def failing_migration(conn):
        conn.execute("CREATE TABLE uncommitted_change (id INTEGER)")
        conn.execute("INSERT INTO schema_migrations VALUES (7, 'must roll back')")
        raise sqlite3.OperationalError("injected migration failure")

    monkeypatch.setattr(db, "_migrate_7_add_failed_status", failing_migration)

    with pytest.raises(sqlite3.OperationalError, match="injected migration failure"):
        db.ensure_migrations(str(path))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version FROM schema_migrations").fetchall() == [(6,)]


def test_unknown_database_is_not_overwritten_or_marked_initialized(tmp_path):
    path = tmp_path / "unrelated.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE customer_data (value TEXT)")
        conn.execute("INSERT INTO customer_data VALUES ('retain')")

    with pytest.raises(RuntimeError, match="schema_migrations"):
        db.ensure_migrations(str(path))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM customer_data").fetchone() == ("retain",)
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchone() is None


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_serving_requires_initialized_database_without_creating_or_changing_it(tmp_path, kind):
    path = tmp_path / "absent-parent" / "source.db"
    if kind == "empty":
        path.parent.mkdir()
        path.touch()
    with pytest.raises((RuntimeError, sqlite3.OperationalError)):
        db.ensure_migrations(str(path), existing_only=True)
    if kind == "missing":
        assert not path.parent.exists()
    else:
        assert path.read_bytes() == b""
        assert sorted(p.name for p in path.parent.iterdir()) == ["source.db"]


def test_existing_only_migration_preserves_recognized_data(tmp_path):
    path = tmp_path / "source.db"
    db.ensure_migrations(str(path))
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects (name) VALUES ('kept')")
    db.ensure_migrations(str(path), existing_only=True)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM projects").fetchall() == [("kept",)]
