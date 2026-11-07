"""Reverse unused peer archival storage without deleting evidence of copied actors."""


def restore_peer_archive_schema(conn):
    """Remove only unused latest migration57 on an idle administrative connection.

    Run with the service stopped. Once archival provenance exists, retain it and
    use forward repair or an explicit verified backup restore instead of deletion.
    """
    if conn.in_transaction:
        raise RuntimeError('Peer archive rollback requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>57 LIMIT 1').fetchone():
            raise RuntimeError('Peer archive rollback refused: newer schema requires a compatible inverse')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=57').fetchone():
            conn.rollback()
            return
        if conn.execute('SELECT 1 FROM runtime_peer_archives LIMIT 1').fetchone():
            raise RuntimeError('Peer archive rollback refused: archival history requires forward repair or explicit backup restore')
        conn.execute('DROP TRIGGER peer_archive_matches_origin')
        conn.execute('DROP TRIGGER peer_archive_immutable')
        conn.execute('DROP TABLE runtime_peer_archives')
        conn.execute('DELETE FROM schema_migrations WHERE version=57')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
