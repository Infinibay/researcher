-- Migration 39: original-owned versioned check reservations and terminal observations.
CREATE TABLE runtime_code_checks (
 id TEXT PRIMARY KEY,
 attempt_id TEXT NOT NULL REFERENCES runtime_code_candidates(attempt_id) ON DELETE CASCADE,
 run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 context_version INTEGER NOT NULL, fence INTEGER NOT NULL, owner_id TEXT NOT NULL,
 operation_key TEXT NOT NULL, subject_json TEXT NOT NULL CHECK(json_valid(subject_json)),
 spec_json TEXT NOT NULL CHECK(json_valid(spec_json)), spec_sha256 TEXT NOT NULL CHECK(length(spec_sha256)=64),
 allocation TEXT NOT NULL UNIQUE,
 state TEXT NOT NULL CHECK(state IN ('preparing','ready','running','finished','reconciling')),
 workspace TEXT, device INTEGER, inode INTEGER,
 metadata TEXT, metadata_device INTEGER, metadata_inode INTEGER,
 peer_id TEXT UNIQUE REFERENCES runtime_peers(id), operation_id TEXT UNIQUE,
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 stdout BLOB, stderr BLOB, junit_xml BLOB, issue TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL,
 UNIQUE(run_id,operation_key),
 CHECK(state NOT IN ('ready','running','finished') OR (workspace IS NOT NULL AND device IS NOT NULL
   AND inode IS NOT NULL AND inode>0 AND metadata IS NOT NULL AND metadata_device IS NOT NULL AND metadata_inode IS NOT NULL AND metadata_inode>0)),
 CHECK(state NOT IN ('running','finished') OR peer_id IS NOT NULL),
 CHECK(state!='finished' OR (operation_id IS NOT NULL AND length(operation_id)=64 AND result_json IS NOT NULL
   AND stdout IS NOT NULL AND typeof(stdout)='blob' AND stderr IS NOT NULL AND typeof(stderr)='blob')),
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TRIGGER code_check_origin_immutable BEFORE UPDATE ON runtime_code_checks
WHEN new.id IS NOT old.id OR new.attempt_id IS NOT old.attempt_id OR new.run_id IS NOT old.run_id
 OR new.project_id IS NOT old.project_id OR new.task_id IS NOT old.task_id OR new.context_version IS NOT old.context_version
 OR new.fence IS NOT old.fence OR new.owner_id IS NOT old.owner_id OR new.operation_key IS NOT old.operation_key
 OR new.subject_json IS NOT old.subject_json OR new.spec_json IS NOT old.spec_json OR new.spec_sha256 IS NOT old.spec_sha256
 OR new.allocation IS NOT old.allocation OR new.created_at IS NOT old.created_at
BEGIN SELECT RAISE(ABORT,'Check original scope and recipe are immutable'); END;
CREATE TRIGGER code_check_prepared_immutable BEFORE UPDATE ON runtime_code_checks
WHEN old.workspace IS NOT NULL AND (new.workspace IS NOT old.workspace OR new.device IS NOT old.device OR new.inode IS NOT old.inode
 OR new.metadata IS NOT old.metadata OR new.metadata_device IS NOT old.metadata_device OR new.metadata_inode IS NOT old.metadata_inode)
BEGIN SELECT RAISE(ABORT,'Check prepared identity is immutable'); END;
CREATE TRIGGER code_check_peer_immutable BEFORE UPDATE ON runtime_code_checks
WHEN old.peer_id IS NOT NULL AND new.peer_id IS NOT old.peer_id
BEGIN SELECT RAISE(ABORT,'Check original peer is immutable'); END;
CREATE TRIGGER code_check_finished_immutable BEFORE UPDATE ON runtime_code_checks
WHEN old.state='finished'
BEGIN SELECT RAISE(ABORT,'Check observations are immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(39,'original_owned_code_checks');
