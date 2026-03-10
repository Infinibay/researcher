"""Tests for the database layer."""

import os
import sqlite3
import tempfile
import threading
import time

import pytest

from backend.tools.base.db import (
    DBConnection,
    execute_with_retry,
    get_connection,
    get_db_path,
)


class TestGetDbPath:
    def test_default_path(self):
        original = os.environ.pop("INFINIBAY_DB", None)
        try:
            assert get_db_path() == "/research/infinibay.db"
        finally:
            if original:
                os.environ["INFINIBAY_DB"] = original

    def test_env_override(self):
        os.environ["INFINIBAY_DB"] = "/custom/path.db"
        try:
            assert get_db_path() == "/custom/path.db"
        finally:
            del os.environ["INFINIBAY_DB"]


class TestGetConnection:
    def test_connection_row_factory(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")
        conn = get_connection(db_path)
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_connection_wal_mode(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")
        conn = get_connection(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_connection_foreign_keys(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")
        conn = get_connection(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()


class TestExecuteWithRetry:
    def test_successful_execution(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.commit()
        conn.close()

        def insert(conn):
            conn.execute("INSERT INTO t (val) VALUES ('hello')")
            conn.commit()
            return conn.execute("SELECT val FROM t").fetchone()[0]

        result = execute_with_retry(insert, db_path=db_path)
        assert result == "hello"

    def test_raises_on_persistent_error(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")

        def always_fails(conn):
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            execute_with_retry(
                always_fails, db_path=db_path,
                max_retries=2, base_delay=0.01,
            )

    def test_raises_non_lock_error_immediately(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")

        def syntax_error(conn):
            conn.execute("INVALID SQL")

        with pytest.raises(sqlite3.OperationalError):
            execute_with_retry(syntax_error, db_path=db_path)


class TestDBConnection:
    def test_auto_commit(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.commit()
        conn.close()

        with DBConnection(db_path) as conn:
            conn.execute("INSERT INTO t (val) VALUES ('auto')")

        # Verify committed
        conn = sqlite3.connect(db_path)
        val = conn.execute("SELECT val FROM t").fetchone()[0]
        assert val == "auto"
        conn.close()

    def test_rollback_on_error(self, tmp_dir):
        db_path = os.path.join(tmp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.commit()
        conn.close()

        with pytest.raises(ValueError):
            with DBConnection(db_path) as conn:
                conn.execute("INSERT INTO t (val) VALUES ('rollback')")
                raise ValueError("Simulated error")

        # Verify rolled back
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        assert count == 0
        conn.close()
