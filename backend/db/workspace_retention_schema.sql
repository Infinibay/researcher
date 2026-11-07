-- Migration68: explicit owner retention preserves original attempt/history identities.
CREATE TABLE workspace_retention (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_development_workspaces(attempt_id) ON DELETE RESTRICT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    task_id INTEGER NOT NULL,
    original_json TEXT NOT NULL CHECK(json_valid(original_json)),
    state TEXT NOT NULL CHECK(state IN ('quarantined','retained','removing','removed')),
    archive_id TEXT NOT NULL,
    archive_sha256 TEXT,
    manifest_json TEXT CHECK(manifest_json IS NULL OR json_valid(manifest_json)),
    retain_until REAL NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE RESTRICT
);
CREATE TABLE workspace_retention_operations (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    attempt_id TEXT NOT NULL REFERENCES workspace_retention(attempt_id) ON DELETE RESTRICT,
    operation_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('archive','remove','restore')),
    intent_json TEXT NOT NULL CHECK(json_valid(intent_json)),
    work_json TEXT CHECK(work_json IS NULL OR json_valid(work_json)),
    state TEXT NOT NULL CHECK(state IN ('pending','completed','superseded')),
    issue TEXT,
    receipt_json TEXT CHECK(receipt_json IS NULL OR json_valid(receipt_json)),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(project_id,operation_key)
);
CREATE INDEX workspace_retention_project ON workspace_retention(project_id,created_at);
CREATE INDEX workspace_retention_operations_project ON workspace_retention_operations(project_id,created_at);
CREATE TRIGGER retention_origin_immutable BEFORE UPDATE ON workspace_retention
WHEN NEW.attempt_id IS NOT OLD.attempt_id OR NEW.project_id IS NOT OLD.project_id OR NEW.task_id IS NOT OLD.task_id
 OR NEW.original_json IS NOT OLD.original_json OR NEW.created_at IS NOT OLD.created_at
BEGIN SELECT RAISE(ABORT,'Retention origin is immutable'); END;
CREATE TRIGGER retention_intent_immutable BEFORE UPDATE ON workspace_retention_operations
WHEN NEW.id IS NOT OLD.id OR NEW.project_id IS NOT OLD.project_id OR NEW.attempt_id IS NOT OLD.attempt_id
 OR NEW.operation_key IS NOT OLD.operation_key OR NEW.kind IS NOT OLD.kind OR NEW.intent_json IS NOT OLD.intent_json
 OR NEW.created_at IS NOT OLD.created_at OR (OLD.state IN ('completed','superseded') AND
 (NEW.state IS NOT OLD.state OR NEW.receipt_json IS NOT OLD.receipt_json OR NEW.work_json IS NOT OLD.work_json))
BEGIN SELECT RAISE(ABORT,'Retention intent or completed receipt is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(68,'explicit_workspace_retention');
