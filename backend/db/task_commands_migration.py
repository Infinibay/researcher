"""Reverse task receipt support only when no task request or newer schema would be lost."""


def restore_task_commands_schema(conn):
    """Restore the exact schema69 receipt table while retaining every original group/milestone receipt."""
    if conn.in_transaction:
        raise RuntimeError('Task receipt inverse requires an idle connection')
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT 1 FROM schema_migrations WHERE version>70 LIMIT 1').fetchone():
            raise RuntimeError('Task receipt inverse refuses newer schema')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=70').fetchone():
            conn.rollback()
            return
        if conn.execute("SELECT 1 FROM owner_planning_commands WHERE kind='task.create' LIMIT 1").fetchone():
            raise RuntimeError('Task receipt inverse refuses recorded task requests')
        conn.execute('DROP TRIGGER owner_planning_command_immutable')
        conn.execute('''CREATE TABLE owner_planning_commands_previous (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            operation_key TEXT NOT NULL CHECK(length(operation_key) BETWEEN 1 AND 128),
            kind TEXT NOT NULL CHECK(kind IN ('group.create','milestone.create')),
            request_json TEXT NOT NULL CHECK(json_valid(request_json)),
            response_json TEXT NOT NULL CHECK(json_valid(response_json)),
            resource_id INTEGER NOT NULL CHECK(resource_id>0),
            created_at REAL NOT NULL,
            PRIMARY KEY(project_id,operation_key)
        )''')
        conn.execute('INSERT INTO owner_planning_commands_previous SELECT * FROM owner_planning_commands')
        conn.execute('DROP TABLE owner_planning_commands')
        conn.execute('ALTER TABLE owner_planning_commands_previous RENAME TO owner_planning_commands')
        conn.execute("CREATE TRIGGER owner_planning_command_immutable BEFORE UPDATE ON owner_planning_commands BEGIN SELECT RAISE(ABORT,'Original owner planning requests and receipts are immutable'); END")
        conn.execute('DELETE FROM schema_migrations WHERE version=70')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
