import sqlite3
from pathlib import Path

import pytest

from backend.tools.base.db import ensure_migrations

SCHEMA = Path(__file__).resolve().parents[2] / "db/schema.sql"


def legacy_database(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA.read_text())
        conn.execute("INSERT INTO projects(id,name) VALUES(17,'Preserved')")
        conn.execute(
            "INSERT INTO artifacts(id,project_id,type,file_path,content) VALUES(24,17,'report','legacy.md','Original report')"
        )


def test_existing_schema_gains_research_tables_without_changing_legacy_rows(tmp_path):
    path = tmp_path / "legacy.db"
    legacy_database(path)
    ensure_migrations(str(path))
    ensure_migrations(str(path))
    with sqlite3.connect(path) as conn:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "tool_grants",
            "task_contexts",
            "tool_operations",
            "research_sources",
            "finding_sources",
            "research_reports",
            "report_findings",
        } <= tables
        assert conn.execute("SELECT id,name FROM projects").fetchall() == [
            (17, "Preserved")
        ]
        assert conn.execute("SELECT id,content FROM artifacts").fetchall() == [
            (24, "Original report")
        ]
        assert conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=18"
        ).fetchone() == (1,)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_invalid_new_schema_rolls_back_ddl_and_version_marker(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    legacy_database(path)
    original_read = Path.read_text

    def corrupt(resource, *args, **kwargs):
        if resource.name == "research_schema.sql":
            return "CREATE TABLE must_rollback (id INTEGER);\nTHIS IS NOT SQL;\n"
        return original_read(resource, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", corrupt)
    with pytest.raises(sqlite3.OperationalError):
        ensure_migrations(str(path))
    with sqlite3.connect(path) as conn:
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE name='must_rollback'"
            ).fetchall()
            == []
        )
        assert (
            conn.execute(
                "SELECT version FROM schema_migrations WHERE version=18"
            ).fetchall()
            == []
        )
        assert conn.execute("SELECT content FROM artifacts").fetchall() == [
            ("Original report",)
        ]
