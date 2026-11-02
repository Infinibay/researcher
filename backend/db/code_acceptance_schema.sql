-- Migration42: immutable paired-owner acceptance of exact code/check/review evidence.
CREATE TABLE runtime_code_acceptances (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 run_id TEXT NOT NULL UNIQUE REFERENCES runtime_runs(id) ON DELETE CASCADE,
 attempt_id TEXT NOT NULL UNIQUE REFERENCES runtime_code_candidates(attempt_id) ON DELETE CASCADE,
 review_run_id TEXT NOT NULL REFERENCES runtime_code_review_requests(run_id) ON DELETE CASCADE,
 context_version INTEGER NOT NULL CHECK(context_version>=1),
 operation_key TEXT NOT NULL, request_sha256 TEXT NOT NULL CHECK(length(request_sha256)=64),
 subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
 review_sha256 TEXT NOT NULL CHECK(length(review_sha256)=64),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)), accepted_at REAL NOT NULL,
 UNIQUE(project_id,task_id,operation_key),
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TRIGGER code_acceptance_immutable BEFORE UPDATE ON runtime_code_acceptances
BEGIN SELECT RAISE(ABORT,'Code acceptances are immutable historical owner decisions'); END;
DROP TRIGGER native_task_done_requires_acceptance;
DROP TRIGGER reopen_changed_accepted_task;
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
CREATE TRIGGER reopen_changed_accepted_task AFTER UPDATE OF
 title,description,type,acceptance_criteria,context_json,priority,estimated_complexity,
 branch_name,assigned_to,reviewer,epic_id,milestone_id,parent_task_id ON tasks
WHEN old.status='done' AND new.status='done'
 AND (old.title IS NOT new.title OR old.description IS NOT new.description
 OR old.type IS NOT new.type OR old.acceptance_criteria IS NOT new.acceptance_criteria
 OR old.context_json IS NOT new.context_json OR old.priority IS NOT new.priority
 OR old.estimated_complexity IS NOT new.estimated_complexity OR old.branch_name IS NOT new.branch_name
 OR old.assigned_to IS NOT new.assigned_to OR old.reviewer IS NOT new.reviewer
 OR old.epic_id IS NOT new.epic_id OR old.milestone_id IS NOT new.milestone_id
 OR old.parent_task_id IS NOT new.parent_task_id)
 AND (EXISTS(SELECT 1 FROM runtime_result_acceptances WHERE project_id=new.project_id AND task_id=new.id)
      OR EXISTS(SELECT 1 FROM runtime_code_acceptances WHERE project_id=new.project_id AND task_id=new.id))
BEGIN UPDATE tasks SET status='pending',completed_at=NULL WHERE project_id=new.project_id AND id=new.id; END;
INSERT INTO schema_migrations(version,name) VALUES(42,'exact_owner_code_acceptance');
