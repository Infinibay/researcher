-- Migration44: fresh readonly observation authority after original publication closure.
CREATE TABLE runtime_publication_observations (
 attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
 run_id TEXT NOT NULL REFERENCES runtime_code_publication_requests(run_id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 operation_key TEXT NOT NULL,
 source_attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id),
 expected_fence INTEGER NOT NULL,
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 closure_json TEXT NOT NULL CHECK(json_valid(closure_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 created_at REAL NOT NULL,
 UNIQUE(project_id,task_id,operation_key)
);
CREATE TRIGGER publication_observation_immutable BEFORE UPDATE OF
 attempt_id,run_id,project_id,task_id,operation_key,source_attempt_id,expected_fence,request_json,closure_json,created_at
 ON runtime_publication_observations
BEGIN SELECT RAISE(ABORT,'Publication observation authority is immutable'); END;
CREATE TRIGGER publication_observation_result_immutable BEFORE UPDATE OF result_json ON runtime_publication_observations
WHEN old.result_json IS NOT NULL AND old.result_json IS NOT new.result_json
BEGIN SELECT RAISE(ABORT,'Publication observations are immutable historical receipts'); END;
INSERT INTO schema_migrations(version,name) VALUES(44,'readonly_publication_recovery');
