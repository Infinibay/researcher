-- Migration 29: every task input writer crosses the same transactional boundary.
-- A metadata change is an observed database write, never inferred user testimony.
CREATE TABLE runtime_task_input_changes (
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    version INTEGER NOT NULL CHECK(version>=2),
    before_json TEXT NOT NULL CHECK(json_valid(before_json)),
    after_json TEXT NOT NULL CHECK(json_valid(after_json)),
    recorded_at REAL NOT NULL,
    PRIMARY KEY(project_id,task_id,version),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TRIGGER immutable_task_input_change BEFORE UPDATE ON runtime_task_input_changes
    BEGIN SELECT RAISE(ABORT,'Task input history is immutable'); END;

CREATE TRIGGER version_task_inputs AFTER UPDATE OF
    title,description,type,acceptance_criteria,context_json,priority,
    estimated_complexity,branch_name,assigned_to,reviewer,epic_id,milestone_id,parent_task_id
    ON tasks
    WHEN old.title IS NOT new.title OR old.description IS NOT new.description
      OR old.type IS NOT new.type OR old.acceptance_criteria IS NOT new.acceptance_criteria
      OR old.context_json IS NOT new.context_json OR old.priority IS NOT new.priority
      OR old.estimated_complexity IS NOT new.estimated_complexity
      OR old.branch_name IS NOT new.branch_name OR old.assigned_to IS NOT new.assigned_to
      OR old.reviewer IS NOT new.reviewer OR old.epic_id IS NOT new.epic_id
      OR old.milestone_id IS NOT new.milestone_id OR old.parent_task_id IS NOT new.parent_task_id
    BEGIN
      INSERT INTO task_contexts(task_id,version) VALUES(new.id,2)
          ON CONFLICT(task_id) DO UPDATE SET version=version+1;
      INSERT INTO runtime_task_input_changes(project_id,task_id,version,before_json,after_json,recorded_at)
          VALUES(new.project_id,new.id,(SELECT version FROM task_contexts WHERE task_id=new.id),
            json_object('title',old.title,'description',old.description,'type',old.type,
              'acceptance_criteria',old.acceptance_criteria,'context_json',old.context_json,
              'priority',old.priority,'estimated_complexity',old.estimated_complexity,
              'branch_name',old.branch_name,'assigned_to',old.assigned_to,'reviewer',old.reviewer,
              'epic_id',old.epic_id,'milestone_id',old.milestone_id,'parent_task_id',old.parent_task_id),
            json_object('title',new.title,'description',new.description,'type',new.type,
              'acceptance_criteria',new.acceptance_criteria,'context_json',new.context_json,
              'priority',new.priority,'estimated_complexity',new.estimated_complexity,
              'branch_name',new.branch_name,'assigned_to',new.assigned_to,'reviewer',new.reviewer,
              'epic_id',new.epic_id,'milestone_id',new.milestone_id,'parent_task_id',new.parent_task_id),
            CAST(strftime('%s','now') AS REAL));
      UPDATE runtime_attempts SET status='reconciling' WHERE status='running' AND id IN (
          SELECT current_attempt_id FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id
          AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review'));
      UPDATE runtime_runs SET
          status=CASE WHEN status IN ('running','cancelling','reconciling') THEN 'reconciling' ELSE 'superseded' END,
          fence=fence+1,updated_at=CAST(strftime('%s','now') AS REAL)
          WHERE project_id=new.project_id AND task_id=new.id
          AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review');
      UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,CAST(strftime('%s','now') AS REAL))
          WHERE project_id=new.project_id AND task_id=new.id;
      UPDATE user_requests SET status='expired' WHERE status='pending' AND id IN (
          SELECT q.request_id FROM runtime_question_links q JOIN runtime_runs r ON r.id=q.run_id
          WHERE q.project_id=new.project_id AND r.task_id=new.id);
      INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json)
          VALUES(new.project_id,'context.task_inputs_changed','runtime','task',new.id,
            json_object('schema_version',1,'version',(SELECT version FROM task_contexts WHERE task_id=new.id),
              'source_kind','task_metadata','actor',NULL));
    END;
INSERT INTO schema_migrations(version,name) VALUES(29,'versioned_task_inputs');
