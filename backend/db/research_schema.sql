-- Migration 18. Applied as individual statements in one transaction.
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_project_identity ON tasks(project_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_findings_project_identity ON findings(project_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_project_identity ON artifacts(project_id,id);

CREATE TABLE IF NOT EXISTS task_contexts (
    task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version>=1)
);
CREATE TABLE IF NOT EXISTS tool_grants (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    permissions_json TEXT NOT NULL CHECK(json_valid(permissions_json)),
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL,
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tool_grants_task ON tool_grants(task_id,revoked_at);
CREATE TABLE IF NOT EXISTS tool_operations (
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    operation_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL CHECK(json_valid(result_json)),
    grant_id TEXT REFERENCES tool_grants(id) ON DELETE SET NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(project_id,task_id,operation_key),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS research_sources (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('attachment','web')),
    locator TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    provenance_json TEXT NOT NULL CHECK(json_valid(provenance_json)),
    captured_at REAL NOT NULL,
    UNIQUE(project_id,id),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_research_sources_project ON research_sources(project_id,id);
CREATE TABLE IF NOT EXISTS finding_sources (
    project_id INTEGER NOT NULL,
    finding_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    quote TEXT NOT NULL,
    PRIMARY KEY(finding_id,source_id,quote),
    FOREIGN KEY(project_id,finding_id) REFERENCES findings(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,source_id) REFERENCES research_sources(project_id,id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS research_reports (
    artifact_id INTEGER PRIMARY KEY REFERENCES artifacts(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL CHECK(report_type IN ('research','analysis','summary')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','accepted','superseded')),
    content_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_findings (
    project_id INTEGER NOT NULL,
    artifact_id INTEGER NOT NULL,
    finding_id INTEGER NOT NULL,
    PRIMARY KEY(artifact_id,finding_id),
    FOREIGN KEY(project_id,artifact_id) REFERENCES artifacts(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,finding_id) REFERENCES findings(project_id,id) ON DELETE RESTRICT
);
INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(18,'research_evidence_and_tool_grants');
