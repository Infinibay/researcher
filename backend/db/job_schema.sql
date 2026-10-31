-- Migration 20: client-owned command identity and uncertain-dispatch receipts.
CREATE TABLE runtime_jobs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
    attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    executor_id TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    argv_json TEXT NOT NULL CHECK(json_valid(argv_json)),
    cwd TEXT NOT NULL,
    workspace TEXT NOT NULL,
    timeout_seconds REAL NOT NULL CHECK(timeout_seconds>0 AND timeout_seconds<=300),
    output_bytes INTEGER NOT NULL CHECK(output_bytes>=1 AND output_bytes<=4194304),
    status TEXT NOT NULL CHECK(status IN ('dispatching','cancelling','exited','unknown')),
    exit_code INTEGER,
    stdout BLOB NOT NULL DEFAULT X'',
    stderr BLOB NOT NULL DEFAULT X'',
    output_limited INTEGER NOT NULL DEFAULT 0 CHECK(output_limited IN (0,1)),
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
    error TEXT,
    created_at REAL NOT NULL,
    ended_at REAL,
    UNIQUE(run_id,operation_key)
);
CREATE UNIQUE INDEX idx_one_unreconciled_job ON runtime_jobs(run_id)
    WHERE status IN ('dispatching','cancelling','unknown');
INSERT INTO schema_migrations(version,name) VALUES(20,'owned_command_dispatch_and_receipts');
