-- Migration60: explicit owner budget revision and immutable original decision receipts.
ALTER TABLE runtime_project_budgets ADD COLUMN revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0);
CREATE TABLE runtime_project_budget_changes (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_key TEXT NOT NULL,
    request_json TEXT NOT NULL CHECK(json_valid(request_json)),
    receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
    PRIMARY KEY(project_id,operation_key)
);
CREATE TRIGGER project_budget_change_immutable BEFORE UPDATE ON runtime_project_budget_changes
BEGIN SELECT RAISE(ABORT,'Project budget decision history is immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(60,'owner_project_budget_revisions');
