-- Migration 36: typed development/code-review execution, before writable controller integration.
-- SQLite expands the column in place; the runtime_runs table identity and child FK targets remain.
DROP INDEX idx_runtime_active_task;
ALTER TABLE runtime_runs ADD COLUMN next_execution_kind TEXT NOT NULL DEFAULT 'research'
    CHECK(next_execution_kind IN ('research','finding_review','development','code_review'));
UPDATE runtime_runs SET next_execution_kind=execution_kind;
ALTER TABLE runtime_runs DROP COLUMN execution_kind;
ALTER TABLE runtime_runs RENAME COLUMN next_execution_kind TO execution_kind;
-- A task has one productive author and one independent review slot, not one per arbitrary role string.
CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(
    project_id,task_id,
    CASE WHEN execution_kind IN ('finding_review','code_review') THEN 'review' ELSE 'author' END
) WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review');
INSERT INTO schema_migrations(version,name) VALUES(36,'typed_native_development_execution');
