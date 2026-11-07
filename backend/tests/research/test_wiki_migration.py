"""Namespace migration preserves rows, references, FTS and rollback without data loss."""

import sqlite3

import pytest


def legacy_database(monkeypatch, path):
    """Build the real pre-wiki-migration schema without copying a production database."""
    from backend.db import wiki_migration
    from backend.tools.base.db import ensure_migrations

    migrate = wiki_migration.apply_wiki_schema
    ensure_migrations(path, target_version=32)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("INSERT INTO projects(id,name) VALUES(101,'Alpha')")
    conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Trial','in_progress')"
    )
    conn.execute(
        "INSERT INTO wiki_pages(id,project_id,path,title,content,created_by) VALUES(77,101,'intro','Intro','Evidence remains searchable','original-author')"
    )
    conn.execute(
        "INSERT INTO wiki_pages(id,project_id,path,title,content) VALUES(99,101,'removed','Removed','Removed')"
    )
    conn.execute("DELETE FROM wiki_pages WHERE id=99")
    conn.execute(
        "INSERT INTO findings(id,project_id,task_id,topic,content,wiki_page_id,agent_id) VALUES(1,101,1001,'Trial','Finding',77,'fixture')"
    )
    conn.execute(
        "INSERT INTO research_sources VALUES(9,101,1001,'attachment','reference:1','Saved','Exact quote','hash','{}',1)"
    )
    conn.execute("INSERT INTO finding_sources VALUES(101,1,9,'Exact quote')")
    conn.commit()
    return conn, migrate


def test_wiki_migration_retains_ids_foreign_keys_sequences_and_search(
    monkeypatch, _isolated_db
):
    """Rebuilding uniqueness may not null findings, reuse a deleted id or detach FTS content."""
    from backend.db.wiki_migration import restore_legacy_wiki_schema

    conn, migrate = legacy_database(monkeypatch, _isolated_db)
    try:
        migrate(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert list(conn.execute("PRAGMA foreign_key_check")) == []
        assert (
            conn.execute("SELECT wiki_page_id FROM findings WHERE id=1").fetchone()[0]
            == 77
        )
        assert conn.execute("SELECT source_id FROM finding_sources").fetchone()[0] == 9
        assert (
            conn.execute(
                "SELECT rowid FROM wiki_fts WHERE wiki_fts MATCH 'searchable'"
            ).fetchone()[0]
            == 77
        )
        revision = conn.execute(
            "SELECT * FROM wiki_revisions WHERE page_id=77 AND revision=1"
        ).fetchone()
        assert revision["content"] == "Evidence remains searchable"
        assert revision["actor"] is None
        assert revision["origin"] == "legacy_snapshot"
        assert (
            conn.execute("SELECT created_by FROM wiki_pages WHERE id=77").fetchone()[0]
            == "original-author"
        )
        assert (
            conn.execute("SELECT revision FROM wiki_pages WHERE id=77").fetchone()[0]
            == 1
        )
        # Safe rollback is available before wiki writes and leaves original relationships intact.
        restore_legacy_wiki_schema(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert (
            conn.execute("SELECT wiki_page_id FROM findings WHERE id=1").fetchone()[0]
            == 77
        )
        migrate(conn)
        cursor = conn.execute(
            "INSERT INTO wiki_pages(project_id,path,title,content) VALUES(101,'new','New','New')"
        )
        assert cursor.lastrowid > 99
        conn.commit()
    finally:
        conn.close()


def test_wiki_migration_failure_rolls_back_schema_and_authority(
    monkeypatch, _isolated_db
):
    """A fault rebuilding the second table must not leave half a migration or FK checks disabled."""
    from backend.db import wiki_migration

    conn, migrate = legacy_database(monkeypatch, _isolated_db)
    rebuild = wiki_migration._rebuild

    def fail_second(connection, table, *args, **kwargs):
        """Inject storage failure after wiki changes but before the source table swap."""
        if table == "research_sources":
            raise sqlite3.OperationalError("synthetic storage fault")
        return rebuild(connection, table, *args, **kwargs)

    monkeypatch.setattr(wiki_migration, "_rebuild", fail_second)
    try:
        with pytest.raises(sqlite3.OperationalError, match="synthetic"):
            migrate(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("SELECT wiki_page_id FROM findings").fetchone()[0] == 77
        assert "revision" not in [
            r[1] for r in conn.execute("PRAGMA table_info(wiki_pages)")
        ]
        assert (
            conn.execute(
                "SELECT count(*) FROM schema_migrations WHERE version=33"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT rowid FROM wiki_fts WHERE wiki_fts MATCH 'searchable'"
            ).fetchone()[0]
            == 77
        )
    finally:
        conn.close()


def test_rollback_refuses_namespace_collisions_without_modifying_data(
    monkeypatch, _isolated_db
):
    """An old global uniqueness constraint cannot safely represent new scoped wiki data."""
    from backend.db.wiki_migration import restore_legacy_wiki_schema

    conn, migrate = legacy_database(monkeypatch, _isolated_db)
    try:
        migrate(conn)
        conn.execute(
            "INSERT INTO wiki_pages(project_id,path,title,content) VALUES(NULL,'intro','Global','Different evidence')"
        )
        conn.commit()
        with pytest.raises(ValueError, match="rollback"):
            restore_legacy_wiki_schema(conn)
        assert conn.execute("SELECT count(*) FROM wiki_pages").fetchone()[0] == 2
        assert (
            conn.execute(
                "SELECT count(*) FROM schema_migrations WHERE version=33"
            ).fetchone()[0]
            == 1
        )
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()
