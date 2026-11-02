-- Migration 37: retained per-attempt private development preparations, not publication authority.
CREATE TABLE runtime_development_workspaces (
    attempt_id TEXT PRIMARY KEY REFERENCES runtime_attempts(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runtime_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    fence INTEGER NOT NULL CHECK(fence>=1),
    owner_id TEXT NOT NULL,
    source_json TEXT NOT NULL CHECK(json_valid(source_json)),
    allocation TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN ('preparing','ready','reconciling','quarantined')),
    workspace TEXT UNIQUE,
    device INTEGER,
    inode INTEGER,
    base_sha TEXT,
    base_tree_sha TEXT,
    issue TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    CHECK(state!='ready' OR (workspace IS NOT NULL AND device IS NOT NULL AND device>=0
        AND inode IS NOT NULL AND inode>0 AND base_sha IS NOT NULL AND base_tree_sha IS NOT NULL
        AND length(base_sha) IN (40,64) AND length(base_tree_sha) IN (40,64)
        AND base_sha NOT GLOB '*[^0-9a-f]*' AND base_tree_sha NOT GLOB '*[^0-9a-f]*')),
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE
);
CREATE TRIGGER development_workspace_origin_immutable BEFORE UPDATE ON runtime_development_workspaces
WHEN new.attempt_id IS NOT old.attempt_id OR new.run_id IS NOT old.run_id
 OR new.project_id IS NOT old.project_id OR new.task_id IS NOT old.task_id
 OR new.context_version IS NOT old.context_version OR new.fence IS NOT old.fence
 OR new.owner_id IS NOT old.owner_id OR new.source_json IS NOT old.source_json
 OR new.allocation IS NOT old.allocation OR new.created_at IS NOT old.created_at
BEGIN SELECT RAISE(ABORT,'Development workspace origin is immutable'); END;
CREATE TRIGGER development_workspace_ready_identity_immutable BEFORE UPDATE ON runtime_development_workspaces
WHEN old.workspace IS NOT NULL AND (new.workspace IS NOT old.workspace OR new.device IS NOT old.device
 OR new.inode IS NOT old.inode OR new.base_sha IS NOT old.base_sha OR new.base_tree_sha IS NOT old.base_tree_sha)
BEGIN SELECT RAISE(ABORT,'Prepared development identity is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(37,'retained_development_workspaces');
