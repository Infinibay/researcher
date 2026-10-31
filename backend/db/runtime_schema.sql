-- Migration 19: product execution identity, authority and durable context.
CREATE TABLE runtime_runs (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    operation_key TEXT NOT NULL,
    prompt TEXT NOT NULL,
    runtime TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','cancelling','reconciling','needs_review','failed','cancelled','superseded','accepted')),
    fence INTEGER NOT NULL DEFAULT 0 CHECK(fence>=0),
    current_attempt_id TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(project_id,task_id,operation_key),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(project_id,task_id)
    WHERE status IN ('queued','running','cancelling','reconciling','needs_review');
CREATE TABLE runtime_attempts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    fence INTEGER NOT NULL CHECK(fence>=1),
    status TEXT NOT NULL CHECK(status IN ('running','finished','reconciling')),
    lease_expires_at REAL NOT NULL,
    thread_id TEXT,
    turn_id TEXT,
    native_result_json TEXT CHECK(native_result_json IS NULL OR json_valid(native_result_json)),
    started_at REAL NOT NULL,
    ended_at REAL,
    UNIQUE(run_id,fence)
);
CREATE TABLE runtime_context_revisions (
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    version INTEGER NOT NULL CHECK(version>=2),
    statement TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK(source_kind IN ('user_message','user_example','tool_evidence','assumption')),
    source_reference TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(project_id,task_id,version),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TABLE runtime_commands (
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    operation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL CHECK(json_valid(result_json)),
    created_at REAL NOT NULL,
    PRIMARY KEY(project_id,task_id,operation_key),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
-- Receipts can outlive event retention; event_id is a historical cursor, not a
-- cascading FK whose deletion would permit a repeated native fact to reappear.
CREATE TABLE runtime_observation_receipts (
    attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    observation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(attempt_id,observation_key)
);
ALTER TABLE tool_grants ADD COLUMN runtime_attempt_id TEXT REFERENCES runtime_attempts(id) ON DELETE SET NULL;
-- Retain binding history if an attempt is deleted: NULL must not restore authority.
ALTER TABLE tool_grants ADD COLUMN runtime_bound INTEGER NOT NULL DEFAULT 0 CHECK(runtime_bound IN (0,1));
CREATE INDEX idx_tool_grants_runtime ON tool_grants(runtime_attempt_id);
CREATE INDEX idx_events_runtime_replay ON events_log(project_id,event_source,id);
INSERT INTO schema_migrations(version,name) VALUES(19,'durable_runtime_coordination');
