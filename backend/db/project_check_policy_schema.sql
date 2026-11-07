-- Migration65: explicit owner choice for future code acceptances; no invented legacy policy.
CREATE TABLE runtime_project_check_policies (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL CHECK(revision>0),
    mode TEXT NOT NULL CHECK(mode IN ('require_tests','allow_missing'))
);
CREATE TABLE runtime_project_check_policy_changes (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_key TEXT NOT NULL,
    request_json TEXT NOT NULL CHECK(json_valid(request_json)),
    receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
    PRIMARY KEY(project_id,operation_key)
);
CREATE TRIGGER project_check_policy_change_immutable BEFORE UPDATE ON runtime_project_check_policy_changes
BEGIN SELECT RAISE(ABORT,'Project check policy history is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(65,'owner_project_check_policy');
