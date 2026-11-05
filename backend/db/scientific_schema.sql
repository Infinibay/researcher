-- Migration53: scientific research now uses existing native evidence/review/owner acceptance, including before first admission.
CREATE TRIGGER research_claim_requires_native_run BEFORE UPDATE OF status ON tasks
WHEN new.type='research' AND new.status='in_progress' AND old.status IS NOT 'in_progress'
 AND NOT EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id)
BEGIN SELECT RAISE(ABORT,'Scientific research requires native owner admission'); END;
CREATE TRIGGER research_done_requires_owner_acceptance BEFORE UPDATE OF status ON tasks
WHEN new.type='research' AND new.status='done' AND old.status IS NOT 'done'
 AND NOT EXISTS(
   SELECT 1 FROM runtime_result_acceptances a
   JOIN runtime_result_proposals p ON p.id=a.proposal_id
   JOIN runtime_runs r ON r.id=a.run_id
   WHERE a.project_id=new.project_id AND a.task_id=new.id AND r.status='accepted'
   AND p.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=new.id),1))
BEGIN SELECT RAISE(ABORT,'Scientific research completion requires explicit owner acceptance'); END;
INSERT INTO schema_migrations(version,name)VALUES(53,'native_scientific_research_ownership');
