-- Migration48: explicit owner execution intent and immutable causal task deliveries.
CREATE TABLE runtime_plan_executions (
 id TEXT PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
 plan_run_id TEXT NOT NULL UNIQUE REFERENCES runtime_project_plan_requests(run_id),
 acceptance_id TEXT NOT NULL REFERENCES runtime_project_plan_acceptances(id),
 operation_key TEXT NOT NULL, manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
 manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json)),
 status TEXT NOT NULL CHECK(status IN ('active','paused')),
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE runtime_plan_deliveries (
 id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES runtime_plan_executions(id),
 task_id INTEGER NOT NULL REFERENCES tasks(id),
 operation_key TEXT NOT NULL UNIQUE,
 run_id TEXT UNIQUE REFERENCES runtime_runs(id), issue_json TEXT CHECK(issue_json IS NULL OR json_valid(issue_json)),
 UNIQUE(execution_id,task_id)
);
CREATE TABLE runtime_plan_handoffs (
 delivery_id TEXT PRIMARY KEY REFERENCES runtime_plan_deliveries(id),
 packet_json TEXT NOT NULL CHECK(json_valid(packet_json)),
 packet_sha256 TEXT NOT NULL CHECK(length(packet_sha256)=64), created_at REAL NOT NULL
);
CREATE TRIGGER plan_handoff_immutable BEFORE UPDATE ON runtime_plan_handoffs
BEGIN SELECT RAISE(ABORT,'Original causal deliveries are immutable'); END;
CREATE TRIGGER plan_delivery_origin_immutable BEFORE UPDATE ON runtime_plan_deliveries
WHEN new.id IS NOT old.id OR new.execution_id IS NOT old.execution_id
 OR new.task_id IS NOT old.task_id OR new.operation_key IS NOT old.operation_key
 OR (old.run_id IS NOT NULL AND new.run_id IS NOT old.run_id)
BEGIN SELECT RAISE(ABORT,'Original delivery identity cannot be replaced'); END;
CREATE TRIGGER plan_execution_origin_immutable BEFORE UPDATE ON runtime_plan_executions
WHEN new.id IS NOT old.id OR new.project_id IS NOT old.project_id
 OR new.plan_run_id IS NOT old.plan_run_id OR new.acceptance_id IS NOT old.acceptance_id
 OR new.operation_key IS NOT old.operation_key OR new.manifest_sha256 IS NOT old.manifest_sha256
 OR new.manifest_json IS NOT old.manifest_json OR new.created_at IS NOT old.created_at
BEGIN SELECT RAISE(ABORT,'Original owner execution intent is immutable'); END;
-- Conservative scope: a changed premise invalidates this authorized graph, not
-- other projects. Match the original version, so nested updates cannot recurse
-- into another invalidation of the same manifest even with recursive_triggers on.
CREATE VIEW runtime_plan_context_members AS
 SELECT e.id AS execution_id,e.project_id,CAST(json_extract(j.value,'$.task_id')AS INTEGER)AS task_id,
 CAST(json_extract(j.value,'$.context_version')AS INTEGER)AS context_version
 FROM runtime_plan_executions e,json_each(e.manifest_json,'$.tasks')j;
CREATE TRIGGER invalidate_authorized_plan_context AFTER UPDATE OF version ON task_contexts
WHEN new.version!=old.version AND EXISTS(
 SELECT 1 FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version)
BEGIN
 UPDATE runtime_plan_executions SET status='paused',updated_at=CAST(strftime('%s','now')AS REAL)
 WHERE id IN(SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version);
 UPDATE task_contexts SET version=version+1 WHERE task_id!=new.task_id AND task_id IN(
 SELECT task_id FROM runtime_plan_context_members WHERE execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version));
 INSERT INTO runtime_context_revisions(project_id,task_id,version,statement,source_kind,source_reference,created_at)
 SELECT DISTINCT m.project_id,m.task_id,c.version,'Another premise in this authorized plan changed. Reconcile the original execution before new work.',
 'tool_evidence','plan-execution:source-task:'||new.task_id||':context:'||new.version,CAST(strftime('%s','now')AS REAL)
 FROM runtime_plan_context_members m JOIN task_contexts c ON c.task_id=m.task_id
 WHERE m.task_id!=new.task_id AND m.execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version);
 UPDATE runtime_attempts SET status='reconciling' WHERE status='running' AND id IN(
 SELECT current_attempt_id FROM runtime_runs WHERE task_id IN(SELECT task_id FROM runtime_plan_context_members WHERE execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version))
 AND status IN('queued','running','cancelling','reconciling','waiting_input','needs_review'));
 UPDATE runtime_runs SET status=CASE WHEN status IN('running','cancelling','reconciling')THEN'reconciling'ELSE'superseded'END,
 fence=fence+1,updated_at=CAST(strftime('%s','now')AS REAL)
 WHERE task_id IN(SELECT task_id FROM runtime_plan_context_members WHERE execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version))
 AND status IN('queued','running','cancelling','reconciling','waiting_input','needs_review');
 UPDATE tool_grants SET revoked_at=coalesce(revoked_at,CAST(strftime('%s','now')AS REAL))WHERE task_id IN(
 SELECT task_id FROM runtime_plan_context_members WHERE execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version));
 UPDATE tasks SET status='pending',completed_at=NULL WHERE status='done' AND id!=new.task_id AND id IN(
 SELECT task_id FROM runtime_plan_context_members WHERE execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version));
 UPDATE user_requests SET status='expired' WHERE status='pending' AND id IN(
 SELECT q.request_id FROM runtime_question_links q JOIN runtime_runs r ON r.id=q.run_id WHERE r.task_id IN(
 SELECT task_id FROM runtime_plan_context_members WHERE execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version)));
 INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json)
 SELECT DISTINCT m.project_id,'context.execution_premise_changed','runtime','task',m.task_id,
 json_object('schema_version',1,'source_task_id',new.task_id,'source_context_version',new.version,'version',c.version,'source_kind','tool_evidence')
 FROM runtime_plan_context_members m JOIN task_contexts c ON c.task_id=m.task_id WHERE m.execution_id IN(
 SELECT execution_id FROM runtime_plan_context_members WHERE task_id=new.task_id AND context_version=old.version);
END;
INSERT INTO schema_migrations(version,name) VALUES(48,'accepted_plan_execution_deliveries');
