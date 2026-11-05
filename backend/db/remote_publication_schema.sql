-- Migration45: separate host remote action runs and original issue-once effect stages.
DROP TRIGGER native_task_done_requires_acceptance;
DROP INDEX idx_runtime_active_task;
ALTER TABLE runtime_runs ADD COLUMN next_execution_kind TEXT NOT NULL DEFAULT 'research'
 CHECK(next_execution_kind IN ('research','finding_review','development','code_review','code_publication','remote_publication'));
UPDATE runtime_runs SET next_execution_kind=execution_kind;
ALTER TABLE runtime_runs DROP COLUMN execution_kind;
ALTER TABLE runtime_runs RENAME COLUMN next_execution_kind TO execution_kind;
CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(
 project_id,task_id,CASE WHEN execution_kind IN ('finding_review','code_review') THEN 'review'
 WHEN execution_kind IN ('code_publication','remote_publication') THEN 'publication' ELSE 'author' END
) WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review');
CREATE TABLE runtime_remote_publications (
 run_id TEXT PRIMARY KEY REFERENCES runtime_runs(id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL,task_id INTEGER NOT NULL,
 local_publication_run_id TEXT NOT NULL REFERENCES runtime_code_publication_requests(run_id),
 origin_run_id TEXT NOT NULL REFERENCES runtime_runs(id),
 stage TEXT NOT NULL CHECK(stage IN ('push','pull','merge')),
 intent_json TEXT NOT NULL CHECK(json_valid(intent_json)),
 protocol_json TEXT NOT NULL CHECK(json_valid(protocol_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 created_at REAL NOT NULL,
 FOREIGN KEY(project_id,task_id)REFERENCES tasks(project_id,id)
);
CREATE TRIGGER remote_publication_intent_immutable BEFORE UPDATE OF run_id,project_id,task_id,local_publication_run_id,origin_run_id,stage,intent_json,protocol_json,created_at ON runtime_remote_publications
 BEGIN SELECT RAISE(ABORT,'Remote publication intent is immutable');END;
CREATE TRIGGER remote_publication_result_immutable BEFORE UPDATE OF result_json ON runtime_remote_publications
 WHEN old.result_json IS NOT NULL AND old.result_json IS NOT new.result_json
 BEGIN SELECT RAISE(ABORT,'Remote publication result is immutable');END;
CREATE TABLE runtime_remote_effects (
 run_id TEXT NOT NULL REFERENCES runtime_remote_publications(run_id) ON DELETE CASCADE,
 effect_name TEXT NOT NULL CHECK(effect_name IN ('push','pull','merge_git','merge_record')),
 operation_id TEXT NOT NULL UNIQUE,
 attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id),
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 state TEXT NOT NULL CHECK(state IN ('issued','uncertain','observed')),
 outcome_json TEXT CHECK(outcome_json IS NULL OR json_valid(outcome_json)),
 client_closed INTEGER NOT NULL DEFAULT 0 CHECK(client_closed IN (0,1)),
 issued_at REAL NOT NULL,
 PRIMARY KEY(run_id,effect_name)
);
CREATE TRIGGER remote_effect_intent_immutable BEFORE UPDATE OF run_id,effect_name,operation_id,attempt_id,request_json,issued_at ON runtime_remote_effects
 BEGIN SELECT RAISE(ABORT,'Original remote effect is immutable');END;
CREATE TRIGGER remote_effect_result_immutable BEFORE UPDATE ON runtime_remote_effects
 WHEN old.state='observed'AND(new.state IS NOT old.state OR new.outcome_json IS NOT old.outcome_json OR new.client_closed IS NOT old.client_closed)
 BEGIN SELECT RAISE(ABORT,'Known original remote effect cannot be replaced');END;
CREATE TABLE runtime_remote_observations (
 id INTEGER PRIMARY KEY,
 run_id TEXT NOT NULL,effect_name TEXT NOT NULL,
 observation_sha256 TEXT NOT NULL,result_json TEXT NOT NULL CHECK(json_valid(result_json)),created_at REAL NOT NULL,
 UNIQUE(run_id,effect_name,observation_sha256),
 FOREIGN KEY(run_id,effect_name)REFERENCES runtime_remote_effects(run_id,effect_name)
);
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
INSERT INTO schema_migrations(version,name)VALUES(45,'durable_remote_effect_stages');
