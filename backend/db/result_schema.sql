-- Migration35: explicit immutable research deliveries and version-bound owner decisions.
CREATE TABLE runtime_result_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
    attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    fence INTEGER NOT NULL CHECK(fence>=1),
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    kind TEXT NOT NULL CHECK(kind='research_reports'),
    subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
    snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),
    created_at REAL NOT NULL,
    UNIQUE(project_id,id),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE INDEX idx_result_proposals_run ON runtime_result_proposals(project_id,run_id,id);
CREATE TABLE runtime_result_acceptances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    run_id TEXT NOT NULL UNIQUE REFERENCES runtime_runs(id) ON DELETE CASCADE,
    proposal_id INTEGER NOT NULL REFERENCES runtime_result_proposals(id) ON DELETE CASCADE,
    operation_key TEXT NOT NULL,
    request_sha256 TEXT NOT NULL CHECK(length(request_sha256)=64),
    subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
    review_sha256 TEXT NOT NULL CHECK(length(review_sha256)=64),
    review_json TEXT NOT NULL CHECK(json_valid(review_json)),
    owner_note TEXT,
    acknowledged_limits INTEGER NOT NULL CHECK(acknowledged_limits IN (0,1)),
    actor_source TEXT NOT NULL CHECK(actor_source='paired_owner_action'),
    receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
    accepted_at REAL NOT NULL,
    UNIQUE(project_id,task_id,operation_key),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TRIGGER result_proposal_immutable BEFORE UPDATE ON runtime_result_proposals
BEGIN SELECT RAISE(ABORT,'Delivered candidates are immutable; propose another version'); END;
CREATE TRIGGER result_acceptance_immutable BEFORE UPDATE ON runtime_result_acceptances
BEGIN SELECT RAISE(ABORT,'Owner acceptances are immutable historical decisions'); END;
-- Native completion is a distinct owner action, even when old helpers write SQL.
CREATE TRIGGER native_task_done_requires_acceptance BEFORE UPDATE OF status ON tasks
WHEN new.status='done' AND old.status IS NOT 'done'
 AND EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id)
 AND NOT EXISTS(
   SELECT 1 FROM runtime_result_acceptances a
   JOIN runtime_result_proposals p ON p.id=a.proposal_id
   JOIN runtime_runs r ON r.id=a.run_id
   WHERE a.project_id=new.project_id AND a.task_id=new.id AND r.status='accepted'
   AND p.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=new.id),1))
BEGIN SELECT RAISE(ABORT,'Native task completion requires explicit owner acceptance'); END;
CREATE TRIGGER native_finding_status_requires_review BEFORE UPDATE OF status ON findings
WHEN new.status IS NOT old.status AND new.status IN ('active','superseded')
 AND EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.task_id)
BEGIN SELECT RAISE(ABORT,'Native findings require versioned review; mutable flags cannot validate or reject them'); END;
-- Reopening inside an input update must not delete not-yet-indexed new text.
DROP TRIGGER tasks_fts_au;
CREATE TRIGGER tasks_fts_au AFTER UPDATE OF title,description,acceptance_criteria ON tasks
BEGIN
    INSERT INTO tasks_fts(tasks_fts,rowid,title,description,acceptance_criteria)
    VALUES('delete',old.id,COALESCE(old.title,''),COALESCE(old.description,''),COALESCE(old.acceptance_criteria,''));
    INSERT INTO tasks_fts(rowid,title,description,acceptance_criteria)
    VALUES(new.id,new.title,COALESCE(new.description,''),COALESCE(new.acceptance_criteria,''));
END;
-- Input changes preserve historical acceptance but reopen the current task.
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
 AND EXISTS(SELECT 1 FROM runtime_result_acceptances WHERE project_id=new.project_id AND task_id=new.id)
BEGIN UPDATE tasks SET status='pending',completed_at=NULL WHERE project_id=new.project_id AND id=new.id; END;
INSERT INTO schema_migrations(version,name) VALUES(35,'explicit_research_result_acceptance');
