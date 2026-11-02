"""Composition for retained finding readers, distinct from native grant authority."""

from sqlite3 import Error as SQLiteError

from backend.knowledge.findings import FindingStore
from backend.research.models import positive_id
from backend.tools.base.db import ensure_migrations, get_db_path

FINDING_READ_ERRORS = (ValueError, LookupError, RuntimeError, OSError, SQLiteError)


def finding_reader(tool, task_id=None):
    """Require project identity and resolve a task filter without widening project scope."""
    project_id = tool._validate_project_context()
    positive_id(project_id)
    selected = tool.task_id if task_id is None else task_id
    if selected == 0 and type(selected) is int:
        selected = None
    elif selected is not None:
        positive_id(selected)
    database = get_db_path()
    ensure_migrations(database, existing_only=True)
    return FindingStore(database), project_id, selected
