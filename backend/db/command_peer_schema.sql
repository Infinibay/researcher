-- Migration 27: closure proof is independent from a command's terminal result.
ALTER TABLE runtime_jobs ADD COLUMN peer_id TEXT REFERENCES runtime_peers(id);
CREATE INDEX idx_jobs_peer ON runtime_jobs(peer_id);
CREATE TRIGGER require_scoped_job_peer BEFORE INSERT ON runtime_jobs
    WHEN (new.peer_id IS NULL AND EXISTS(SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=new.attempt_id))
      OR (new.peer_id IS NOT NULL AND NOT EXISTS(
          SELECT 1 FROM runtime_peers p WHERE p.id=new.peer_id
          AND p.attempt_id=new.attempt_id AND p.kind='command' AND p.state='bound'))
    BEGIN SELECT RAISE(ABORT,'Command requires its bound owned peer'); END;
CREATE TRIGGER immutable_job_peer BEFORE UPDATE OF peer_id ON runtime_jobs
    WHEN old.peer_id IS NOT new.peer_id
    BEGIN SELECT RAISE(ABORT,'Command peer ownership is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(27,'command_peer_ownership_and_quiescence');
