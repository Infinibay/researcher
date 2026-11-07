"""Migrate wiki identity without nulling references, dropping history or reusing ids.

SQLite table rebuilds run inside one exclusive write transaction with FK enforcement
restored before returning. Existing metadata/columns, explicit indexes and FTS triggers
are retained. Rollback is intentionally limited to before wiki edits or wiki captures;
an older schema cannot safely represent new namespaced documents or wiki sources.
"""

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend.db.migrations import execute_resource


@contextmanager
def _schema_transaction(conn):
    """Own the whole rebuild and restore the caller's FK setting even after a copy fault."""
    if conn.in_transaction:
        raise RuntimeError("Wiki schema migration requires an idle connection")
    enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    previous = {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield
        current = {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}
        if current - previous:
            raise sqlite3.IntegrityError(
                "Wiki migration would break foreign-key references"
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys={int(enabled)}")


def _catalog(conn, table):
    """Read trusted schema declarations so a rebuild retains explicit indexes and triggers."""
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if ddl is None:
        raise RuntimeError(f"Missing pre-migration table {table}")
    objects = [
        row[0]
        for row in conn.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name",
            (table,),
        )
    ]
    return {"ddl": ddl[0], "objects": objects}


def _rebuild(conn, table, ddl, objects):
    """Swap one host-named table without renaming the original FK target or extracting data."""
    if table not in ("wiki_pages", "research_sources"):
        raise ValueError("Unsupported schema rebuild target")
    temporary = table + "_namespace_copy"
    replacement, count = re.subn(
        r'(?i)CREATE TABLE(?: IF NOT EXISTS)?\s+(?:"'
        + table
        + r'"|'
        + table
        + r")(?=\s|\()",
        "CREATE TABLE " + temporary,
        ddl,
        count=1,
    )
    if count != 1:
        raise ValueError("Unsupported table declaration for wiki migration")
    columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
    # Column identifiers come from the trusted schema, escaped even for custom metadata.
    projection = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
    sequence = None
    if "AUTOINCREMENT" in ddl.upper():
        row = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name=?", (table,)
        ).fetchone()
        sequence = row[0] if row else None
    conn.execute(replacement)
    conn.execute(
        f'INSERT INTO "{temporary}" ({projection}) SELECT {projection} FROM "{table}"'
    )
    conn.execute(f'DROP TABLE "{table}"')
    conn.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
    for sql in objects:
        conn.execute(sql)
    if sequence is not None:
        conn.execute(
            "UPDATE sqlite_sequence SET seq=max(seq,?) WHERE name=?", (sequence, table)
        )


def _wiki_fingerprint(conn, columns):
    """Detect any wiki data change before allowing an exact pre-write schema rollback."""
    projection = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
    digest = hashlib.sha256()
    for row in conn.execute(f"SELECT {projection} FROM wiki_pages ORDER BY id"):
        encoded = json.dumps(
            list(row),
            ensure_ascii=True,
            separators=(",", ":"),
            default=lambda value: {"bytes_hex": value.hex()},
        ).encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def apply_wiki_schema(conn):
    """Replace global path uniqueness, backfill immutable revisions and permit wiki snapshots."""
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version=33").fetchone():
        return
    with _schema_transaction(conn):
        original = {
            name: _catalog(conn, name) for name in ("wiki_pages", "research_sources")
        }
        columns = [row[1] for row in conn.execute("PRAGMA table_info(wiki_pages)")]
        baseline = _wiki_fingerprint(conn, columns)
        wiki_ddl, count = re.subn(
            r"(?i)(\bpath\s+TEXT\s+NOT\s+NULL)\s+UNIQUE\b",
            r"\1",
            original["wiki_pages"]["ddl"],
        )
        if count != 1:
            raise ValueError(
                "Unsupported wiki path constraint; migration requires the legacy schema"
            )
        sources_ddl = original["research_sources"]["ddl"].replace(
            "CHECK(kind IN ('attachment','web'))",
            "CHECK(kind IN ('attachment','web','wiki'))",
        )
        if sources_ddl == original["research_sources"]["ddl"]:
            raise ValueError("Unsupported captured-source kind constraint")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS wiki_migration_state(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)"
        )
        state = {
            "original": original,
            "wiki_columns": columns,
            "wiki_fingerprint": baseline,
        }
        conn.execute(
            "INSERT OR REPLACE INTO wiki_migration_state VALUES(1,?)",
            (json.dumps(state),),
        )
        _rebuild(conn, "wiki_pages", wiki_ddl, original["wiki_pages"]["objects"])
        conn.execute(
            "ALTER TABLE wiki_pages ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"
        )
        _rebuild(
            conn,
            "research_sources",
            sources_ddl,
            original["research_sources"]["objects"],
        )
        execute_resource(conn, Path(__file__).with_name("wiki_schema.sql"))
        names = [row[1] for row in conn.execute("PRAGMA table_info(wiki_pages)")]
        for row in conn.execute("SELECT * FROM wiki_pages"):
            page = dict(zip(names, row))
            conn.execute(
                "INSERT INTO wiki_revisions(page_id,revision,project_id,path,title,content,parent_path,sha256,actor,recorded_at,origin) VALUES(?,1,?,?,?,?,?,?,?,?,'legacy_snapshot')",
                (
                    page["id"],
                    page["project_id"],
                    page["path"],
                    page["title"],
                    page["content"],
                    page["parent_path"],
                    hashlib.sha256(page["content"].encode("utf-8")).hexdigest(),
                    page["updated_by"],
                    page["updated_at"],
                ),
            )


def restore_legacy_wiki_schema(conn):
    """Reverse only latest version33 before wiki writes; refuse later schemas and lossy changes/captures."""
    with _schema_transaction(conn):
        if conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0] != 33:
            raise ValueError('Wiki rollback requires latest version33; preserve later schemas and use compatible forward repair or explicit restore')
        row = conn.execute(
            "SELECT payload FROM wiki_migration_state WHERE id=1"
        ).fetchone()
        if row is None:
            raise ValueError("Wiki rollback metadata is unavailable")
        state = json.loads(row[0])
        if (
            _wiki_fingerprint(conn, state["wiki_columns"]) != state["wiki_fingerprint"]
            or conn.execute(
                "SELECT 1 FROM wiki_pages WHERE revision != 1 LIMIT 1"
            ).fetchone()
            or conn.execute("SELECT 1 FROM wiki_operations LIMIT 1").fetchone()
            or conn.execute(
                "SELECT 1 FROM research_sources WHERE kind='wiki' LIMIT 1"
            ).fetchone()
        ):
            raise ValueError(
                "Wiki rollback refused: new wiki data requires forward repair or an explicit backup restore"
            )
        # Remove only the added revision column; retained revision history stays in its own table.
        conn.execute("ALTER TABLE wiki_pages DROP COLUMN revision")
        for table in ("wiki_pages", "research_sources"):
            original = state["original"][table]
            _rebuild(conn, table, original["ddl"], original["objects"])
        conn.execute("DELETE FROM wiki_revisions")
        conn.execute("DELETE FROM schema_migrations WHERE version=33")
