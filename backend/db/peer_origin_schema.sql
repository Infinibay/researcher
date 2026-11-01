-- Migration 26: origin cannot be guessed for previously registered peers.
ALTER TABLE runtime_peers ADD COLUMN database_identity TEXT;
INSERT INTO schema_migrations(version,name) VALUES(26,'owned_peer_database_origin');
