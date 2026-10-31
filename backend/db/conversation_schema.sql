-- Migration 22: human conversation delivery shares the run's transaction.
CREATE UNIQUE INDEX idx_runtime_run_project_identity ON runtime_runs(project_id,id);
CREATE UNIQUE INDEX idx_chat_message_scope ON chat_messages(project_id,thread_id,id);
CREATE UNIQUE INDEX idx_conversation_scope ON conversation_threads(project_id,thread_id);
CREATE TABLE runtime_chat_links (
    run_id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    user_message_id INTEGER NOT NULL UNIQUE,
    proposal_message_id INTEGER UNIQUE,
    FOREIGN KEY(project_id,run_id) REFERENCES runtime_runs(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,thread_id) REFERENCES conversation_threads(project_id,thread_id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,thread_id,user_message_id) REFERENCES chat_messages(project_id,thread_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,thread_id,proposal_message_id) REFERENCES chat_messages(project_id,thread_id,id) ON DELETE CASCADE
);
INSERT INTO schema_migrations(version,name) VALUES(22,'runtime_human_conversation_delivery');
