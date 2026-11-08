-- Migration71: one materialized causal wave across dependency and plan context writers.
-- Completed records preserve why authority changed; no historical premises are invented.
CREATE TABLE runtime_context_causes (
 id INTEGER PRIMARY KEY,
 project_id INTEGER NOT NULL,
 task_id INTEGER NOT NULL,
 previous_version INTEGER NOT NULL CHECK(previous_version>=1),
 version INTEGER NOT NULL CHECK(version>previous_version),
 processing INTEGER NOT NULL DEFAULT 1 CHECK(processing IN (0,1)),
 created_at REAL NOT NULL,
 UNIQUE(task_id,version),
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TABLE runtime_context_affected (
 cause_id INTEGER NOT NULL REFERENCES runtime_context_causes(id) ON DELETE CASCADE,
 task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
 previous_version INTEGER NOT NULL CHECK(previous_version>=1),
 version INTEGER NOT NULL CHECK(version>previous_version),
 PRIMARY KEY(cause_id,task_id)
);
CREATE TRIGGER context_cause_completed_immutable BEFORE UPDATE ON runtime_context_causes
WHEN old.processing=0 OR new.id IS NOT old.id OR new.project_id IS NOT old.project_id
 OR new.task_id IS NOT old.task_id OR new.previous_version IS NOT old.previous_version
 OR new.version IS NOT old.version OR new.created_at IS NOT old.created_at
BEGIN SELECT RAISE(ABORT,'Completed context causes are immutable'); END;
CREATE TRIGGER context_affected_immutable BEFORE UPDATE ON runtime_context_affected
BEGIN SELECT RAISE(ABORT,'Original affected context versions are immutable'); END;
CREATE TABLE runtime_manual_prerequisites (
 run_id TEXT PRIMARY KEY REFERENCES runtime_runs(id) ON DELETE CASCADE,
 packet_json TEXT NOT NULL CHECK(json_valid(packet_json)),
 packet_sha256 TEXT NOT NULL CHECK(length(packet_sha256)=64),
 created_at REAL NOT NULL
);
CREATE TRIGGER manual_prerequisites_immutable BEFORE UPDATE ON runtime_manual_prerequisites
BEGIN SELECT RAISE(ABORT,'Original manual prerequisite material is immutable'); END;

-- Preserve the effective authorized-plan membership view, including reauthorizations.
CREATE VIEW runtime_context_causal_edges AS
 SELECT d.depends_on_task_id AS source_task_id,d.task_id AS target_task_id,
        NULL AS source_context_version
 FROM task_dependencies d WHERE d.dependency_type='blocks'
 UNION
 SELECT a.task_id,p.task_id,NULL FROM runtime_project_plan_tasks p
 JOIN runtime_project_plan_acceptances a ON a.id=p.acceptance_id
 UNION
 SELECT s.task_id,t.task_id,s.context_version FROM runtime_plan_context_members s
 JOIN runtime_plan_context_members t ON t.execution_id=s.execution_id;

DROP TRIGGER version_children_of_changed_plan;
DROP TRIGGER invalidate_authorized_plan_context;

CREATE TRIGGER apply_context_cause AFTER INSERT ON runtime_context_causes
BEGIN
 -- UNION visits each task once, so cycles and converging paths do not amplify revisions.
 -- Freeze membership before changing contexts; nested updates cannot re-evaluate this wave.
 INSERT INTO runtime_context_affected(cause_id,task_id,previous_version,version)
 WITH RECURSIVE affected(task_id) AS (
  SELECT new.task_id
  UNION
  SELECT e.target_task_id FROM affected a JOIN runtime_context_causal_edges e
   ON e.source_task_id=a.task_id
   JOIN tasks target ON target.id=e.target_task_id AND target.project_id=new.project_id
   WHERE e.source_context_version IS NULL OR e.source_context_version=
    CASE WHEN a.task_id=new.task_id THEN new.previous_version
     ELSE coalesce((SELECT version FROM task_contexts WHERE task_id=a.task_id),1) END
 )
 SELECT new.id,a.task_id,
  CASE WHEN a.task_id=new.task_id THEN new.previous_version ELSE coalesce(c.version,1) END,
  CASE WHEN a.task_id=new.task_id THEN new.version ELSE coalesce(c.version,1)+1 END
 FROM affected a LEFT JOIN task_contexts c ON c.task_id=a.task_id;

 UPDATE runtime_plan_executions SET status='paused',updated_at=new.created_at
 WHERE id IN(SELECT m.execution_id FROM runtime_plan_context_members m
  JOIN runtime_context_affected a ON a.task_id=m.task_id
   AND a.previous_version=m.context_version WHERE a.cause_id=new.id);

 INSERT INTO task_contexts(task_id,version)
 SELECT task_id,version FROM runtime_context_affected
 WHERE cause_id=new.id AND task_id!=new.task_id
 ON CONFLICT(task_id) DO UPDATE SET version=excluded.version;

 INSERT INTO runtime_context_revisions(project_id,task_id,version,statement,source_kind,source_reference,created_at)
 SELECT new.project_id,a.task_id,a.version,
  'Cambió una premisa de esta tarea: tarea '||new.task_id||', contexto '||new.previous_version||' → '||new.version||'. Revisa el trabajo anterior antes de iniciar otra solicitud.',
  'tool_evidence','context-cause:'||new.id||':task:'||new.task_id||':version:'||new.version,new.created_at
 FROM runtime_context_affected a WHERE a.cause_id=new.id AND a.task_id!=new.task_id;

 -- Root authority is retired by its existing owner-correction/metadata transaction.
 -- This wave retires every dependent before the same transaction can commit.
 UPDATE runtime_attempts SET status='reconciling' WHERE status='running' AND id IN(
  SELECT current_attempt_id FROM runtime_runs WHERE task_id IN(
   SELECT task_id FROM runtime_context_affected WHERE cause_id=new.id AND task_id!=new.task_id)
  AND status IN('queued','running','cancelling','reconciling','waiting_input','needs_review'));
 UPDATE runtime_runs SET
  status=CASE WHEN status IN('running','cancelling','reconciling') THEN 'reconciling' ELSE 'superseded' END,
  fence=fence+1,updated_at=new.created_at
 WHERE task_id IN(SELECT task_id FROM runtime_context_affected WHERE cause_id=new.id AND task_id!=new.task_id)
 AND status IN('queued','running','cancelling','reconciling','waiting_input','needs_review');
 UPDATE tool_grants SET revoked_at=coalesce(revoked_at,new.created_at)
 WHERE task_id IN(SELECT task_id FROM runtime_context_affected WHERE cause_id=new.id AND task_id!=new.task_id);
 UPDATE tasks SET status='pending',completed_at=NULL WHERE status='done' AND id IN(
  SELECT a.task_id FROM runtime_context_affected a WHERE a.cause_id=new.id AND a.task_id!=new.task_id
   AND EXISTS(SELECT 1 FROM runtime_runs r WHERE r.task_id=a.task_id
    AND r.status='accepted' AND r.context_version=a.previous_version));
 UPDATE user_requests SET status='expired' WHERE status='pending' AND id IN(
  SELECT q.request_id FROM runtime_question_links q JOIN runtime_runs r ON r.id=q.run_id
  WHERE r.task_id IN(SELECT task_id FROM runtime_context_affected WHERE cause_id=new.id AND task_id!=new.task_id));
 INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json)
 SELECT new.project_id,'context.dependencies_changed','runtime','task',a.task_id,
  json_object('schema_version',1,'cause_id',new.id,'source_task_id',new.task_id,
   'source_context_version',new.version,'previous_version',a.previous_version,
   'version',a.version,'source_kind','tool_evidence')
 FROM runtime_context_affected a WHERE a.cause_id=new.id AND a.task_id!=new.task_id;
 UPDATE runtime_context_causes SET processing=0 WHERE id=new.id;
END;

CREATE TRIGGER capture_context_update AFTER UPDATE OF version ON task_contexts
WHEN new.version>old.version AND NOT EXISTS(SELECT 1 FROM runtime_context_causes WHERE processing=1)
BEGIN
 INSERT INTO runtime_context_causes(project_id,task_id,previous_version,version,created_at)
 SELECT project_id,new.task_id,old.version,new.version,CAST(strftime('%s','now')AS REAL)
 FROM tasks WHERE id=new.task_id;
END;
CREATE TRIGGER capture_first_context_change AFTER INSERT ON task_contexts
WHEN new.version>1 AND NOT EXISTS(SELECT 1 FROM runtime_context_causes WHERE processing=1)
BEGIN
 INSERT INTO runtime_context_causes(project_id,task_id,previous_version,version,created_at)
 SELECT project_id,new.task_id,1,new.version,CAST(strftime('%s','now')AS REAL)
 FROM tasks WHERE id=new.task_id;
END;
INSERT INTO schema_migrations(version,name) VALUES(71,'causal_dependency_contexts');
