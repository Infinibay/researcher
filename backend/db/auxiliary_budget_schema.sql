-- Migration61: local workers reserve capacity before execution and retain original results/unknown usage.
CREATE TABLE runtime_auxiliary_policies (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    operation_limit INTEGER NOT NULL CHECK(operation_limit>0),
    cpu_ms_limit INTEGER NOT NULL CHECK(cpu_ms_limit>0)
);
CREATE TABLE runtime_auxiliary_work (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    input_bytes INTEGER NOT NULL CHECK(input_bytes>=0),
    attempt_id TEXT,
    grant_id TEXT,
    cpu_ceiling_ms INTEGER NOT NULL CHECK(cpu_ceiling_ms>0),
    status TEXT NOT NULL CHECK(status IN ('reserved','settled','unknown')),
    observed_cpu_ms INTEGER CHECK(observed_cpu_ms IS NULL OR observed_cpu_ms>=0),
    output BLOB,
    output_sha256 TEXT,
    created_at REAL NOT NULL,
    finished_at REAL,
    PRIMARY KEY(project_id,operation_id)
);
CREATE INDEX runtime_auxiliary_attempt ON runtime_auxiliary_work(attempt_id);
CREATE TRIGGER runtime_auxiliary_identity_immutable BEFORE UPDATE ON runtime_auxiliary_work
WHEN OLD.project_id IS NOT NEW.project_id OR OLD.operation_id IS NOT NEW.operation_id
 OR OLD.kind IS NOT NEW.kind OR OLD.fingerprint IS NOT NEW.fingerprint
 OR OLD.input_sha256 IS NOT NEW.input_sha256 OR OLD.input_bytes IS NOT NEW.input_bytes
 OR OLD.attempt_id IS NOT NEW.attempt_id OR OLD.grant_id IS NOT NEW.grant_id
 OR OLD.cpu_ceiling_ms IS NOT NEW.cpu_ceiling_ms OR OLD.created_at IS NOT NEW.created_at
 OR OLD.status<>'reserved'
BEGIN SELECT RAISE(ABORT,'Auxiliary work original identity and final receipt are immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(61,'durable_auxiliary_work_budget');
