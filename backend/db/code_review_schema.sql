-- Migration 40: immutable independent code-review subjects and source/candidate identity.
CREATE TABLE runtime_code_review_requests (
 run_id TEXT PRIMARY KEY REFERENCES runtime_runs(id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 context_version INTEGER NOT NULL CHECK(context_version>=1),
 subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
 snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),
 author_run_id TEXT NOT NULL REFERENCES runtime_runs(id),
 author_attempt_id TEXT NOT NULL REFERENCES runtime_code_candidates(attempt_id),
 author_actor_id TEXT NOT NULL, author_thread_id TEXT NOT NULL,
 candidate_workspace TEXT NOT NULL, candidate_device INTEGER NOT NULL,
 candidate_inode INTEGER NOT NULL CHECK(candidate_inode>0),
 created_at REAL NOT NULL,
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE,
 CHECK(run_id!=author_run_id)
);
CREATE INDEX code_review_author ON runtime_code_review_requests(project_id,author_attempt_id,created_at);
CREATE TRIGGER code_review_request_immutable BEFORE UPDATE ON runtime_code_review_requests
BEGIN SELECT RAISE(ABORT,'Code review subjects are immutable; admit a new review'); END;
INSERT INTO schema_migrations(version,name) VALUES(40,'independent_code_review_subjects');
