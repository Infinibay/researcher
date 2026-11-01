-- Migration 24. The runner disables FK cascades only for this owned transaction.
-- Preserve rowids: task history is ordered by admission, not the host clock.
CREATE TABLE runtime_runs_v24 (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    operation_key TEXT NOT NULL,
    prompt TEXT NOT NULL,
    runtime TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review','failed','cancelled','superseded','accepted')),
    fence INTEGER NOT NULL DEFAULT 0 CHECK(fence>=0),
    current_attempt_id TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(project_id,task_id,operation_key),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
INSERT INTO runtime_runs_v24(rowid,id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,fence,current_attempt_id,cancel_requested,created_at,updated_at)
    SELECT rowid,id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,fence,current_attempt_id,cancel_requested,created_at,updated_at FROM runtime_runs;
DROP TABLE runtime_runs;
ALTER TABLE runtime_runs_v24 RENAME TO runtime_runs;
CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(project_id,task_id)
    WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review');
CREATE UNIQUE INDEX idx_runtime_run_project_identity ON runtime_runs(project_id,id);
CREATE UNIQUE INDEX idx_runtime_attempt_scope ON runtime_attempts(run_id,id);
CREATE UNIQUE INDEX idx_user_request_scope ON user_requests(project_id,id);
CREATE TABLE runtime_question_links (
    request_id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    attempt_id TEXT NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    operation_key TEXT NOT NULL,
    question_set_json TEXT NOT NULL CHECK(json_valid(question_set_json)),
    thread_id TEXT NOT NULL REFERENCES conversation_threads(thread_id) ON DELETE CASCADE,
    question_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    answer_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    answer_context_version INTEGER,
    FOREIGN KEY(project_id,request_id) REFERENCES user_requests(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,run_id) REFERENCES runtime_runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(run_id,attempt_id) REFERENCES runtime_attempts(run_id,id) ON DELETE CASCADE
);
INSERT INTO schema_migrations(version,name) VALUES(24,'durable_human_questions');
