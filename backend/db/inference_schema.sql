-- Migration 21: dispatch intent and conservative lifetime project work budgets.
CREATE TABLE runtime_project_budgets (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    turn_limit INTEGER NOT NULL CHECK(turn_limit>0),
    token_limit INTEGER NOT NULL CHECK(token_limit>0)
);
CREATE TABLE runtime_inference_dispatches (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace TEXT NOT NULL,
    catalog_hash TEXT NOT NULL,
    runtime_version TEXT NOT NULL,
    limits_json TEXT NOT NULL CHECK(json_valid(limits_json)),
    token_ceiling INTEGER NOT NULL CHECK(token_ceiling>0),
    status TEXT NOT NULL CHECK(status IN ('reserved','settled','unknown')),
    observed_tokens INTEGER CHECK(observed_tokens IS NULL OR observed_tokens>=0),
    native_status TEXT,
    created_at REAL NOT NULL,
    settled_at REAL
);
CREATE INDEX idx_inference_project ON runtime_inference_dispatches(project_id);
INSERT INTO schema_migrations(version,name) VALUES(21,'durable_inference_dispatch');
