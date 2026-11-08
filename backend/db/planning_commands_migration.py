"""Reverse only unused owner planning infrastructure without discarding a recorded request."""


def restore_planning_commands_schema(conn):
    """Restore schema68 atomically only when no planning receipt or later migration exists."""
    if conn.in_transaction:
        raise RuntimeError("Planning inverse requires an idle connection")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version>69 LIMIT 1").fetchone():
            raise RuntimeError("Planning inverse refuses newer schema")
        if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=69").fetchone():
            conn.rollback()
            return
        if conn.execute("SELECT 1 FROM owner_planning_commands LIMIT 1").fetchone():
            raise RuntimeError("Planning inverse refuses recorded requests")
        conn.execute("DROP TABLE owner_planning_commands")
        conn.execute("DELETE FROM schema_migrations WHERE version=69")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
