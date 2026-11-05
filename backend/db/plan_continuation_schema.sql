-- Migration50: immutable nonforking delivery lineage; preserve all original packet bytes.
CREATE TEMP TABLE plan_original_deliveries AS SELECT *FROM runtime_plan_deliveries;
CREATE TEMP TABLE plan_original_handoffs AS SELECT *FROM runtime_plan_handoffs;
DROP TRIGGER plan_delivery_origin_immutable;
DROP TRIGGER plan_handoff_immutable;
DROP TABLE runtime_plan_handoffs;
DROP TABLE runtime_plan_deliveries;
CREATE TABLE runtime_plan_deliveries (
 id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES runtime_plan_executions(id),
 task_id INTEGER NOT NULL REFERENCES tasks(id), operation_key TEXT NOT NULL UNIQUE,
 run_id TEXT UNIQUE REFERENCES runtime_runs(id), issue_json TEXT CHECK(issue_json IS NULL OR json_valid(issue_json)),
 predecessor_delivery_id TEXT UNIQUE REFERENCES runtime_plan_deliveries(id),
 continuation_json TEXT CHECK(continuation_json IS NULL OR json_valid(continuation_json)),
 CHECK((predecessor_delivery_id IS NULL)=(continuation_json IS NULL))
);
CREATE UNIQUE INDEX plan_original_delivery ON runtime_plan_deliveries(execution_id,task_id) WHERE predecessor_delivery_id IS NULL;
INSERT INTO runtime_plan_deliveries(id,execution_id,task_id,operation_key,run_id,issue_json)
 SELECT id,execution_id,task_id,operation_key,run_id,issue_json FROM plan_original_deliveries;
CREATE TABLE runtime_plan_handoffs (
 delivery_id TEXT PRIMARY KEY REFERENCES runtime_plan_deliveries(id),
 packet_json TEXT NOT NULL CHECK(json_valid(packet_json)),
 packet_sha256 TEXT NOT NULL CHECK(length(packet_sha256)=64), created_at REAL NOT NULL
);
INSERT INTO runtime_plan_handoffs SELECT *FROM plan_original_handoffs;
DROP TABLE plan_original_handoffs;
DROP TABLE plan_original_deliveries;
CREATE TRIGGER plan_handoff_immutable BEFORE UPDATE ON runtime_plan_handoffs
BEGIN SELECT RAISE(ABORT,'Original causal deliveries are immutable'); END;
CREATE TRIGGER plan_delivery_origin_immutable BEFORE UPDATE ON runtime_plan_deliveries
WHEN new.id IS NOT old.id OR new.execution_id IS NOT old.execution_id
 OR new.task_id IS NOT old.task_id OR new.operation_key IS NOT old.operation_key
 OR new.predecessor_delivery_id IS NOT old.predecessor_delivery_id OR new.continuation_json IS NOT old.continuation_json
 OR (old.run_id IS NOT NULL AND new.run_id IS NOT old.run_id)
BEGIN SELECT RAISE(ABORT,'Original delivery identity cannot be replaced'); END;
CREATE TRIGGER plan_successor_scope BEFORE INSERT ON runtime_plan_deliveries
WHEN new.predecessor_delivery_id IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM runtime_plan_deliveries p WHERE p.id=new.predecessor_delivery_id
 AND p.execution_id=new.execution_id AND p.task_id=new.task_id AND p.run_id IS NOT NULL)
BEGIN SELECT RAISE(ABORT,'Successor must preserve the original delivery scope'); END;
INSERT INTO schema_migrations(version,name) VALUES(50,'explicit_plan_delivery_continuations');
