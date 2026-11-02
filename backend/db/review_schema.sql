-- Migration 34: immutable reviewed subjects and original-attempt decisions.
ALTER TABLE runtime_runs ADD COLUMN execution_kind TEXT NOT NULL DEFAULT 'research'
    CHECK(execution_kind IN ('research','finding_review'));
DROP INDEX idx_runtime_active_task;
CREATE UNIQUE INDEX idx_runtime_active_task ON runtime_runs(project_id,task_id,execution_kind)
    WHERE status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review');
CREATE TABLE finding_review_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE REFERENCES runtime_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    finding_id INTEGER NOT NULL,
    context_version INTEGER NOT NULL CHECK(context_version>=1),
    subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
    snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),
    author_run_id TEXT NOT NULL,
    author_attempt_id TEXT NOT NULL,
    author_actor_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(project_id,task_id) REFERENCES tasks(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,finding_id) REFERENCES findings(project_id,id) ON DELETE CASCADE
);
CREATE INDEX idx_finding_reviews_subject ON finding_review_requests(project_id,finding_id,created_at);
CREATE TABLE finding_review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE REFERENCES finding_review_requests(run_id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL,
    finding_id INTEGER NOT NULL,
    subject_sha256 TEXT NOT NULL CHECK(length(subject_sha256)=64),
    reviewer_attempt_id TEXT NOT NULL,
    reviewer_actor_id TEXT NOT NULL,
    reviewer_fence INTEGER NOT NULL CHECK(reviewer_fence>=1),
    verdict TEXT NOT NULL CHECK(verdict IN ('supported','needs_revision','inconclusive')),
    decision_json TEXT NOT NULL CHECK(json_valid(decision_json)),
    created_at REAL NOT NULL,
    FOREIGN KEY(project_id,finding_id) REFERENCES findings(project_id,id) ON DELETE CASCADE
);
CREATE TRIGGER review_subject_immutable BEFORE UPDATE ON finding_review_requests
BEGIN
    SELECT RAISE(ABORT,'Review subjects are immutable; admit a new review');
END;
CREATE UNIQUE INDEX idx_review_decision_project_identity ON finding_review_decisions(project_id,id);
CREATE TABLE finding_review_evidence (
    project_id INTEGER NOT NULL,
    decision_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
    metadata_sha256 TEXT NOT NULL CHECK(length(metadata_sha256)=64),
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
    PRIMARY KEY(decision_id,source_id),
    FOREIGN KEY(project_id,decision_id) REFERENCES finding_review_decisions(project_id,id) ON DELETE CASCADE,
    FOREIGN KEY(project_id,source_id) REFERENCES research_sources(project_id,id) ON DELETE RESTRICT
);
CREATE TRIGGER review_evidence_immutable BEFORE UPDATE ON finding_review_evidence
BEGIN
    SELECT RAISE(ABORT,'Review evidence is immutable; admit a new review');
END;
CREATE TRIGGER review_decision_immutable BEFORE UPDATE ON finding_review_decisions
BEGIN
    SELECT RAISE(ABORT,'Review decisions are immutable; admit a new review');
END;
INSERT INTO schema_migrations(version,name) VALUES(34,'version_bound_finding_review');
