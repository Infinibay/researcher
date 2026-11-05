-- Migration47: structured native planning and explicit owner graph expansion.
CREATE TABLE runtime_project_plan_requests (
 run_id TEXT PRIMARY KEY REFERENCES runtime_runs(id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL,task_id INTEGER NOT NULL,context_version INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),snapshot_sha256 TEXT NOT NULL,
 created_at REAL NOT NULL,FOREIGN KEY(project_id,task_id)REFERENCES tasks(project_id,id)
);
CREATE TRIGGER project_plan_request_immutable BEFORE UPDATE ON runtime_project_plan_requests
 BEGIN SELECT RAISE(ABORT,'Original planning inputs are immutable');END;
CREATE TABLE runtime_project_plan_proposals (
 id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runtime_project_plan_requests(run_id) ON DELETE CASCADE,
 attempt_id TEXT NOT NULL UNIQUE REFERENCES runtime_attempts(id),operation_key TEXT NOT NULL,
 proposal_sha256 TEXT NOT NULL UNIQUE,proposal_json TEXT NOT NULL CHECK(json_valid(proposal_json)),
 created_at REAL NOT NULL,UNIQUE(run_id,operation_key)
);
CREATE TRIGGER project_plan_proposal_immutable BEFORE UPDATE ON runtime_project_plan_proposals
 BEGIN SELECT RAISE(ABORT,'Planning proposals are immutable');END;
CREATE TABLE runtime_project_plan_acceptances (
 id TEXT PRIMARY KEY,project_id INTEGER NOT NULL,task_id INTEGER NOT NULL,
 run_id TEXT NOT NULL UNIQUE REFERENCES runtime_project_plan_requests(run_id),
 proposal_id TEXT NOT NULL UNIQUE REFERENCES runtime_project_plan_proposals(id),
 context_version INTEGER NOT NULL,operation_key TEXT NOT NULL,
 result_json TEXT NOT NULL CHECK(json_valid(result_json)),created_at REAL NOT NULL,
 UNIQUE(project_id,operation_key),FOREIGN KEY(project_id,task_id)REFERENCES tasks(project_id,id)
);
CREATE TRIGGER project_plan_acceptance_immutable BEFORE UPDATE ON runtime_project_plan_acceptances
 BEGIN SELECT RAISE(ABORT,'Plan owner decisions are immutable');END;
CREATE TABLE runtime_project_plan_tasks (
 task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
 acceptance_id TEXT NOT NULL REFERENCES runtime_project_plan_acceptances(id),
 local_key TEXT NOT NULL,UNIQUE(acceptance_id,local_key)
);
CREATE TABLE runtime_project_plan_starts (
 project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,operation_key TEXT NOT NULL,
 task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id),
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),binding_json TEXT NOT NULL CHECK(json_valid(binding_json)),
 project_json TEXT NOT NULL CHECK(json_valid(project_json)),created_at REAL NOT NULL,
 PRIMARY KEY(project_id,operation_key)
);
CREATE TRIGGER project_plan_start_immutable BEFORE UPDATE ON runtime_project_plan_starts
 BEGIN SELECT RAISE(ABORT,'Original planning starts are immutable');END;
CREATE TRIGGER version_project_planning_inputs AFTER UPDATE OF name,description ON projects
 WHEN old.name IS NOT new.name OR old.description IS NOT new.description
 BEGIN
  UPDATE tasks SET context_json=json_set(CASE WHEN json_valid(context_json) THEN context_json ELSE '{}'END,
    '$.project_metadata',json_object('name',new.name,'description',new.description))
   WHERE project_id=new.id AND (created_by='native-project-planner'OR id IN(
    SELECT task_id FROM runtime_project_plan_requests WHERE project_id=new.id));
 END;
