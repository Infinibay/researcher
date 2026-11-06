-- Migration 56: attributed advisory messages between admitted native runs.
CREATE UNIQUE INDEX idx_agent_message_run_scope ON runtime_runs(project_id,id);
CREATE UNIQUE INDEX idx_agent_message_attempt_scope ON runtime_attempts(run_id,id);
CREATE TABLE runtime_agent_messages (
    message_id INTEGER PRIMARY KEY REFERENCES chat_messages(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sender_run_id TEXT NOT NULL,
    sender_attempt_id TEXT NOT NULL,
    sender_context_version INTEGER NOT NULL CHECK(sender_context_version>=1),
    recipient_run_id TEXT NOT NULL,
    recipient_context_version INTEGER NOT NULL CHECK(recipient_context_version>=1),
    intent TEXT NOT NULL CHECK(intent IN ('note','question','answer')),
    body_json TEXT NOT NULL CHECK(json_valid(body_json) AND length(body_json)<=64000),
    body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64),
    acknowledged_by_attempt TEXT,
    acknowledged_at REAL,
    CHECK(sender_run_id<>recipient_run_id),
    CHECK((acknowledged_by_attempt IS NULL)=(acknowledged_at IS NULL)),
    FOREIGN KEY(project_id,sender_run_id) REFERENCES runtime_runs(project_id,id),
    FOREIGN KEY(project_id,recipient_run_id) REFERENCES runtime_runs(project_id,id),
    FOREIGN KEY(sender_run_id,sender_attempt_id) REFERENCES runtime_attempts(run_id,id),
    FOREIGN KEY(recipient_run_id,acknowledged_by_attempt) REFERENCES runtime_attempts(run_id,id)
);
CREATE INDEX idx_agent_message_inbox ON runtime_agent_messages(recipient_run_id,message_id);
CREATE INDEX idx_agent_message_outbox ON runtime_agent_messages(sender_run_id,message_id);
INSERT INTO schema_migrations(version,name) VALUES(56,'native_agent_advisory_messages');
