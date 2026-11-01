-- Migration 30. Historical dispatches acquire no invented input or understanding.
CREATE TABLE runtime_input_snapshots (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_inference_dispatches(attempt_id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL CHECK(schema_version=1),
    input_text TEXT NOT NULL CHECK(json_valid(input_text)),
    input_sha256 TEXT NOT NULL CHECK(length(input_sha256)=64),
    developer_instructions TEXT NOT NULL,
    instructions_sha256 TEXT NOT NULL CHECK(length(instructions_sha256)=64),
    business_catalog_json TEXT NOT NULL CHECK(json_valid(business_catalog_json)),
    created_at REAL NOT NULL
);
CREATE TRIGGER immutable_runtime_input BEFORE UPDATE ON runtime_input_snapshots
    BEGIN SELECT RAISE(ABORT,'Runtime input snapshot is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(30,'frozen_host_input_and_conversation');
