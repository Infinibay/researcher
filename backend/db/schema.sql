-- =============================================================================
-- INFINIBAY v2 - Database Schema
-- Version: 2.0.0
-- Description: Single source of truth for all CrewAI flows and agents.
--              Project-centric architecture with granular task states,
--              Git branch tracking, task dependencies, and structured
--              agent communication.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Pragmas
-- ---------------------------------------------------------------------------
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -8000;

-- ---------------------------------------------------------------------------
-- Schema Migrations Tracking
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version   INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================= CORE TABLES =================================

-- ---------------------------------------------------------------------------
-- 1. projects  (replaces PRD concept)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT NOT NULL,
    description           TEXT,
    original_description  TEXT,
    status                TEXT NOT NULL DEFAULT 'new'
                            CHECK(status IN ('new', 'planning', 'executing', 'paused', 'completed', 'cancelled')),
    created_by            TEXT DEFAULT 'user',
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at          DATETIME,
    metadata_json         TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- ---------------------------------------------------------------------------
-- 2. epics
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS epics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open', 'in_progress', 'completed', 'cancelled')),
    priority      INTEGER DEFAULT 2 CHECK(priority BETWEEN 1 AND 5),
    order_index   INTEGER DEFAULT 0,
    created_by    TEXT DEFAULT 'orchestrator',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at  DATETIME
);

CREATE INDEX IF NOT EXISTS idx_epics_project ON epics(project_id);
CREATE INDEX IF NOT EXISTS idx_epics_status  ON epics(status);

-- ---------------------------------------------------------------------------
-- 3. milestones
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS milestones (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    epic_id       INTEGER NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open', 'in_progress', 'completed', 'cancelled')),
    target_cycle  INTEGER,
    due_date      DATETIME,
    order_index   INTEGER DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at  DATETIME
);

CREATE INDEX IF NOT EXISTS idx_milestones_epic    ON milestones(epic_id);
CREATE INDEX IF NOT EXISTS idx_milestones_project ON milestones(project_id);
CREATE INDEX IF NOT EXISTS idx_milestones_status  ON milestones(status);

-- ---------------------------------------------------------------------------
-- 4. tasks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id           INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    epic_id              INTEGER REFERENCES epics(id) ON DELETE SET NULL,
    milestone_id         INTEGER REFERENCES milestones(id) ON DELETE SET NULL,
    parent_task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    type                 TEXT NOT NULL
                           CHECK(type IN (
                             'plan', 'research', 'investigation', 'code', 'review', 'test',
                             'design', 'integrate', 'documentation', 'bug_fix'
                           )),
    status               TEXT NOT NULL DEFAULT 'backlog'
                           CHECK(status IN (
                             'backlog', 'pending', 'in_progress',
                             'review_ready', 'rejected', 'done', 'cancelled',
                             'failed', 'blocked'
                           )),
    title                TEXT NOT NULL,
    description          TEXT,
    acceptance_criteria  TEXT,
    context_json         TEXT,
    priority             INTEGER DEFAULT 2 CHECK(priority BETWEEN 1 AND 5),
    estimated_complexity TEXT DEFAULT 'medium'
                           CHECK(estimated_complexity IN (
                             'trivial', 'low', 'medium', 'high', 'very_high'
                           )),
    branch_name          TEXT,
    pr_number            INTEGER,
    pr_url               TEXT,
    assigned_to          TEXT,
    reviewer             TEXT,
    created_by           TEXT NOT NULL DEFAULT 'orchestrator',
    retry_count          INTEGER DEFAULT 0,
    created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at         DATETIME
);

CREATE INDEX IF NOT EXISTS idx_tasks_project    ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_type       ON tasks(type);
CREATE INDEX IF NOT EXISTS idx_tasks_priority   ON tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_epic       ON tasks(epic_id);
CREATE INDEX IF NOT EXISTS idx_tasks_milestone  ON tasks(milestone_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned   ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_reviewer   ON tasks(reviewer);
CREATE INDEX IF NOT EXISTS idx_tasks_branch     ON tasks(branch_name);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by);

-- ---------------------------------------------------------------------------
-- 5. task_dependencies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_dependencies (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id            INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dependency_type    TEXT DEFAULT 'blocks'
                         CHECK(dependency_type IN ('blocks', 'related_to', 'parent_of')),
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, depends_on_task_id)
);

CREATE INDEX IF NOT EXISTS idx_task_deps_task    ON task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_task_deps_depends ON task_dependencies(depends_on_task_id);

