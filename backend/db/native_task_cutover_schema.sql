-- Migration54: retire pre-admission legacy claims/completion without rewriting historical work.
-- After admission, native_task_done_requires_acceptance keeps the existing exact
-- code/result/project-plan owner proof. Research/investigation retain their guards.
CREATE TRIGGER task_cutover_claim_requires_native_run BEFORE UPDATE OF status ON tasks
WHEN new.type IN ('code','bug_fix','test','design','integrate','documentation','experimentation','optimization','review','plan')
 AND new.status='in_progress' AND old.status IS NOT 'in_progress'
 AND NOT EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id)
BEGIN SELECT RAISE(ABORT,'Task execution requires native owner admission'); END;
CREATE TRIGGER task_cutover_done_requires_native_run BEFORE UPDATE OF status ON tasks
WHEN new.type IN ('code','bug_fix','test','design','integrate','documentation','experimentation','optimization','review','plan')
 AND new.status='done' AND old.status IS NOT 'done'
 AND NOT EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id)
BEGIN SELECT RAISE(ABORT,'Task completion requires native owner acceptance'); END;
INSERT INTO schema_migrations(version,name)VALUES(54,'native_task_flow_cutover');