CREATE TRIGGER version_children_of_changed_plan AFTER UPDATE OF version ON task_contexts
 WHEN new.version IS NOT old.version AND EXISTS(
  SELECT 1 FROM runtime_project_plan_acceptances WHERE task_id=new.task_id)
 BEGIN
  INSERT INTO task_contexts(task_id,version) SELECT p.task_id,2 FROM runtime_project_plan_tasks p
   JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id WHERE a.task_id=new.task_id
   ON CONFLICT(task_id)DO UPDATE SET version=version+1;
  INSERT INTO runtime_context_revisions(project_id,task_id,version,statement,source_kind,source_reference,created_at)
   SELECT a.project_id,p.task_id,c.version,
    'Cambió el contexto del plan aceptado; su autorización anterior ya no permite iniciar este trabajo.',
    'tool_evidence','project-plan:'||new.task_id||':context:'||new.version,CAST(strftime('%s','now')AS REAL)
   FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id
   JOIN task_contexts c ON c.task_id=p.task_id WHERE a.task_id=new.task_id;
  UPDATE runtime_attempts SET status='reconciling'WHERE status='running'AND id IN(
   SELECT current_attempt_id FROM runtime_runs WHERE task_id IN(SELECT p.task_id FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id WHERE a.task_id=new.task_id)
   AND status IN('queued','running','cancelling','reconciling','waiting_input','needs_review'));
  UPDATE runtime_runs SET status=CASE WHEN status IN('running','cancelling','reconciling')THEN'reconciling'ELSE'superseded'END,
   fence=fence+1,updated_at=CAST(strftime('%s','now')AS REAL)
   WHERE task_id IN(SELECT p.task_id FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id WHERE a.task_id=new.task_id)AND status IN('queued','running','cancelling','reconciling','waiting_input','needs_review');
  UPDATE tool_grants SET revoked_at=coalesce(revoked_at,CAST(strftime('%s','now')AS REAL))WHERE task_id IN(SELECT p.task_id FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id WHERE a.task_id=new.task_id);
  UPDATE user_requests SET status='expired'WHERE status='pending'AND id IN(
   SELECT q.request_id FROM runtime_question_links q JOIN runtime_runs r ON r.id=q.run_id WHERE r.task_id IN(SELECT p.task_id FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id WHERE a.task_id=new.task_id));
  INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json)
   SELECT a.project_id,'context.plan_changed','runtime','task',p.task_id,
   json_object('schema_version',1,'version',c.version,'plan_task_id',new.task_id,'plan_context_version',new.version,'source_kind','tool_evidence')
   FROM runtime_project_plan_tasks p JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id
   JOIN task_contexts c ON c.task_id=p.task_id WHERE a.task_id=new.task_id;
 END;
DROP TRIGGER native_task_done_requires_acceptance;
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
 AND NOT EXISTS(
   SELECT 1 FROM runtime_project_plan_acceptances a
   JOIN runtime_project_plan_proposals p ON p.id=a.proposal_id
   JOIN runtime_runs r ON r.id=a.run_id
   WHERE a.project_id=new.project_id AND a.task_id=new.id AND r.status='accepted'
     AND r.current_attempt_id=p.attempt_id AND a.context_version=coalesce(
       (SELECT version FROM task_contexts WHERE task_id=new.id),1))
BEGIN SELECT RAISE(ABORT,'Native task completion requires explicit owner acceptance'); END;
CREATE TRIGGER planned_work_requires_native_result BEFORE UPDATE OF status ON tasks
 WHEN new.status='done'AND old.status IS NOT'done'
 AND EXISTS(SELECT 1 FROM runtime_project_plan_tasks WHERE task_id=new.id)
 AND NOT EXISTS(SELECT 1 FROM runtime_runs r WHERE r.project_id=new.project_id AND r.task_id=new.id
  AND r.status='accepted'AND r.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=new.id),1))
 BEGIN SELECT RAISE(ABORT,'Planned work requires a current native owner acceptance');END;
INSERT INTO schema_migrations(version,name)VALUES(47,'native_project_planning');
