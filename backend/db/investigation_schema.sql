-- Migration52: exploratory summaries retain typed scope/area evidence alongside ordinary report drafts.
CREATE TABLE research_investigation_summaries (
 artifact_id INTEGER PRIMARY KEY REFERENCES research_reports(artifact_id) ON DELETE CASCADE,
 project_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
 context_version INTEGER NOT NULL CHECK(context_version>0),
 producer_grant_id TEXT NOT NULL REFERENCES tool_grants(id), operation_key TEXT NOT NULL,
 summary_json TEXT NOT NULL CHECK(json_valid(summary_json)),
 summary_sha256 TEXT NOT NULL CHECK(length(summary_sha256)=64),
 FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id),
 UNIQUE(project_id,task_id,operation_key)
);
CREATE TRIGGER investigation_summary_immutable BEFORE UPDATE ON research_investigation_summaries
BEGIN SELECT RAISE(ABORT,'Original exploratory summary is immutable'); END;
-- Block pre-admission legacy claims and completion; historical done rows remain historical.
CREATE TRIGGER investigation_claim_requires_native_run BEFORE UPDATE OF status ON tasks
WHEN new.type='investigation' AND new.status='in_progress' AND old.status IS NOT 'in_progress'
 AND NOT EXISTS(SELECT 1 FROM runtime_runs WHERE project_id=new.project_id AND task_id=new.id)
BEGIN SELECT RAISE(ABORT,'Investigation requires native owner admission'); END;
CREATE TRIGGER investigation_done_requires_owner_acceptance BEFORE UPDATE OF status ON tasks
WHEN new.type='investigation' AND new.status='done' AND old.status IS NOT 'done'
 AND NOT EXISTS(
   SELECT 1 FROM runtime_result_acceptances a
   JOIN runtime_result_proposals p ON p.id=a.proposal_id
   JOIN runtime_runs r ON r.id=a.run_id
   WHERE a.project_id=new.project_id AND a.task_id=new.id AND r.status='accepted'
   AND p.context_version=coalesce((SELECT version FROM task_contexts WHERE task_id=new.id),1))
BEGIN SELECT RAISE(ABORT,'Investigation completion requires explicit owner acceptance'); END;
INSERT INTO schema_migrations(version,name)VALUES(52,'native_exploratory_investigation');
