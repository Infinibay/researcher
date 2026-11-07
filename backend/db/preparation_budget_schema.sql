-- Migration64: admit each attempt before preparing Ken or the native session.
CREATE TABLE runtime_preparation_reservations (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    limits_json TEXT NOT NULL CHECK(json_valid(limits_json)),
    token_ceiling INTEGER NOT NULL CHECK(token_ceiling>0),
    created_at REAL NOT NULL
);
CREATE INDEX idx_preparation_project ON runtime_preparation_reservations(project_id);
CREATE TRIGGER runtime_preparation_immutable
BEFORE UPDATE ON runtime_preparation_reservations BEGIN
    SELECT RAISE(ABORT,'Preparation reservation is immutable');
END;
INSERT INTO schema_migrations(version,name) VALUES(64,'preparation_budget');
