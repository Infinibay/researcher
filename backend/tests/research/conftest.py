import pytest


@pytest.fixture
def research_store(_isolated_db, db_conn):
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.tools.base.db import ensure_migrations

    ensure_migrations(_isolated_db)
    db_conn.execute("INSERT INTO projects(id,name) VALUES (101,'Alpha'),(202,'Beta')")
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status,created_by) VALUES (1001,101,'research','Research','in_progress','user'),(2002,202,'research','Research','in_progress','user')"
    )
    db_conn.commit()
    return SQLiteResearchStore(_isolated_db)


@pytest.fixture
def research_scope(research_store):
    token = research_store.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="researcher-a",
        permissions={
            "sources.read",
            "sources.capture",
            "findings.read",
            "findings.write",
            "reports.read",
            "reports.write",
        },
    )
    return research_store.authorize(token)
