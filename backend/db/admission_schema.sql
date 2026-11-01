-- Migration 28: immutable repository/workspace admission and observable startup.
ALTER TABLE runtime_runs ADD COLUMN issue_json TEXT CHECK(issue_json IS NULL OR json_valid(issue_json));
CREATE TABLE runtime_workspace_bindings (
    run_id TEXT PRIMARY KEY REFERENCES runtime_runs(id) ON DELETE CASCADE,
    repository_id INTEGER NOT NULL,
    repository_name TEXT NOT NULL,
    requested_repository_id INTEGER,
    registration_path TEXT NOT NULL,
    workspace TEXT NOT NULL,
    device INTEGER NOT NULL,
    inode INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE TRIGGER immutable_workspace_binding BEFORE UPDATE ON runtime_workspace_bindings
    BEGIN SELECT RAISE(ABORT,'Workspace admission is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(28,'durable_workspace_admission_and_start_issues');