-- ---------------------------------------------------------------------------
-- 6. task_comments
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_comments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author        TEXT NOT NULL,
    comment_type  TEXT DEFAULT 'comment'
                    CHECK(comment_type IN (
                      'comment', 'change_request', 'approval', 'question', 'answer'
                    )),
    content       TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_comments_task   ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_author ON task_comments(author);
CREATE INDEX IF NOT EXISTS idx_task_comments_type   ON task_comments(comment_type);

-- ========================= GIT INTEGRATION =================================

-- ---------------------------------------------------------------------------
-- 7. branches
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS branches (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id          INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    repo_name        TEXT NOT NULL,
    branch_name      TEXT NOT NULL,
    base_branch      TEXT DEFAULT 'main',
    status           TEXT DEFAULT 'active'
                       CHECK(status IN ('active', 'merged', 'abandoned', 'stale')),
    created_by       TEXT NOT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    merged_at        DATETIME,
    last_commit_hash TEXT,
    last_commit_at   DATETIME,
    UNIQUE(repo_name, branch_name)
);

CREATE INDEX IF NOT EXISTS idx_branches_project ON branches(project_id);
CREATE INDEX IF NOT EXISTS idx_branches_task    ON branches(task_id);
CREATE INDEX IF NOT EXISTS idx_branches_repo    ON branches(repo_name);
CREATE INDEX IF NOT EXISTS idx_branches_status  ON branches(status);

-- ---------------------------------------------------------------------------
-- 7b. repositories
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS repositories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    local_path      TEXT NOT NULL,
    remote_url      TEXT,
    default_branch  TEXT DEFAULT 'main',
    status          TEXT DEFAULT 'active'
                      CHECK(status IN ('active', 'archived')),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_repositories_project ON repositories(project_id);
CREATE INDEX IF NOT EXISTS idx_repositories_status  ON repositories(status);

-- ========================= COMMUNICATION ===================================

-- ---------------------------------------------------------------------------
-- 8. conversation_threads
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversation_threads (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id         TEXT UNIQUE NOT NULL,
    project_id        INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    task_id           INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    thread_type       TEXT NOT NULL
                        CHECK(thread_type IN (
                          'task_discussion', 'code_review', 'brainstorming',
                          'user_chat', 'team_sync'
                        )),
    participants_json TEXT DEFAULT '[]',
    status            TEXT DEFAULT 'active'
                        CHECK(status IN ('active', 'archived', 'resolved')),
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_message_at   DATETIME
);

CREATE INDEX IF NOT EXISTS idx_conv_threads_project ON conversation_threads(project_id);
CREATE INDEX IF NOT EXISTS idx_conv_threads_task    ON conversation_threads(task_id);
CREATE INDEX IF NOT EXISTS idx_conv_threads_type    ON conversation_threads(thread_type);
CREATE INDEX IF NOT EXISTS idx_conv_threads_status  ON conversation_threads(status);

