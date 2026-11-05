-- Migration51: immutable owner revisions of one execution, preserving its original intent.
CREATE TABLE runtime_plan_execution_revisions (
 execution_id TEXT NOT NULL REFERENCES runtime_plan_executions(id),
 revision INTEGER NOT NULL CHECK(revision>0), operation_key TEXT NOT NULL,
 manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json)),
 manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
 snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),
 snapshot_sha256 TEXT NOT NULL CHECK(length(snapshot_sha256)=64), created_at REAL NOT NULL,
 PRIMARY KEY(execution_id,revision), UNIQUE(execution_id,operation_key)
);
CREATE TRIGGER plan_revision_immutable BEFORE UPDATE ON runtime_plan_execution_revisions
BEGIN SELECT RAISE(ABORT,'Owner graph authorization revisions are immutable'); END;
CREATE TRIGGER plan_revision_sequence BEFORE INSERT ON runtime_plan_execution_revisions
WHEN new.revision!=coalesce((SELECT max(revision)FROM runtime_plan_execution_revisions WHERE execution_id=new.execution_id),0)+1
BEGIN SELECT RAISE(ABORT,'Graph authorization revisions cannot fork or skip history'); END;
CREATE VIEW runtime_plan_effective_executions AS
 SELECT e.id,e.project_id,e.plan_run_id,e.acceptance_id,
 coalesce(r.operation_key,e.operation_key)AS operation_key,
 coalesce(r.manifest_sha256,e.manifest_sha256)AS manifest_sha256,
 coalesce(r.manifest_json,e.manifest_json)AS manifest_json,
 e.status,e.created_at,e.updated_at,coalesce(r.revision,0)AS authorization_revision,
 r.snapshot_json AS authorization_snapshot_json,e.operation_key AS original_operation_key,
 e.manifest_sha256 AS original_manifest_sha256
 FROM runtime_plan_executions e LEFT JOIN runtime_plan_execution_revisions r
 ON r.execution_id=e.id AND r.revision=(SELECT max(revision)FROM runtime_plan_execution_revisions WHERE execution_id=e.id);
DROP VIEW runtime_plan_context_members;
CREATE VIEW runtime_plan_context_members AS
 SELECT e.id AS execution_id,e.project_id,CAST(json_extract(j.value,'$.task_id')AS INTEGER)AS task_id,
 CAST(json_extract(j.value,'$.context_version')AS INTEGER)AS context_version
 FROM runtime_plan_effective_executions e,json_each(e.manifest_json,'$.tasks')j;
DROP TRIGGER plan_successor_scope;
CREATE TRIGGER plan_successor_scope BEFORE INSERT ON runtime_plan_deliveries
WHEN new.predecessor_delivery_id IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM runtime_plan_deliveries p WHERE p.id=new.predecessor_delivery_id
 AND p.execution_id=new.execution_id AND p.task_id=new.task_id AND (
 p.run_id IS NOT NULL OR (json_extract(new.continuation_json,'$.kind')='graph_reauthorization'
 AND EXISTS(SELECT 1 FROM runtime_plan_execution_revisions r WHERE r.execution_id=new.execution_id
 AND r.revision=json_extract(new.continuation_json,'$.authorization_revision')))))
BEGIN SELECT RAISE(ABORT,'Successor must preserve original scope and explicit graph authorization'); END;
INSERT INTO schema_migrations(version,name)VALUES(51,'explicit_corrected_graph_reauthorization');
