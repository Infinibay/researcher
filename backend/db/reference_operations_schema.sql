-- Migration66: original attachment intents survive filesystem/SQLite boundaries.
CREATE TABLE reference_file_operations (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    operation_key TEXT NOT NULL CHECK(length(operation_key) BETWEEN 1 AND 128),
    kind TEXT NOT NULL CHECK(kind IN ('upload','delete')),
    state TEXT NOT NULL CHECK(state IN ('pending','published','deleted','abandoned')),
    request_json TEXT NOT NULL CHECK(json_valid(request_json)),
    relative_path TEXT NOT NULL,
    reference_id INTEGER,
    receipt_json TEXT CHECK(receipt_json IS NULL OR json_valid(receipt_json)),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(project_id,operation_key),
    CHECK((state='published' AND kind='upload' AND reference_id IS NOT NULL AND receipt_json IS NOT NULL)
       OR (state='deleted' AND kind='delete') OR state IN ('pending','abandoned'))
);
CREATE INDEX reference_operations_project_history ON reference_file_operations(project_id,created_at DESC,operation_key);
CREATE TRIGGER reference_operation_intent_immutable BEFORE UPDATE ON reference_file_operations
WHEN old.project_id!=new.project_id OR old.operation_key!=new.operation_key
  OR old.kind!=new.kind OR old.request_json!=new.request_json OR old.relative_path!=new.relative_path
  OR old.created_at!=new.created_at OR old.state!='pending'
BEGIN SELECT RAISE(ABORT,'Reference operation intent or completed receipt is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(66,'durable_reference_file_operations');
