"""Forward/inverse causality migration preserves schema70 and refuses erasing observed changes."""

from contextlib import closing
import sqlite3

import pytest

from backend.db.context_causality_migration import restore_context_causality_schema
from backend.tools.base.db import ensure_migrations


def schema(conn):
    """Compare exact retained SQLite definitions, independently of journal pages and file layout."""
    return conn.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()


def test_unused_schema71_roundtrip_restores_original_triggers(tmp_path):
    """An unused forward/inverse/forward keeps original schema and retained task rows without fabricated causal history."""
    database=tmp_path/'causality.db'
    ensure_migrations(str(database),target_version=70)
    with closing(sqlite3.connect(database)) as conn,conn:
        conn.execute("INSERT INTO projects(id,name) VALUES(101,'Retained')")
        conn.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Original')")
        original=schema(conn)
    ensure_migrations(str(database),target_version=71)
    with closing(sqlite3.connect(database)) as conn:
        assert not conn.execute('SELECT 1 FROM runtime_context_causes').fetchall()
        restore_context_causality_schema(conn)
        assert schema(conn)==original
        assert conn.execute('SELECT title FROM tasks').fetchone()==('Original',)
    ensure_migrations(str(database),target_version=71)


def test_causality_inverse_preserves_used_history_and_refuses_future_schema(coordination):
    """A recorded context cause or future version cannot be removed by an inverse."""
    c=coordination
    c.conn.execute("UPDATE tasks SET description='Changed' WHERE id=1001");c.conn.commit()
    with closing(sqlite3.connect(c.database)) as conn:
        original=schema(conn)
        causes=conn.execute('SELECT * FROM runtime_context_causes').fetchall()
        with pytest.raises(RuntimeError,match='recorded authority changes'):
            restore_context_causality_schema(conn)
        assert schema(conn)==original and conn.execute('SELECT * FROM runtime_context_causes').fetchall()==causes
        with conn:
            conn.execute("INSERT INTO schema_migrations(version,name) VALUES(72,'future fixture')")
        with pytest.raises(RuntimeError,match='newer schema'):
            restore_context_causality_schema(conn)


def test_failed_inverse_restores_original_new_schema_atomically(coordination):
    """A rejected final version removal rolls back table drops and historical trigger recreation together."""
    with closing(sqlite3.connect(coordination.database)) as conn:
        original=schema(conn)
        def refuse(action,table,*args):
            """Reject history removal after actual inverse schema work has occurred."""
            return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_DELETE and table=='schema_migrations' else sqlite3.SQLITE_OK
        conn.set_authorizer(refuse)
        with pytest.raises(sqlite3.DatabaseError):
            restore_context_causality_schema(conn)
        conn.set_authorizer(None)
        assert schema(conn)==original