-- ---------------------------------------------------------------------------
-- 9. chat_messages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id         INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    thread_id          TEXT NOT NULL REFERENCES conversation_threads(thread_id) ON DELETE CASCADE,
    parent_message_id  INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    from_agent         TEXT NOT NULL,
    to_agent           TEXT,
    to_role            TEXT,
    conversation_type  TEXT DEFAULT 'agent_to_agent'
                         CHECK(conversation_type IN (
                           'agent_to_agent', 'user_to_agent',
                           'agent_to_user', 'broadcast'
                         )),
    message            TEXT NOT NULL,
    priority           INTEGER DEFAULT 0,
    metadata_json      TEXT DEFAULT '{}',
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_to_agent          ON chat_messages(to_agent);
CREATE INDEX IF NOT EXISTS idx_chat_to_role            ON chat_messages(to_role);
CREATE INDEX IF NOT EXISTS idx_chat_thread             ON chat_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_chat_project            ON chat_messages(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversation_type  ON chat_messages(conversation_type);
CREATE INDEX IF NOT EXISTS idx_chat_parent             ON chat_messages(parent_message_id);

-- ---------------------------------------------------------------------------
-- 10. message_reads
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS message_reads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    agent_id   TEXT NOT NULL,
    read_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_message_reads_message ON message_reads(message_id);
CREATE INDEX IF NOT EXISTS idx_message_reads_agent   ON message_reads(agent_id);

-- ========================= KNOWLEDGE =======================================

-- ---------------------------------------------------------------------------
-- 11. reference_files
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_name   TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    file_type   TEXT,
    file_size   INTEGER,
    description TEXT,
    uploaded_by TEXT DEFAULT 'user',
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    tags_json   TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_reference_files_project ON reference_files(project_id);
CREATE INDEX IF NOT EXISTS idx_reference_files_type    ON reference_files(file_type);

-- ---------------------------------------------------------------------------
-- 12. findings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS findings (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id            INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    task_id               INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent_run_id          TEXT,
    topic                 TEXT NOT NULL,
    content               TEXT NOT NULL,
    sources_json          TEXT DEFAULT '[]',
    confidence            REAL DEFAULT 0.5
                            CHECK(confidence BETWEEN 0.0 AND 1.0),
    agent_id              TEXT NOT NULL,
    status                TEXT DEFAULT 'provisional'
                            CHECK(status IN ('active', 'provisional', 'superseded')),
    finding_type          TEXT DEFAULT 'observation'
                            CHECK(finding_type IN (
                              'observation', 'hypothesis', 'experiment',
                              'proof', 'conclusion'
                            )),
    validation_method     TEXT,
    reproducibility_score REAL
                            CHECK(reproducibility_score IS NULL
                              OR reproducibility_score BETWEEN 0.0 AND 1.0),
    embedding             BLOB,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_findings_project   ON findings(project_id);
CREATE INDEX IF NOT EXISTS idx_findings_task_id   ON findings(task_id);
CREATE INDEX IF NOT EXISTS idx_findings_topic     ON findings(topic);
CREATE INDEX IF NOT EXISTS idx_findings_status    ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_agent_run ON findings(agent_run_id);

-- ---------------------------------------------------------------------------
-- 13. finding_deps
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finding_deps (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id            INTEGER NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    depends_on_finding_id INTEGER NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    relationship          TEXT DEFAULT 'supports'
                            CHECK(relationship IN (
                              'supports', 'contradicts', 'extends', 'supersedes'
                            )),
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(finding_id, depends_on_finding_id)
);

-- ---------------------------------------------------------------------------
-- 14. knowledge
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    agent_id   TEXT,
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_project  ON knowledge(project_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_key      ON knowledge(key);

-- ---------------------------------------------------------------------------
-- 15. wiki_pages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wiki_pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    path        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    parent_path TEXT,
    created_by  TEXT,
    updated_by  TEXT,
    embedding   BLOB,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wiki_project ON wiki_pages(project_id);
CREATE INDEX IF NOT EXISTS idx_wiki_path    ON wiki_pages(path);
CREATE INDEX IF NOT EXISTS idx_wiki_parent  ON wiki_pages(parent_path);

-- ========================= AGENTS ==========================================

-- ---------------------------------------------------------------------------
-- 16. agent_registry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_registry (
    id              TEXT PRIMARY KEY,
    role            TEXT NOT NULL,
    task_description TEXT,
    container_id    TEXT,
    status          TEXT DEFAULT 'alive'
                      CHECK(status IN ('alive', 'exited')),
    registered_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_status ON agent_registry(status);

-- ---------------------------------------------------------------------------
-- 17. roster
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roster (
    agent_id       TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    role           TEXT NOT NULL,
    memory         TEXT DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'idle'
                     CHECK(status IN ('idle', 'active', 'retired')),
    total_runs     INTEGER DEFAULT 0,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_roster_role   ON roster(role);
CREATE INDEX IF NOT EXISTS idx_roster_status ON roster(status);

-- ---------------------------------------------------------------------------
-- 18. agent_runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    agent_run_id   TEXT UNIQUE NOT NULL,
    agent_id       TEXT NOT NULL,
    task_id        INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    role           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'running'
                     CHECK(status IN ('running', 'completed', 'failed', 'timeout')),
    prompt_hash    TEXT,
    output_summary TEXT,
    tokens_used    INTEGER,
    error_class    TEXT,
    started_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at       DATETIME
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_project ON agent_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_task    ON agent_runs(task_id);

-- ---------------------------------------------------------------------------
-- 19. agent_performance  (global, no project FK)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_performance (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id            TEXT NOT NULL,
    role                TEXT NOT NULL,
    total_runs          INTEGER DEFAULT 0,
    successful_runs     INTEGER DEFAULT 0,
    failed_runs         INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,
    total_cost_usd      REAL DEFAULT 0.0,
    avg_task_duration_s REAL,
    last_updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_perf_agent ON agent_performance(agent_id);

-- ---------------------------------------------------------------------------
-- 20. status_updates
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS status_updates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    agent_id     TEXT NOT NULL,
    agent_run_id TEXT,
    message      TEXT NOT NULL,
    progress     INTEGER CHECK(progress BETWEEN 0 AND 100),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_status_updates_project ON status_updates(project_id);
CREATE INDEX IF NOT EXISTS idx_status_updates_agent   ON status_updates(agent_id);
CREATE INDEX IF NOT EXISTS idx_status_updates_run     ON status_updates(agent_run_id);

-- ========================= AUDIT / EVENTS ==================================

-- ---------------------------------------------------------------------------
-- 21. events_log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    event_source    TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       INTEGER,
    event_data_json TEXT DEFAULT '{}',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events_log(project_id);
CREATE INDEX IF NOT EXISTS idx_events_type    ON events_log(event_type);
CREATE INDEX IF NOT EXISTS idx_events_entity  ON events_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events_log(created_at);

-- ========================= ARTIFACTS / CODE QUALITY ========================

-- ---------------------------------------------------------------------------
-- 22. artifacts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    task_id     INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    type        TEXT NOT NULL
                  CHECK(type IN ('code', 'report', 'data', 'diagram')),
    file_path   TEXT NOT NULL,
    description TEXT,
    content     TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts(project_id);

-- ---------------------------------------------------------------------------
-- 23. artifact_changes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifact_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    agent_run_id TEXT,
    cycle        INTEGER,
    file_path    TEXT NOT NULL,
    action       TEXT NOT NULL
                   CHECK(action IN ('created', 'modified', 'deleted')),
    before_hash  TEXT,
    after_hash   TEXT,
    size_bytes   INTEGER,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_artifact_changes_project ON artifact_changes(project_id);
CREATE INDEX IF NOT EXISTS idx_artifact_changes_cycle   ON artifact_changes(cycle);
CREATE INDEX IF NOT EXISTS idx_artifact_changes_file    ON artifact_changes(file_path);

-- ---------------------------------------------------------------------------
-- 24. code_reviews
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    task_id      INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    branch       TEXT NOT NULL,
    agent_run_id TEXT NOT NULL,
    repo_name    TEXT NOT NULL,
    summary      TEXT DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending'
                   CHECK(status IN ('pending', 'approved', 'changes_requested', 'merged')),
    reviewer     TEXT,
    comments     TEXT,
    forgejo_pr_index INTEGER,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    reviewed_at  DATETIME
);

CREATE INDEX IF NOT EXISTS idx_code_reviews_project ON code_reviews(project_id);
CREATE INDEX IF NOT EXISTS idx_code_reviews_task    ON code_reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_code_reviews_status  ON code_reviews(status);

-- ---------------------------------------------------------------------------
-- 25. code_quality
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_quality (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    cycle       INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    syntax_ok   INTEGER DEFAULT 1,
    lint_issues INTEGER DEFAULT 0,
    lint_output TEXT,
    test_count  INTEGER DEFAULT 0,
    test_pass   INTEGER DEFAULT 0,
    test_output TEXT,
    coverage    REAL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_code_quality_project ON code_quality(project_id);
CREATE INDEX IF NOT EXISTS idx_code_quality_cycle   ON code_quality(cycle);
CREATE INDEX IF NOT EXISTS idx_code_quality_file    ON code_quality(file_path);

-- ---------------------------------------------------------------------------
-- 26. validation_results
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS validation_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    cycle        INTEGER NOT NULL,
    file_path    TEXT NOT NULL,
    result       TEXT NOT NULL
                   CHECK(result IN ('pass', 'fail', 'timeout', 'skip')),
    error_output TEXT,
    attempt      INTEGER DEFAULT 1,
    file_mtime   REAL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_validation_project ON validation_results(project_id);
CREATE INDEX IF NOT EXISTS idx_validation_cycle   ON validation_results(cycle);
CREATE INDEX IF NOT EXISTS idx_validation_file    ON validation_results(file_path);

-- ========================= MISC ============================================

-- ---------------------------------------------------------------------------
-- 27. processes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    task_id      INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    agent_run_id TEXT,
    command      TEXT NOT NULL,
    pid          INTEGER,
    status       TEXT NOT NULL DEFAULT 'running'
                   CHECK(status IN ('running', 'completed', 'failed', 'stopped')),
    output_file  TEXT,
    started_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at     DATETIME,
    last_check_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_processes_project ON processes(project_id);
CREATE INDEX IF NOT EXISTS idx_processes_status  ON processes(status);

-- ---------------------------------------------------------------------------
-- 28. user_requests
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    agent_id     TEXT NOT NULL,
    agent_run_id TEXT,
    request_type TEXT NOT NULL
                   CHECK(request_type IN ('question', 'file', 'approval', 'api_key')),
    title        TEXT NOT NULL,
    body         TEXT,
    options_json TEXT DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'pending'
                   CHECK(status IN ('pending', 'responded', 'expired')),
    response     TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_user_requests_project ON user_requests(project_id);
CREATE INDEX IF NOT EXISTS idx_user_requests_status  ON user_requests(status);
CREATE INDEX IF NOT EXISTS idx_user_requests_agent   ON user_requests(agent_id);

-- ---------------------------------------------------------------------------
-- 29. notices
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    priority   INTEGER DEFAULT 0,
    active     INTEGER DEFAULT 1,
    created_by TEXT DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_notices_project ON notices(project_id);
CREATE INDEX IF NOT EXISTS idx_notices_active  ON notices(active);

-- ---------------------------------------------------------------------------
-- 30. brainstorm_sessions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brainstorm_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    topic        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                   CHECK(status IN ('pending', 'active', 'completed', 'cancelled')),
    cycle        INTEGER DEFAULT 0,
    ideas_count  INTEGER DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_brainstorm_project ON brainstorm_sessions(project_id);

-- ---------------------------------------------------------------------------
-- 31. convergence_log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS convergence_log (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id             INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    iteration              INTEGER NOT NULL,
    total_tasks            INTEGER,
    completed_tasks        INTEGER,
    failed_tasks           INTEGER,
    new_tasks_this_cycle   INTEGER,
    total_findings         INTEGER,
    new_findings_this_cycle INTEGER,
    major_issues           INTEGER,
    minor_issues           INTEGER,
    code_files_pass        INTEGER,
    code_files_fail        INTEGER,
    progress_score         REAL,
    strategy_note          TEXT,
    decision               TEXT
                             CHECK(decision IN (
                               'continue', 'converged', 'forced', 'interrupted'
                             )),
    total_tokens           INTEGER,
    estimated_cost_usd     REAL,
    checked_at             DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_convergence_project ON convergence_log(project_id);

-- ---------------------------------------------------------------------------
-- 32. env_vars  (global, no project FK)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS env_vars (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    value      TEXT NOT NULL DEFAULT '',
    is_secret  INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 33. circuit_breaker  (global, no project FK)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS circuit_breaker (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type      TEXT NOT NULL,
    state          TEXT NOT NULL DEFAULT 'closed'
                     CHECK(state IN ('closed', 'open', 'half_open')),
    failure_count  INTEGER DEFAULT 0,
    last_failure_at DATETIME,
    opened_at      DATETIME,
    threshold      INTEGER DEFAULT 3,
    window_seconds INTEGER DEFAULT 300
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_circuit_breaker_type ON circuit_breaker(task_type);

-- ========================= ANTI-LOOP SYSTEM ================================

-- ---------------------------------------------------------------------------
-- 34. message_fingerprints  (deduplication for loop detection)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS message_fingerprints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    from_agent  TEXT NOT NULL,
    to_agent    TEXT,
    to_role     TEXT,
    thread_id   TEXT,
    fingerprint TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_msg_fp_agent_created
    ON message_fingerprints(from_agent, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_fp_fingerprint_agent
    ON message_fingerprints(fingerprint, from_agent);
CREATE INDEX IF NOT EXISTS idx_msg_fp_thread_agent_created
    ON message_fingerprints(thread_id, from_agent, created_at);

-- ---------------------------------------------------------------------------
-- 35. loop_incidents  (audit log for loop detection events)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loop_incidents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    incident_type   TEXT NOT NULL
                      CHECK(incident_type IN (
                        'duplicate_message', 'rate_limit', 'ping_pong',
                        'circuit_open', 'question_budget', 'pair_exchange'
                      )),
    thread_id       TEXT,
    agents_involved TEXT NOT NULL DEFAULT '[]',
    action_taken    TEXT NOT NULL
                      CHECK(action_taken IN (
                        'blocked', 'throttled', 'escalated_to_user', 'circuit_opened'
                      )),
    details         TEXT DEFAULT '',
    resolved        INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loop_incidents_project ON loop_incidents(project_id);
CREATE INDEX IF NOT EXISTS idx_loop_incidents_type    ON loop_incidents(incident_type);

-- ---------------------------------------------------------------------------
-- 36. clarification_questions  (cross-agent question deduplication)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clarification_questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    asked_by      TEXT NOT NULL,
    asked_to_role TEXT,
    question_hash TEXT NOT NULL,
    question_text TEXT NOT NULL,
    answer_text   TEXT,
    answered_by   TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'answered', 'assumed', 'expired')),
    assumption    TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    answered_at   DATETIME
);

CREATE INDEX IF NOT EXISTS idx_clarif_q_project ON clarification_questions(project_id);
CREATE INDEX IF NOT EXISTS idx_clarif_q_hash    ON clarification_questions(question_hash);
CREATE INDEX IF NOT EXISTS idx_clarif_q_status  ON clarification_questions(status);
CREATE INDEX IF NOT EXISTS idx_clarif_q_task    ON clarification_questions(task_id);

-- ========================= DEVELOPER SESSION NOTES =========================

-- ---------------------------------------------------------------------------
-- 37. developer_session_notes  (persist developer progress across interruptions)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS developer_session_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent_id    TEXT NOT NULL,
    phase       TEXT NOT NULL
                  CHECK(phase IN (
                    'thinking', 'locating', 'implementing', 'testing',
                    'decomposing', 'searching', 'evaluating', 'synthesizing', 'reporting'
                  )),
    notes_json  TEXT NOT NULL DEFAULT '{}',
    last_file   TEXT,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_session_notes_task  ON developer_session_notes(task_id);
CREATE INDEX IF NOT EXISTS idx_session_notes_agent ON developer_session_notes(agent_id);

-- ========================= FLOW PERSISTENCE =================================

-- ---------------------------------------------------------------------------
-- 38. flow_snapshots  (persist flow position for resume-on-restart)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flow_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    flow_name    TEXT NOT NULL,
    current_step TEXT NOT NULL,
    state_json   TEXT NOT NULL DEFAULT '{}',
    subflow_name TEXT,
    subflow_step TEXT,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id)
);

CREATE INDEX IF NOT EXISTS idx_flow_snapshots_project ON flow_snapshots(project_id);

-- ========================= FTS5 (Full-Text Search) =========================

-- Findings FTS
CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts USING fts5(
    topic, content, content=findings, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS findings_fts_ai AFTER INSERT ON findings BEGIN
    INSERT INTO findings_fts(rowid, topic, content)
    VALUES (new.id, new.topic, new.content);
END;

CREATE TRIGGER IF NOT EXISTS findings_fts_ad AFTER DELETE ON findings BEGIN
    INSERT INTO findings_fts(findings_fts, rowid, topic, content)
    VALUES ('delete', old.id, old.topic, old.content);
END;

CREATE TRIGGER IF NOT EXISTS findings_fts_au AFTER UPDATE ON findings BEGIN
    INSERT INTO findings_fts(findings_fts, rowid, topic, content)
    VALUES ('delete', old.id, old.topic, old.content);
    INSERT INTO findings_fts(rowid, topic, content)
    VALUES (new.id, new.topic, new.content);
END;

-- Knowledge FTS
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    category, key, value, content=knowledge, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS knowledge_fts_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(rowid, category, key, value)
    VALUES (new.id, new.category, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_fts_ad AFTER DELETE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, category, key, value)
    VALUES ('delete', old.id, old.category, old.key, old.value);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_fts_au AFTER UPDATE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, category, key, value)
    VALUES ('delete', old.id, old.category, old.key, old.value);
    INSERT INTO knowledge_fts(rowid, category, key, value)
    VALUES (new.id, new.category, new.key, new.value);
END;

-- Wiki FTS
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    path, title, content, content=wiki_pages, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS wiki_fts_ai AFTER INSERT ON wiki_pages BEGIN
    INSERT INTO wiki_fts(rowid, path, title, content)
    VALUES (new.id, new.path, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS wiki_fts_ad AFTER DELETE ON wiki_pages BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, path, title, content)
    VALUES ('delete', old.id, old.path, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS wiki_fts_au AFTER UPDATE ON wiki_pages BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, path, title, content)
    VALUES ('delete', old.id, old.path, old.title, old.content);
    INSERT INTO wiki_fts(rowid, path, title, content)
    VALUES (new.id, new.path, new.title, new.content);
END;

-- Tasks FTS
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    title, description, acceptance_criteria, content=tasks, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS tasks_fts_ai AFTER INSERT ON tasks BEGIN
    INSERT INTO tasks_fts(rowid, title, description, acceptance_criteria)
    VALUES (new.id, new.title, COALESCE(new.description, ''), COALESCE(new.acceptance_criteria, ''));
END;

CREATE TRIGGER IF NOT EXISTS tasks_fts_ad AFTER DELETE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, title, description, acceptance_criteria)
    VALUES ('delete', old.id, COALESCE(old.title, ''), COALESCE(old.description, ''), COALESCE(old.acceptance_criteria, ''));
END;

CREATE TRIGGER IF NOT EXISTS tasks_fts_au AFTER UPDATE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, title, description, acceptance_criteria)
    VALUES ('delete', old.id, COALESCE(old.title, ''), COALESCE(old.description, ''), COALESCE(old.acceptance_criteria, ''));
    INSERT INTO tasks_fts(rowid, title, description, acceptance_criteria)
    VALUES (new.id, new.title, COALESCE(new.description, ''), COALESCE(new.acceptance_criteria, ''));
END;

-- Task Comments FTS
CREATE VIRTUAL TABLE IF NOT EXISTS task_comments_fts USING fts5(
    content, content=task_comments, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS task_comments_fts_ai AFTER INSERT ON task_comments BEGIN
    INSERT INTO task_comments_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS task_comments_fts_ad AFTER DELETE ON task_comments BEGIN
    INSERT INTO task_comments_fts(task_comments_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS task_comments_fts_au AFTER UPDATE ON task_comments BEGIN
    INSERT INTO task_comments_fts(task_comments_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO task_comments_fts(rowid, content)
    VALUES (new.id, new.content);
END;

-- Reference Files FTS
CREATE VIRTUAL TABLE IF NOT EXISTS reference_files_fts USING fts5(
    file_name, description, content=reference_files, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS reference_files_fts_ai AFTER INSERT ON reference_files BEGIN
    INSERT INTO reference_files_fts(rowid, file_name, description)
    VALUES (new.id, new.file_name, COALESCE(new.description, ''));
END;

CREATE TRIGGER IF NOT EXISTS reference_files_fts_ad AFTER DELETE ON reference_files BEGIN
    INSERT INTO reference_files_fts(reference_files_fts, rowid, file_name, description)
    VALUES ('delete', old.id, old.file_name, COALESCE(old.description, ''));
END;

CREATE TRIGGER IF NOT EXISTS reference_files_fts_au AFTER UPDATE ON reference_files BEGIN
    INSERT INTO reference_files_fts(reference_files_fts, rowid, file_name, description)
    VALUES ('delete', old.id, old.file_name, COALESCE(old.description, ''));
    INSERT INTO reference_files_fts(rowid, file_name, description)
    VALUES (new.id, new.file_name, COALESCE(new.description, ''));
END;

-- Artifacts (reports) full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
    file_path, description, content, content=artifacts, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS artifacts_fts_ai AFTER INSERT ON artifacts BEGIN
    INSERT INTO artifacts_fts(rowid, file_path, description, content)
    VALUES (new.id, new.file_path, COALESCE(new.description, ''), COALESCE(new.content, ''));
END;

CREATE TRIGGER IF NOT EXISTS artifacts_fts_ad AFTER DELETE ON artifacts BEGIN
    INSERT INTO artifacts_fts(artifacts_fts, rowid, file_path, description, content)
    VALUES ('delete', old.id, old.file_path, COALESCE(old.description, ''), COALESCE(old.content, ''));
END;

CREATE TRIGGER IF NOT EXISTS artifacts_fts_au AFTER UPDATE ON artifacts BEGIN
    INSERT INTO artifacts_fts(artifacts_fts, rowid, file_path, description, content)
    VALUES ('delete', old.id, old.file_path, COALESCE(old.description, ''), COALESCE(old.content, ''));
    INSERT INTO artifacts_fts(rowid, file_path, description, content)
    VALUES (new.id, new.file_path, COALESCE(new.description, ''), COALESCE(new.content, ''));
END;

-- ========================= AUDIT TRIGGERS ==================================

-- Task created
CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_insert AFTER INSERT ON tasks
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'task_created',
        COALESCE(new.created_by, 'system'),
        'task',
        new.id,
        json_object(
            'title', new.title,
            'type', new.type,
            'status', new.status,
            'assigned_to', new.assigned_to
        )
    );
END;

-- Task status changed
CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_status AFTER UPDATE OF status ON tasks
WHEN old.status != new.status
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'task_status_changed',
        'system',
        'task',
        new.id,
        json_object(
            'old_status', old.status,
            'new_status', new.status,
            'assigned_to', new.assigned_to
        )
    );
END;

-- Task general update (non-status fields)
CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_update AFTER UPDATE ON tasks
WHEN old.status = new.status
 AND (old.title != new.title OR old.assigned_to IS NOT new.assigned_to
      OR old.reviewer IS NOT new.reviewer OR old.branch_name IS NOT new.branch_name)
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'task_updated',
        'system',
        'task',
        new.id,
        json_object(
            'title', new.title,
            'assigned_to', new.assigned_to,
            'reviewer', new.reviewer,
            'branch_name', new.branch_name
        )
    );
END;

-- Epic created
CREATE TRIGGER IF NOT EXISTS trg_epics_audit_insert AFTER INSERT ON epics
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'epic_created',
        COALESCE(new.created_by, 'system'),
        'epic',
        new.id,
        json_object('title', new.title, 'status', new.status)
    );
END;

-- Epic status changed
CREATE TRIGGER IF NOT EXISTS trg_epics_audit_status AFTER UPDATE OF status ON epics
WHEN old.status != new.status
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'epic_status_changed',
        'system',
        'epic',
        new.id,
        json_object('old_status', old.status, 'new_status', new.status)
    );
END;

-- Milestone created
CREATE TRIGGER IF NOT EXISTS trg_milestones_audit_insert AFTER INSERT ON milestones
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'milestone_created',
        'system',
        'milestone',
        new.id,
        json_object('title', new.title, 'status', new.status)
    );
END;

-- Milestone status changed
CREATE TRIGGER IF NOT EXISTS trg_milestones_audit_status AFTER UPDATE OF status ON milestones
WHEN old.status != new.status
BEGIN
    INSERT INTO events_log(project_id, event_type, event_source, entity_type, entity_id, event_data_json)
    VALUES (
        new.project_id,
        'milestone_status_changed',
        'system',
        'milestone',
        new.id,
        json_object('old_status', old.status, 'new_status', new.status)
    );
END;

-- ========================= INITIAL MIGRATION RECORD ========================

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (1, 'initial_schema_v2');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (2, 'add_repositories_table');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (3, 'add_forgejo_pr_index_to_code_reviews');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (4, 'add_developer_session_notes');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (5, 'add_flow_snapshots');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (6, 'add_artifact_content_column');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (7, 'add_failed_task_status');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (8, 'add_original_description_to_projects');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (14, 'expand_session_note_phases');

-- ========================= AGENT AUTONOMY ================================

-- ---------------------------------------------------------------------------
-- 39. autonomy_actions  (audit log for autonomous agent decisions)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS autonomy_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_id    TEXT NOT NULL,
    action_type TEXT NOT NULL,
    task_id     INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    reason      TEXT DEFAULT '',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_autonomy_project ON autonomy_actions(project_id);
CREATE INDEX IF NOT EXISTS idx_autonomy_agent ON autonomy_actions(agent_id);

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (9, 'add_autonomy_actions_table');

-- ========================= AGENT EVENT LOOP ================================

-- ---------------------------------------------------------------------------
-- 40. agent_events  (persistent work queue for agent loops)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id       TEXT NOT NULL,
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL,
    source         TEXT NOT NULL DEFAULT '',
    priority       INTEGER NOT NULL DEFAULT 50,
    status         TEXT NOT NULL DEFAULT 'pending'
                     CHECK(status IN ('pending', 'claimed', 'in_progress', 'completed', 'failed', 'cancelled')),
    payload_json   TEXT NOT NULL DEFAULT '{}',
    progress_json  TEXT NOT NULL DEFAULT '{}',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    claimed_at     DATETIME,
    started_at     DATETIME,
    completed_at   DATETIME,
    error_message  TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_events_poll
    ON agent_events(agent_id, status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_events_project
    ON agent_events(project_id);

-- ---------------------------------------------------------------------------
-- 41. agent_loop_state  (per-agent crash recovery checkpoint)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_loop_state (
    agent_id          TEXT PRIMARY KEY,
    project_id        INTEGER NOT NULL,
    status            TEXT NOT NULL DEFAULT 'idle'
                        CHECK(status IN ('idle', 'processing', 'stopped')),
    current_event_id  INTEGER REFERENCES agent_events(id),
    last_poll_at      DATETIME,
    last_error        TEXT,
    consecutive_errors INTEGER NOT NULL DEFAULT 0,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (10, 'add_agent_events_and_loop_state');

-- ========================= PER-AGENT GIT WORKTREES ========================

-- ---------------------------------------------------------------------------
-- 42. agent_worktrees  (per-agent isolated git working copies)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_worktrees (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    repo_id        INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    agent_id       TEXT NOT NULL,
    worktree_path  TEXT NOT NULL UNIQUE,
    branch_name    TEXT,
    status         TEXT DEFAULT 'active' CHECK(status IN ('active', 'removed')),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    cleaned_up_at  DATETIME
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_worktrees_agent_project
    ON agent_worktrees(agent_id, project_id);
CREATE INDEX IF NOT EXISTS idx_agent_worktrees_project
    ON agent_worktrees(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_worktrees_status
    ON agent_worktrees(status);

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (11, 'add_agent_worktrees');

-- ========================= WEB CACHE ========================================

-- ---------------------------------------------------------------------------
-- 41. web_cache  (avoid re-fetching same URLs between LoopEngine iterations)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS web_cache (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL,
    format     TEXT NOT NULL DEFAULT 'markdown',
    content    TEXT NOT NULL,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(url, format)
);

CREATE INDEX IF NOT EXISTS idx_web_cache_url ON web_cache(url);

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (12, 'expand_session_note_phases');

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (13, 'add_web_cache');
