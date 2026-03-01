"""SQLite database layer with retry logic and connection management."""

import logging
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Callable, TypeVar

from backend.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_DB_PATH = "/research/pabada.db"


def get_db_path() -> str:
    """Get database path from environment or default."""
    return os.environ.get("PABADA_DB", DEFAULT_DB_PATH)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection with required pragmas. Caller must close it."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -8000")
    return conn


def execute_with_retry(
    fn: Callable[[sqlite3.Connection], T],
    db_path: str | None = None,
    max_retries: int | None = None,
    base_delay: float | None = None,
) -> T:
    """Execute fn(conn) with exponential backoff retry on SQLITE_BUSY/LOCKED."""
    if db_path is None:
        db_path = get_db_path()
    if max_retries is None:
        max_retries = settings.MAX_RETRIES
    if base_delay is None:
        base_delay = settings.RETRY_BASE_DELAY

    last_error: Exception | None = None
    for attempt in range(max_retries):
        conn = get_connection(db_path)
        try:
            result = fn(conn)
            return result
        except sqlite3.OperationalError as e:
            last_error = e
            err_msg = str(e).lower()
            if ("locked" in err_msg or "busy" in err_msg) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(
                    "DB busy/locked (attempt %d/%d), retrying in %.2fs: %s",
                    attempt + 1, max_retries, delay, e,
                )
                time.sleep(delay)
                continue
            raise
        finally:
            conn.close()
    raise sqlite3.OperationalError(
        f"Database busy after {max_retries} retries: {last_error}"
    )


