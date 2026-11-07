-- Migration63: local permissions belong to one physical database; restored work is historical evidence.
DROP TRIGGER runtime_auxiliary_continuation_immutable;
ALTER TABLE runtime_auxiliary_continuations RENAME TO runtime_auxiliary_continuations_v62;
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
    origin_database TEXT NOT NULL,
    PRIMARY KEY(project_id,operation_key),
    UNIQUE(project_id,source_operation_id,origin_database),
    UNIQUE(project_id,successor_operation_id),
    UNIQUE(project_id,root_operation_id,generation),
    FOREIGN KEY(project_id,source_operation_id) REFERENCES runtime_auxiliary_work(project_id,operation_id)
);
-- Do not invent original physical identity for existing permission receipts.
INSERT INTO runtime_auxiliary_continuations SELECT *,'' FROM runtime_auxiliary_continuations_v62;
DROP TABLE runtime_auxiliary_continuations_v62;
CREATE TRIGGER runtime_auxiliary_continuation_immutable BEFORE UPDATE ON runtime_auxiliary_continuations
BEGIN SELECT RAISE(ABORT,'Original local continuation decisions are immutable'); END;
CREATE TABLE runtime_auxiliary_archives (
    project_id INTEGER NOT NULL,
    operation_id TEXT NOT NULL,
    database_identity TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    archived_at REAL NOT NULL,
    PRIMARY KEY(project_id,operation_id,database_identity),
    FOREIGN KEY(project_id,operation_id) REFERENCES runtime_auxiliary_work(project_id,operation_id) ON DELETE CASCADE
);
CREATE TRIGGER runtime_auxiliary_archive_immutable BEFORE UPDATE ON runtime_auxiliary_archives
BEGIN SELECT RAISE(ABORT,'Original local restoration provenance is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(63,'local_permission_origin_and_restored_history');
