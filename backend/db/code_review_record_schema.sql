-- Migration 41: original-owned native review validation, proposal and confirmation.
CREATE TABLE runtime_code_review_records (
 attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
 run_id TEXT NOT NULL UNIQUE REFERENCES runtime_code_review_requests(run_id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 context_version INTEGER NOT NULL, fence INTEGER NOT NULL, owner_id TEXT NOT NULL,
 subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
 state TEXT NOT NULL CHECK(state IN ('preparing','ready','proposed','confirmed','reconciling')),
 preflight_json TEXT CHECK(preflight_json IS NULL OR json_valid(preflight_json)),
 proposal_key TEXT, proposal_json TEXT CHECK(proposal_json IS NULL OR (json_valid(proposal_json) AND length(CAST(proposal_json AS BLOB))<=262144)),
 reference_proof_json TEXT CHECK(reference_proof_json IS NULL OR json_valid(reference_proof_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)), issue TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL,
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE,
 CHECK(state NOT IN ('ready','proposed','confirmed') OR preflight_json IS NOT NULL),
 CHECK(state NOT IN ('proposed','confirmed') OR (proposal_json IS NOT NULL AND proposal_key IS NOT NULL AND reference_proof_json IS NOT NULL)),
 CHECK(state!='confirmed' OR result_json IS NOT NULL)
);
CREATE TRIGGER code_review_record_origin_immutable BEFORE UPDATE ON runtime_code_review_records
WHEN new.attempt_id IS NOT old.attempt_id OR new.run_id IS NOT old.run_id OR new.project_id IS NOT old.project_id
 OR new.task_id IS NOT old.task_id OR new.context_version IS NOT old.context_version OR new.fence IS NOT old.fence
 OR new.owner_id IS NOT old.owner_id OR new.subject_sha256 IS NOT old.subject_sha256 OR new.created_at IS NOT old.created_at
 OR (old.preflight_json IS NOT NULL AND new.preflight_json IS NOT old.preflight_json)
BEGIN SELECT RAISE(ABORT,'Native review origin and preflight are immutable'); END;
CREATE TRIGGER code_review_proposal_immutable BEFORE UPDATE ON runtime_code_review_records
WHEN old.proposal_json IS NOT NULL AND (new.proposal_json IS NOT old.proposal_json OR new.proposal_key IS NOT old.proposal_key
 OR new.reference_proof_json IS NOT old.reference_proof_json)
BEGIN SELECT RAISE(ABORT,'Code review proposals are immutable'); END;
CREATE TRIGGER code_review_confirmation_immutable BEFORE UPDATE ON runtime_code_review_records
WHEN old.state='confirmed'
BEGIN SELECT RAISE(ABORT,'Confirmed review observations are immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(41,'original_owned_native_code_review_records');
