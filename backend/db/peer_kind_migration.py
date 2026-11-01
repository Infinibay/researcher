"""Expand peer kind atomically without rewriting external FK/trigger targets."""


def migrate_ken_peers(conn):
    if conn.in_transaction:
        raise RuntimeError("Peer kind migration requires its own transaction")
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    legacy = conn.execute("PRAGMA legacy_alter_table").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA legacy_alter_table=ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version=31").fetchone():
            conn.commit()
            return
        original = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='runtime_peers'"
        ).fetchone()[0]
        old = "kind IN ('native','business','command')"
        if original.count(old) != 1:
            raise RuntimeError("Unrecognized historical peer kind constraint")
        objects = [
            row[0]
            for row in conn.execute(
                "SELECT sql FROM sqlite_master WHERE tbl_name='runtime_peers' AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name"
            )
        ]
        columns = [row[1] for row in conn.execute("PRAGMA table_info(runtime_peers)")]
        quoted = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
        conn.execute("ALTER TABLE runtime_peers RENAME TO runtime_peers_v30")
        conn.execute(
            original.replace(old, "kind IN ('native','business','command','ken')")
        )
        conn.execute(
            f"INSERT INTO runtime_peers(rowid,{quoted}) SELECT rowid,{quoted} FROM runtime_peers_v30"
        )
        conn.execute("DROP TABLE runtime_peers_v30")
        for sql in objects:
            conn.execute(sql)
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Peer kind migration found inconsistent references")
        conn.execute(
            "INSERT INTO schema_migrations(version,name) VALUES(31,'owned_ken_peer_kind')"
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA legacy_alter_table=" + str(int(legacy)))
        conn.execute("PRAGMA foreign_keys=" + str(int(foreign_keys)))
