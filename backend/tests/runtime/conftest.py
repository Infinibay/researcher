"""Shared real SQLite coordination fixture; no model or external service."""

from types import SimpleNamespace

import pytest

from backend.tools.base.db import ensure_migrations


@pytest.fixture
def coordination(_isolated_db, db_conn):
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime import contracts
    from backend.runtime.sqlite_runs import SQLiteRunStore

    ensure_migrations(_isolated_db)
    db_conn.execute("INSERT INTO projects(id,name) VALUES(101,'Alpha'),(202,'Beta')")
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Policy','in_progress'),(1002,101,'research','Second','pending'),(2002,202,'research','Policy','in_progress')"
    )
    db_conn.commit()
    now = [1000.0]
    store = SQLiteRunStore(_isolated_db, clock=lambda: now[0])
    spec = contracts.RunSpec(
        project_id=101,
        task_id=1001,
        actor_id="researcher-a",
        context_version=1,
        operation_key="request-1",
        prompt="Contrast source and code",
        runtime="codex",
    )
    return SimpleNamespace(
        store=store,
        spec=spec,
        now=now,
        contracts=contracts,
        conn=db_conn,
        research=SQLiteResearchStore(_isolated_db, clock=lambda: now[0]),
        database=_isolated_db,
    )