class DBConnection:
    """Context manager for database connections with transaction support.

    Usage:
        with DBConnection() as conn:
            conn.execute("INSERT INTO ...")
            # auto-commits on success, rolls back on exception
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or get_db_path()
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = get_connection(self._db_path)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is None:
            return False
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
                logger.error("DB transaction rolled back: %s", exc_val)
        finally:
            self._conn.close()
            self._conn = None
        return False


@contextmanager
def db_transaction(db_path: str | None = None):
    """Convenience context manager wrapping DBConnection."""
    with DBConnection(db_path) as conn:
        yield conn


def ensure_migrations(db_path: str | None = None) -> None:
    """Run pending schema migrations for existing databases.

    Checks the ``schema_migrations`` table and applies any missing
    migrations.  Safe to call multiple times (idempotent).
    """
    if db_path is None:
        db_path = get_db_path()

    conn = get_connection(db_path)
    try:
        applied = {
            row[0]
            for row in conn.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }

        # Migration 6: add content column to artifacts
        if 6 not in applied:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
            }
            if "content" not in cols:
                conn.execute("ALTER TABLE artifacts ADD COLUMN content TEXT")
                logger.info("Migration 6: added 'content' column to artifacts")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name) "
                "VALUES (6, 'add_artifact_content_column')"
            )
            conn.commit()

        # Migration 7: add 'failed' to tasks.status CHECK constraint
        if 7 not in applied:
            _migrate_7_add_failed_status(conn)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name) "
                "VALUES (7, 'add_failed_task_status')"
            )
            conn.commit()
            logger.info("Migration 7: added 'failed' to tasks.status CHECK")

        # Migration 11: add agent_worktrees table
        if 11 not in applied:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_worktrees (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    repo_id        INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                    agent_id       TEXT NOT NULL,
                    worktree_path  TEXT NOT NULL UNIQUE,
                    branch_name    TEXT,
                    status         TEXT DEFAULT 'active' CHECK(status IN ('active', 'removed')),
                    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cleaned_up_at  DATETIME
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_worktrees_agent_project
                    ON agent_worktrees(agent_id, project_id);
                CREATE INDEX IF NOT EXISTS idx_agent_worktrees_project
                    ON agent_worktrees(project_id);
                CREATE INDEX IF NOT EXISTS idx_agent_worktrees_status
                    ON agent_worktrees(status);
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name) "
                "VALUES (11, 'add_agent_worktrees')"
            )
            conn.commit()
            logger.info("Migration 11: added agent_worktrees table")

        # Migration 12: add pr_number and pr_url columns to tasks
        if 12 not in applied:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "pr_number" not in cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN pr_number INTEGER")
            if "pr_url" not in cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN pr_url TEXT")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name) "
                "VALUES (12, 'add_tasks_pr_fields')"
            )
            conn.commit()
            logger.info("Migration 12: added pr_number and pr_url to tasks")

        # Migration 13: add 'blocked' to tasks.status CHECK constraint
        if 13 not in applied:
            _migrate_13_add_blocked_status(conn)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name) "
                "VALUES (13, 'add_blocked_task_status')"
            )
            conn.commit()
            logger.info("Migration 13: added 'blocked' to tasks.status CHECK")
    except Exception:
        logger.exception("ensure_migrations failed")
        conn.rollback()
    finally:
        conn.close()


def _migrate_7_add_failed_status(conn: sqlite3.Connection) -> None:
    """Rebuild the tasks table with 'failed' added to the status CHECK.

    SQLite enforces CHECK constraints defined at CREATE TABLE time, so
    existing DBs need a table rebuild to allow ``status = 'failed'``.
    """
    # Check if already migrated (idempotent) — try a dummy check
    try:
        conn.execute(
            "INSERT INTO tasks (project_id, type, title, status, created_by) "
            "VALUES (-1, 'plan', '__migration_test__', 'failed', 'migration')"
        )
        # Worked — constraint already allows 'failed', clean up
        conn.execute(
            "DELETE FROM tasks WHERE title = '__migration_test__' AND project_id = -1"
        )
        return
    except sqlite3.IntegrityError:
        # CHECK failed — need to rebuild
        pass

    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute("""
        CREATE TABLE tasks_new (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id           INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            epic_id              INTEGER REFERENCES epics(id) ON DELETE SET NULL,
            milestone_id         INTEGER REFERENCES milestones(id) ON DELETE SET NULL,
            parent_task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            type                 TEXT NOT NULL
                                   CHECK(type IN (
                                     'plan', 'research', 'code', 'review', 'test',
                                     'design', 'integrate', 'documentation', 'bug_fix'
                                   )),
            status               TEXT NOT NULL DEFAULT 'backlog'
                                   CHECK(status IN (
                                     'backlog', 'pending', 'in_progress',
                                     'review_ready', 'rejected', 'done', 'cancelled',
                                     'failed'
                                   )),
            title                TEXT NOT NULL,
            description          TEXT,
            acceptance_criteria  TEXT,
            context_json         TEXT,
            priority             INTEGER DEFAULT 2 CHECK(priority BETWEEN 1 AND 5),
            estimated_complexity TEXT DEFAULT 'medium'
                                   CHECK(estimated_complexity IN (
                                     'trivial', 'low', 'medium', 'high', 'very_high'
                                   )),
            branch_name          TEXT,
            assigned_to          TEXT,
            reviewer             TEXT,
            created_by           TEXT NOT NULL DEFAULT 'orchestrator',
            retry_count          INTEGER DEFAULT 0,
            created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at         DATETIME
        )
    """)

    conn.execute("INSERT INTO tasks_new SELECT * FROM tasks")

    # Drop old triggers that reference tasks
    for trigger in (
        "tasks_fts_ai", "tasks_fts_ad", "tasks_fts_au",
        "trg_tasks_audit_insert", "trg_tasks_audit_status",
        "trg_tasks_audit_update",
    ):
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")

    # Drop FTS virtual table before dropping tasks (content=tasks backing)
    conn.execute("DROP TABLE IF EXISTS tasks_fts")

    conn.execute("DROP TABLE tasks")
    conn.execute("ALTER TABLE tasks_new RENAME TO tasks")

    # Recreate indexes
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS idx_tasks_project    ON tasks(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_type       ON tasks(type)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_priority   ON tasks(priority DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_epic       ON tasks(epic_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_milestone  ON tasks(milestone_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_assigned   ON tasks(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_reviewer   ON tasks(reviewer)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_branch     ON tasks(branch_name)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by)",
    ):
        conn.execute(idx_sql)

    # Recreate FTS virtual table and rebuild index
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
            title, description, acceptance_criteria,
            content=tasks, content_rowid=id
        )
    """)
    conn.execute("""
        INSERT INTO tasks_fts(tasks_fts) VALUES('rebuild')
    """)

    # Recreate FTS triggers
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS tasks_fts_ai AFTER INSERT ON tasks BEGIN
            INSERT INTO tasks_fts(rowid, title, description, acceptance_criteria)
            VALUES (new.id, new.title, COALESCE(new.description, ''),
                    COALESCE(new.acceptance_criteria, ''));
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS tasks_fts_ad AFTER DELETE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts, rowid, title, description, acceptance_criteria)
            VALUES ('delete', old.id, COALESCE(old.title, ''),
                    COALESCE(old.description, ''),
                    COALESCE(old.acceptance_criteria, ''));
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS tasks_fts_au AFTER UPDATE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts, rowid, title, description, acceptance_criteria)
            VALUES ('delete', old.id, COALESCE(old.title, ''),
                    COALESCE(old.description, ''),
                    COALESCE(old.acceptance_criteria, ''));
            INSERT INTO tasks_fts(rowid, title, description, acceptance_criteria)
            VALUES (new.id, new.title, COALESCE(new.description, ''),
                    COALESCE(new.acceptance_criteria, ''));
        END
    """)

    # Recreate audit triggers
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_insert AFTER INSERT ON tasks
        BEGIN
            INSERT INTO events_log(project_id, event_type, event_source,
                                   entity_type, entity_id, event_data_json)
            VALUES (
                new.project_id, 'task_created',
                COALESCE(new.created_by, 'system'), 'task', new.id,
                json_object('title', new.title, 'type', new.type,
                            'status', new.status, 'assigned_to', new.assigned_to)
            );
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_status
        AFTER UPDATE OF status ON tasks
        WHEN old.status != new.status
        BEGIN
            INSERT INTO events_log(project_id, event_type, event_source,
                                   entity_type, entity_id, event_data_json)
            VALUES (
                new.project_id, 'task_status_changed', 'system', 'task', new.id,
                json_object('old_status', old.status, 'new_status', new.status,
                            'assigned_to', new.assigned_to)
            );
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_update AFTER UPDATE ON tasks
        WHEN old.status = new.status
         AND (old.title != new.title OR old.assigned_to IS NOT new.assigned_to
              OR old.reviewer IS NOT new.reviewer
              OR old.branch_name IS NOT new.branch_name)
        BEGIN
            INSERT INTO events_log(project_id, event_type, event_source,
                                   entity_type, entity_id, event_data_json)
            VALUES (
                new.project_id, 'task_updated', 'system', 'task', new.id,
                json_object('title', new.title, 'assigned_to', new.assigned_to,
                            'reviewer', new.reviewer,
                            'branch_name', new.branch_name)
            );
        END
    """)

    conn.execute("PRAGMA foreign_keys = ON")


