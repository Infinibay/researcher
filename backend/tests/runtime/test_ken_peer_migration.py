"""Independent historical peer schema, references, custom data and rollback."""

import sqlite3
from pathlib import Path

import pytest


def legacy(tmp_path):
    conn = sqlite3.connect(tmp_path / "legacy.db")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT);
CREATE TABLE tasks(project_id INTEGER,id INTEGER,PRIMARY KEY(project_id,id));
CREATE TABLE runtime_runs(id TEXT PRIMARY KEY,project_id INTEGER,UNIQUE(project_id,id));
CREATE TABLE runtime_attempts(id TEXT PRIMARY KEY,run_id TEXT,UNIQUE(run_id,id));
INSERT INTO runtime_attempts VALUES('attempt','run');""")
    root = Path(__file__).parents[2] / "db"
    conn.executescript((root / "peer_schema.sql").read_text())
    conn.executescript((root / "peer_origin_schema.sql").read_text())
    conn.executescript("""ALTER TABLE runtime_peers ADD COLUMN custom_blob BLOB;
CREATE INDEX custom_peer_reason ON runtime_peers(reason);
CREATE TABLE custom_ref(id INTEGER PRIMARY KEY,peer_id TEXT REFERENCES runtime_peers(id));
CREATE TRIGGER custom_ref_scope BEFORE INSERT ON custom_ref
 WHEN NOT EXISTS(SELECT 1 FROM runtime_peers WHERE id=new.peer_id)
 BEGIN SELECT RAISE(ABORT,'Missing peer'); END;
INSERT INTO schema_migrations VALUES(30,'historical-inputs');""")
    conn.execute(
        "INSERT INTO runtime_peers(rowid,id,attempt_id,kind,protocol_version,state,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at,database_identity,custom_blob) VALUES(77,'native','attempt','native',1,'prepared',9,123,456,'boot',789,1.5,'source',?)",
        (b"\x00\xff",),
    )
    conn.execute(
        "INSERT INTO runtime_peers(rowid,id,attempt_id,kind,protocol_version,state,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at,reason,closed_at) VALUES(91,'command','attempt','command',1,'closed',9,123,456,'boot',789,2.5,'closed',3.5)"
    )
    conn.execute("INSERT INTO custom_ref VALUES(1,'native')")
    conn.commit()
    return conn


def snapshot(conn):
    return list(conn.execute("SELECT rowid,* FROM runtime_peers ORDER BY rowid"))


def test_peer_kind_upgrade_preserves_live_history_rowids_and_external_references(
    tmp_path,
):
    from backend.db.peer_kind_migration import migrate_ken_peers

    with legacy(tmp_path) as conn:
        before = snapshot(conn)
        migrate_ken_peers(conn)
        assert snapshot(conn) == before
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert (
            conn.execute("PRAGMA foreign_key_list(custom_ref)").fetchone()[2]
            == "runtime_peers"
        )
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='custom_peer_reason'"
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError, match="Close owned peers"):
            conn.execute("DELETE FROM runtime_peers WHERE id='native'")
        conn.rollback()
        conn.execute(
            "INSERT INTO runtime_peers(id,attempt_id,kind,protocol_version,state,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,created_at) VALUES('ken','attempt','ken',1,'prepared',9,123,456,'boot',789,4.5)"
        )
        conn.commit()
        migrate_ken_peers(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version=31"
            ).fetchone()[0]
            == 1
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO custom_ref VALUES(2,'absent')")


def test_failed_peer_upgrade_rolls_back_schema_rows_and_connection_pragmas(tmp_path):
    from backend.db.peer_kind_migration import migrate_ken_peers

    with legacy(tmp_path) as conn:
        before = snapshot(conn)
        schema = list(
            conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
            )
        )

        def deny_drop(action, arg1, *_):
            return (
                sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_DROP_TABLE and arg1 == "runtime_peers_v30"
                else sqlite3.SQLITE_OK
            )

        conn.set_authorizer(deny_drop)
        try:
            with pytest.raises(sqlite3.DatabaseError):
                migrate_ken_peers(conn)
        finally:
            conn.set_authorizer(None)
        assert snapshot(conn) == before
        assert (
            list(
                conn.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
                )
            )
            == schema
        )
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA legacy_alter_table").fetchone()[0] == 0
        assert not conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=31"
        ).fetchone()
