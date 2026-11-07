-- Migration67: bind historical labels once to an existing project/repository identity.
CREATE UNIQUE INDEX repository_project_identity ON repositories(id,project_id);
CREATE TABLE branches_scoped (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    repo_name TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    base_branch TEXT DEFAULT 'main',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','merged','abandoned','stale')),
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    merged_at DATETIME,
    last_commit_hash TEXT,
    last_commit_at DATETIME,
    repo_id INTEGER,
    FOREIGN KEY(repo_id,project_id) REFERENCES repositories(id,project_id) ON DELETE RESTRICT,
    UNIQUE(repo_id,branch_name)
);
INSERT INTO branches_scoped
SELECT b.*,r.id FROM branches b LEFT JOIN repositories r ON r.project_id=b.project_id AND r.name=b.repo_name;
UPDATE sqlite_sequence SET seq=MAX(seq,coalesce((SELECT seq FROM sqlite_sequence WHERE name='branches'),0)) WHERE name='branches_scoped';
DROP TABLE branches;
ALTER TABLE branches_scoped RENAME TO branches;
CREATE INDEX idx_branches_project ON branches(project_id);
CREATE INDEX idx_branches_task ON branches(task_id);
CREATE INDEX idx_branches_repo ON branches(repo_id);
CREATE INDEX idx_branches_status ON branches(status);
CREATE UNIQUE INDEX unresolved_branch_names ON branches(project_id,repo_name,branch_name) WHERE repo_id IS NULL;
ALTER TABLE code_reviews ADD COLUMN repo_id INTEGER REFERENCES repositories(id) ON DELETE RESTRICT;
UPDATE code_reviews SET repo_id=(SELECT r.id FROM repositories r WHERE r.project_id=code_reviews.project_id AND r.name=code_reviews.repo_name);
CREATE INDEX idx_code_reviews_repo ON code_reviews(repo_id);
-- Compatibility inserts resolve only at creation; later registration never adopts old unresolved rows.
CREATE TRIGGER bind_branch_repository AFTER INSERT ON branches WHEN NEW.repo_id IS NULL
BEGIN
    UPDATE branches SET repo_id=(SELECT id FROM repositories WHERE project_id=NEW.project_id AND name=NEW.repo_name) WHERE id=NEW.id;
END;
CREATE TRIGGER bind_review_repository AFTER INSERT ON code_reviews WHEN NEW.repo_id IS NULL
BEGIN
    UPDATE code_reviews SET repo_id=(SELECT id FROM repositories WHERE project_id=NEW.project_id AND name=NEW.repo_name) WHERE id=NEW.id;
END;
CREATE TRIGGER review_repository_scope_insert BEFORE INSERT ON code_reviews
WHEN NEW.repo_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM repositories WHERE id=NEW.repo_id AND project_id=NEW.project_id)
BEGIN SELECT RAISE(ABORT,'Review repository belongs to another project'); END;
CREATE TRIGGER review_repository_scope_update BEFORE UPDATE OF repo_id,project_id ON code_reviews
WHEN NEW.repo_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM repositories WHERE id=NEW.repo_id AND project_id=NEW.project_id)
BEGIN SELECT RAISE(ABORT,'Review repository belongs to another project'); END;
INSERT INTO schema_migrations(version,name) VALUES(67,'project_repository_git_identity');