def _migrate_13_add_blocked_status(conn: sqlite3.Connection) -> None:
    """Rebuild the tasks table with 'blocked' added to the status CHECK.

    Same technique as migration 7 — SQLite requires a table rebuild to
    modify a CHECK constraint.
    """
    # Check if already migrated (idempotent)
    try:
        conn.execute(
            "INSERT INTO tasks (project_id, type, title, status, created_by) "
            "VALUES (-1, 'plan', '__migration_test__', 'blocked', 'migration')"
        )
        conn.execute(
            "DELETE FROM tasks WHERE title = '__migration_test__' AND project_id = -1"
        )
        return  # CHECK already allows 'blocked'
    except sqlite3.IntegrityError:
        pass  # Need to rebuild

    # Get current column names (order matters for SELECT *)
    col_info = conn.execute("PRAGMA table_info(tasks)").fetchall()
    col_names = [row[1] for row in col_info]

    # Commit any pending transaction so the table rebuild can proceed
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute("""
        CREATE TABLE tasks_new (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id           INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            epic_id              INTEGER REFERENCES epics(id) ON DELETE SET NULL,
            milestone_id         INTEGER REFERENCES milestones(id) ON DELETE SET NULL,
            parent_task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            type                 TEXT NOT NULL
                                   CHECK(type IN (
                                     'plan', 'research', 'code', 'review', 'test',
                                     'design', 'integrate', 'documentation', 'bug_fix'
                                   )),
            status               TEXT NOT NULL DEFAULT 'backlog'
                                   CHECK(status IN (
                                     'backlog', 'pending', 'in_progress',
                                     'review_ready', 'rejected', 'done', 'cancelled',
                                     'failed', 'blocked'
                                   )),
            title                TEXT NOT NULL,
            description          TEXT,
            acceptance_criteria  TEXT,
            context_json         TEXT,
            priority             INTEGER DEFAULT 2 CHECK(priority BETWEEN 1 AND 5),
            estimated_complexity TEXT DEFAULT 'medium'
                                   CHECK(estimated_complexity IN (
                                     'trivial', 'low', 'medium', 'high', 'very_high'
                                   )),
            branch_name          TEXT,
            pr_number            INTEGER,
            pr_url               TEXT,
            assigned_to          TEXT,
            reviewer             TEXT,
            created_by           TEXT NOT NULL DEFAULT 'orchestrator',
            retry_count          INTEGER DEFAULT 0,
            created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at         DATETIME
        )
    """)

    # Build INSERT that maps old columns to new positions.
    # pr_number and pr_url may not exist yet if migration 12 hasn't run
    # (though it should have by now). Handle gracefully.
    new_cols = [
        "id", "project_id", "epic_id", "milestone_id", "parent_task_id",
        "type", "status", "title", "description", "acceptance_criteria",
        "context_json", "priority", "estimated_complexity", "branch_name",
        "pr_number", "pr_url", "assigned_to", "reviewer", "created_by",
        "retry_count", "created_at", "completed_at",
    ]
    # Only SELECT columns that exist in the old table
    select_exprs = []
    for c in new_cols:
        if c in col_names:
            select_exprs.append(c)
        else:
            select_exprs.append(f"NULL AS {c}")

    conn.execute(
        f"INSERT INTO tasks_new ({', '.join(new_cols)}) "
        f"SELECT {', '.join(select_exprs)} FROM tasks"
    )

    # Drop old triggers
    for trigger in (
        "tasks_fts_ai", "tasks_fts_ad", "tasks_fts_au",
        "trg_tasks_audit_insert", "trg_tasks_audit_status",
        "trg_tasks_audit_update",
    ):
        conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")

    conn.execute("DROP TABLE IF EXISTS tasks_fts")
    conn.execute("DROP TABLE tasks")
    conn.execute("ALTER TABLE tasks_new RENAME TO tasks")

    # Recreate indexes
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS idx_tasks_project    ON tasks(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_type       ON tasks(type)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_priority   ON tasks(priority DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_epic       ON tasks(epic_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_milestone  ON tasks(milestone_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_assigned   ON tasks(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_reviewer   ON tasks(reviewer)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_branch     ON tasks(branch_name)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by)",
    ):
        conn.execute(idx_sql)

    # Recreate FTS
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
            title, description, acceptance_criteria,
            content=tasks, content_rowid=id
        )
    """)
    conn.execute("INSERT INTO tasks_fts(tasks_fts) VALUES('rebuild')")

    # Recreate FTS triggers
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS tasks_fts_ai AFTER INSERT ON tasks BEGIN
            INSERT INTO tasks_fts(rowid, title, description, acceptance_criteria)
            VALUES (new.id, new.title, COALESCE(new.description, ''),
                    COALESCE(new.acceptance_criteria, ''));
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS tasks_fts_ad AFTER DELETE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts, rowid, title, description, acceptance_criteria)
            VALUES ('delete', old.id, COALESCE(old.title, ''),
                    COALESCE(old.description, ''),
                    COALESCE(old.acceptance_criteria, ''));
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS tasks_fts_au AFTER UPDATE ON tasks BEGIN
            INSERT INTO tasks_fts(tasks_fts, rowid, title, description, acceptance_criteria)
            VALUES ('delete', old.id, COALESCE(old.title, ''),
                    COALESCE(old.description, ''),
                    COALESCE(old.acceptance_criteria, ''));
            INSERT INTO tasks_fts(rowid, title, description, acceptance_criteria)
            VALUES (new.id, new.title, COALESCE(new.description, ''),
                    COALESCE(new.acceptance_criteria, ''));
        END
    """)

    # Recreate audit triggers
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_insert AFTER INSERT ON tasks
        BEGIN
            INSERT INTO events_log(project_id, event_type, event_source,
                                   entity_type, entity_id, event_data_json)
            VALUES (
                new.project_id, 'task_created',
                COALESCE(new.created_by, 'system'), 'task', new.id,
                json_object('title', new.title, 'type', new.type,
                            'status', new.status, 'assigned_to', new.assigned_to)
            );
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_status
        AFTER UPDATE OF status ON tasks
        WHEN old.status != new.status
        BEGIN
            INSERT INTO events_log(project_id, event_type, event_source,
                                   entity_type, entity_id, event_data_json)
            VALUES (
                new.project_id, 'task_status_changed', 'system', 'task', new.id,
                json_object('old_status', old.status, 'new_status', new.status,
                            'assigned_to', new.assigned_to)
            );
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_tasks_audit_update AFTER UPDATE ON tasks
        WHEN old.status = new.status
         AND (old.title != new.title OR old.assigned_to IS NOT new.assigned_to
              OR old.reviewer IS NOT new.reviewer
              OR old.branch_name IS NOT new.branch_name)
        BEGIN
            INSERT INTO events_log(project_id, event_type, event_source,
                                   entity_type, entity_id, event_data_json)
            VALUES (
                new.project_id, 'task_updated', 'system', 'task', new.id,
                json_object('title', new.title, 'assigned_to', new.assigned_to,
                            'reviewer', new.reviewer,
                            'branch_name', new.branch_name)
            );
        END
    """)

    conn.execute("PRAGMA foreign_keys = ON")


def sanitize_fts5_query(query: str) -> str:
    """Sanitize a user query for safe use in FTS5 MATCH.

    Wraps each token in double quotes so FTS5 treats them as literal
    strings rather than column names or operators (e.g. ``RTL``
    won't be interpreted as ``RTL:`` column prefix).
    """
    tokens = query.split()
    if not tokens:
        return '""'
    return " ".join(f'"{t}"' for t in tokens)
