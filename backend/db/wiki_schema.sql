CREATE UNIQUE INDEX IF NOT EXISTS uq_wiki_project_path ON wiki_pages(project_id,path) WHERE project_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_wiki_global_path ON wiki_pages(path) WHERE project_id IS NULL;
CREATE TABLE IF NOT EXISTS wiki_revisions (
    page_id INTEGER NOT NULL,
    revision INTEGER NOT NULL CHECK(revision > 0),
    project_id INTEGER,
    path TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    parent_path TEXT,
    sha256 TEXT NOT NULL,
    actor TEXT,
    origin TEXT NOT NULL DEFAULT 'adapter_write' CHECK(origin IN ('adapter_write','legacy_snapshot')),
    recorded_at TEXT,
    PRIMARY KEY(page_id,revision)
);
CREATE INDEX IF NOT EXISTS idx_wiki_revision_scope ON wiki_revisions(project_id,page_id,revision);
CREATE TABLE IF NOT EXISTS wiki_operations (
    scope_identity TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL CHECK(json_valid(result_json)),
    PRIMARY KEY(scope_identity,operation_key)
);
INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(33,'explicit_wiki_namespaces_and_revisions');
