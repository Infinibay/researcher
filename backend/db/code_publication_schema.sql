-- Migration43: acceptance-bound host publication, separate from model execution.
DROP TRIGGER native_task_done_requires_acceptance;
DROP INDEX idx_runtime_active_task;
ALTER TABLE runtime_runs ADD COLUMN next_execution_kind TEXT NOT NULL DEFAULT 'research'
 CHECK(next_execution_kind IN ('research','finding_review','development','code_review','code_publication'));
UPDATE runtime_runs SET next_execution_kind=execution_kind;
ALTER TABLE runtime_runs DROP COLUMN execution_kind;
ALTER TABLE runtime_runs RENAME COLUMN next_execution_kind TO execution_kind;
CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(
 project_id,task_id,CASE WHEN execution_kind IN ('finding_review','code_review') THEN 'review'
 WHEN execution_kind='code_publication' THEN 'publication' ELSE 'author' END
) WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review');

CREATE TABLE runtime_code_publication_requests (
 run_id TEXT PRIMARY KEY REFERENCES runtime_runs(id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 author_run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
 author_attempt_id TEXT NOT NULL REFERENCES runtime_code_candidates(attempt_id),
 acceptance_id INTEGER NOT NULL REFERENCES runtime_code_acceptances(id),
 context_version INTEGER NOT NULL CHECK(context_version>=1),
 subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
 review_sha256 TEXT NOT NULL CHECK(length(review_sha256)=64),
 target_ref TEXT NOT NULL, expected_target_sha TEXT, receipt_ref TEXT NOT NULL UNIQUE,
 intent_json TEXT NOT NULL CHECK(json_valid(intent_json)),
 view_json TEXT NOT NULL CHECK(json_valid(view_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 created_at REAL NOT NULL,
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE INDEX idx_publication_author ON runtime_code_publication_requests(project_id,author_run_id,context_version);
CREATE TRIGGER code_publication_request_immutable BEFORE UPDATE OF
 run_id,project_id,task_id,author_run_id,author_attempt_id,acceptance_id,context_version,
 subject_sha256,review_sha256,target_ref,expected_target_sha,receipt_ref,intent_json,view_json,created_at
 ON runtime_code_publication_requests
BEGIN SELECT RAISE(ABORT,'Publication requests are immutable original owner intents'); END;
CREATE TRIGGER code_publication_result_immutable BEFORE UPDATE OF result_json ON runtime_code_publication_requests
WHEN old.result_json IS NOT NULL AND old.result_json IS NOT new.result_json
BEGIN SELECT RAISE(ABORT,'Publication results are immutable historical receipts'); END;

CREATE TRIGGER native_task_done_requires_acceptance BEFORE UPDATE OF status ON tasks
WHEN new.status='done' AND old.status IS NOT 'done'
 AND EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id)
 AND NOT EXISTS(
   SELECT 1 FROM runtime_result_acceptances a
   JOIN runtime_result_proposals p ON p.id=a.proposal_id
   JOIN runtime_runs r ON r.id=a.run_id
   WHERE a.project_id=new.project_id AND a.task_id=new.id AND r.status='accepted'
   AND p.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=new.id),1))
 AND NOT EXISTS(
   SELECT 1 FROM runtime_code_acceptances a
   JOIN runtime_code_candidates c ON c.attempt_id=a.attempt_id
   JOIN runtime_runs r ON r.id=a.run_id
   JOIN runtime_runs v ON v.id=a.review_run_id
   JOIN runtime_code_review_records rr ON rr.run_id=v.id
   WHERE a.project_id=new.project_id AND a.task_id=new.id AND r.status='accepted'
     AND r.execution_kind='development' AND r.current_attempt_id=a.attempt_id
     AND c.state='ready' AND v.status='accepted' AND rr.state='confirmed'
     AND json_extract(rr.proposal_json,'$.verdict')='supported'
     AND a.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=new.id),1))
BEGIN SELECT RAISE(ABORT,'Native task completion requires explicit owner acceptance'); END;
INSERT INTO schema_migrations(version,name) VALUES(43,'acceptance_bound_host_publication');
