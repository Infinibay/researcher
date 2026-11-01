-- Migration32: keep immutable native peer history, permit a closed replacement.
DROP INDEX idx_one_inference_peer_kind;
CREATE UNIQUE INDEX idx_one_inference_peer_kind ON runtime_peers(attempt_id,kind)
    WHERE kind='business' OR (kind='native' AND state<>'closed');
INSERT INTO schema_migrations(version,name) VALUES(32,'retained_native_peer_history');
