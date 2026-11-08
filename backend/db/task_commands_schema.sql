-- Migration70: extend immutable owner planning receipts to exact task creation.
DROP TRIGGER owner_planning_command_immutable;
CREATE TABLE owner_planning_commands_next (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_key TEXT NOT NULL CHECK(length(operation_key) BETWEEN 1 AND 128),
    kind TEXT NOT NULL CHECK(kind IN ('group.create','milestone.create','task.create')),
    request_json TEXT NOT NULL CHECK(json_valid(request_json)),
    response_json TEXT NOT NULL CHECK(json_valid(response_json)),
    resource_id INTEGER NOT NULL CHECK(resource_id>0),
    created_at REAL NOT NULL,
    PRIMARY KEY(project_id,operation_key)
);
INSERT INTO owner_planning_commands_next SELECT * FROM owner_planning_commands;
DROP TABLE owner_planning_commands;
ALTER TABLE owner_planning_commands_next RENAME TO owner_planning_commands;
CREATE TRIGGER owner_planning_command_immutable BEFORE UPDATE ON owner_planning_commands
BEGIN SELECT RAISE(ABORT,'Original owner planning requests and receipts are immutable'); END;
INSERT INTO schema_migrations(version,name) VALUES(70,'recoverable_owner_task_commands');
