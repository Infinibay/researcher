-- Migration57: a copied peer is historical evidence, never proof its original process ended.
CREATE TABLE runtime_peer_archives (
    peer_id TEXT PRIMARY KEY REFERENCES runtime_peers(id),
    snapshot_id TEXT NOT NULL CHECK(length(snapshot_id)=32),
    original_state TEXT NOT NULL CHECK(original_state IN ('prepared','bound')),
    origin_boot_id TEXT NOT NULL,
    origin_observer_namespace INTEGER NOT NULL,
    origin_database_identity TEXT,
    archived_at REAL NOT NULL
);
CREATE TRIGGER peer_archive_matches_origin BEFORE INSERT ON runtime_peer_archives
WHEN NOT EXISTS (
    SELECT 1 FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id
    JOIN runtime_runs r ON r.id=a.run_id
    WHERE p.id=new.peer_id AND p.state=new.original_state
      AND p.boot_id=new.origin_boot_id AND p.observer_namespace=new.origin_observer_namespace
      AND p.database_identity IS new.origin_database_identity AND r.status='superseded'
)
BEGIN SELECT RAISE(ABORT,'Peer archive must preserve a superseded original identity'); END;
CREATE TRIGGER peer_archive_immutable BEFORE UPDATE ON runtime_peer_archives
BEGIN SELECT RAISE(ABORT,'Original peer archival provenance is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(57,'restored_peer_history_without_closure_claim');
