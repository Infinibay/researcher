-- Migration 25: durable, gated PID-namespace ownership. No payload before binding.
CREATE TABLE runtime_peer_scopes (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    protocol_version INTEGER NOT NULL CHECK(protocol_version=1),
    created_at REAL NOT NULL
);
CREATE TABLE runtime_peers (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('native','business','command')),
    protocol_version INTEGER NOT NULL CHECK(protocol_version=1),
    state TEXT NOT NULL CHECK(state IN ('prepared','bound','closed')),
    fence INTEGER NOT NULL,
    owner_pid INTEGER NOT NULL,
    owner_start_ticks INTEGER NOT NULL,
    boot_id TEXT NOT NULL,
    observer_namespace INTEGER NOT NULL,
    init_pid INTEGER,
    start_ticks INTEGER,
    init_namespace INTEGER,
    reason TEXT,
    created_at REAL NOT NULL,
    bound_at REAL,
    closed_at REAL,
    CHECK(state<>'bound' OR (init_pid IS NOT NULL AND start_ticks IS NOT NULL AND init_namespace IS NOT NULL)),
    CHECK(state<>'closed' OR (reason IS NOT NULL AND closed_at IS NOT NULL))
);
CREATE UNIQUE INDEX idx_one_inference_peer_kind ON runtime_peers(attempt_id,kind)
    WHERE kind IN ('native','business');
CREATE INDEX idx_peers_attempt ON runtime_peers(attempt_id,id);
CREATE TRIGGER protect_live_peer_history BEFORE DELETE ON runtime_peers
    WHEN old.state<>'closed'
    BEGIN SELECT RAISE(ABORT,'Close owned peers before deleting execution history'); END;
CREATE TABLE runtime_recovery_operations (
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    operation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    requested_at REAL NOT NULL,
    completed_at REAL,
    PRIMARY KEY(project_id,task_id,operation_key),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id) REFERENCES runtime_runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(run_id,attempt_id) REFERENCES runtime_attempts(run_id,id) ON DELETE CASCADE
);
INSERT INTO schema_migrations(version,name) VALUES(25,'owned_pid_namespace_peers');
