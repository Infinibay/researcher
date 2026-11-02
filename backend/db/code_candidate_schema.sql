-- Migration 38: retain exact private candidates without accepting or publishing a task.
CREATE TABLE runtime_code_candidates (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_development_workspaces(attempt_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    repository_id INTEGER NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    fence INTEGER NOT NULL CHECK(fence>=1),
    owner_id TEXT NOT NULL,
    source_json TEXT NOT NULL CHECK(json_valid(source_json)),
    prepared_json TEXT NOT NULL CHECK(json_valid(prepared_json)),
    base_sha TEXT NOT NULL,
    base_tree_sha TEXT NOT NULL,
    allocation TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN ('capturing','ready','reconciling')),
    workspace TEXT UNIQUE,
    device INTEGER,
    inode INTEGER,
    head_sha TEXT,
    tree_sha TEXT,
    diff BLOB,
    diff_sha256 TEXT,
    writer_proof_json TEXT CHECK(writer_proof_json IS NULL OR json_valid(writer_proof_json)),
    issue TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    CHECK(length(base_sha) IN (40,64) AND base_sha NOT GLOB '*[^0-9a-f]*'),
    CHECK(length(base_tree_sha) IN (40,64) AND base_tree_sha NOT GLOB '*[^0-9a-f]*'),
    CHECK(state!='ready' OR (workspace IS NOT NULL AND device IS NOT NULL AND device>=0
      AND inode IS NOT NULL AND inode>0 AND head_sha IS NOT NULL AND tree_sha IS NOT NULL
      AND length(head_sha) IN (40,64) AND head_sha NOT GLOB '*[^0-9a-f]*'
      AND length(tree_sha) IN (40,64) AND tree_sha NOT GLOB '*[^0-9a-f]*'
      AND diff IS NOT NULL AND typeof(diff)='blob' AND length(diff)<=1048576
      AND diff_sha256 IS NOT NULL AND length(diff_sha256)=64 AND diff_sha256 NOT GLOB '*[^0-9a-f]*'
      AND writer_proof_json IS NOT NULL AND json_type(writer_proof_json)='object'
      AND coalesce(json_type(writer_proof_json,'$.grant_id')='text'
        AND length(json_extract(writer_proof_json,'$.grant_id'))=64
        AND json_extract(writer_proof_json,'$.grant_id') NOT GLOB '*[^0-9a-f]*'
        AND json_type(writer_proof_json,'$.operations')='array'
        AND json_array_length(writer_proof_json,'$.operations') BETWEEN 1 AND 512,0))),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE INDEX idx_code_candidate_run ON runtime_code_candidates(project_id,run_id);
CREATE TRIGGER code_candidate_origin_immutable BEFORE UPDATE ON runtime_code_candidates
WHEN new.attempt_id IS NOT old.attempt_id OR new.run_id IS NOT old.run_id
 OR new.project_id IS NOT old.project_id OR new.task_id IS NOT old.task_id
 OR new.repository_id IS NOT old.repository_id OR new.context_version IS NOT old.context_version
 OR new.fence IS NOT old.fence OR new.owner_id IS NOT old.owner_id
 OR new.source_json IS NOT old.source_json OR new.prepared_json IS NOT old.prepared_json
 OR new.base_sha IS NOT old.base_sha OR new.base_tree_sha IS NOT old.base_tree_sha
 OR new.allocation IS NOT old.allocation OR new.created_at IS NOT old.created_at
BEGIN SELECT RAISE(ABORT,'Candidate original scope is immutable'); END;
CREATE TRIGGER code_candidate_ready_immutable BEFORE UPDATE ON runtime_code_candidates
WHEN old.state='ready'
BEGIN SELECT RAISE(ABORT,'Captured candidate is immutable; use a new attempt'); END;
INSERT INTO schema_migrations(version,name) VALUES(38,'retained_exact_code_candidates');
