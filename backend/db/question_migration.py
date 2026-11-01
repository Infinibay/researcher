"""Rebuild the run CHECK constraint using SQLite's transactional copy procedure."""

import sqlite3
from pathlib import Path

from backend.db.migrations import execute_resource


def apply_question_schema(conn):
    if conn.in_transaction:
        raise RuntimeError("Question migration cannot enter an existing transaction")
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    legacy_alter = conn.execute("PRAGMA legacy_alter_table").fetchone()[0]
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version=24").fetchone():
            conn.commit()
            return
        objects = conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE tbl_name='runtime_runs' AND type IN ('index','trigger') AND sql IS NOT NULL"
        ).fetchall()
        execute_resource(conn, Path(__file__).with_name("question_schema.sql"))
        # Known indexes are replaced by the resource; custom objects retain SQL.
        existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        for name, sql in objects:
            if name not in existing:
                conn.execute(sql)
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError(
                "Question migration found foreign key violations"
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA legacy_alter_table={int(legacy_alter)}")
        conn.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")
