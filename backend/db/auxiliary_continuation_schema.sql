-- Migration62: physical local-work evidence and immutable owner continuation decisions.
CREATE TABLE runtime_auxiliary_executions (
    project_id INTEGER NOT NULL,
    operation_id TEXT NOT NULL,
    owner_json TEXT NOT NULL,
    phase TEXT NOT NULL CHECK(phase IN ('reserved','spawning','worker','closed')),
    worker_json TEXT,
    closed_at REAL,
    PRIMARY KEY(project_id,operation_id),
    FOREIGN KEY(project_id,operation_id) REFERENCES runtime_auxiliary_work(project_id,operation_id) ON DELETE CASCADE
);
CREATE TABLE runtime_auxiliary_continuations (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_key TEXT NOT NULL,
    source_operation_id TEXT NOT NULL,
    successor_operation_id TEXT NOT NULL,
    root_operation_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation>0),
    request_json TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(project_id,operation_key),
    UNIQUE(project_id,source_operation_id),
    UNIQUE(project_id,successor_operation_id),
    UNIQUE(project_id,root_operation_id,generation),
    FOREIGN KEY(project_id,source_operation_id) REFERENCES runtime_auxiliary_work(project_id,operation_id)
);
CREATE TRIGGER runtime_auxiliary_continuation_immutable BEFORE UPDATE ON runtime_auxiliary_continuations
BEGIN SELECT RAISE(ABORT,'Original local continuation decisions are immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(62,'explicit_auxiliary_continuation');
