"""Immediate host withdrawal must also fence already-authorized DB writers."""

import asyncio
import threading

import pytest


def grant(coordination):
    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "owner", lease_seconds=30)
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="researcher-a",
        permissions={"sources.capture", "sources.read"},
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    return token, scope


def test_runtime_bound_grants_require_the_current_hosts_live_registration(coordination):
    from backend.research.models import ResearchForbidden
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.live_grants import LiveGrants

    c = coordination
    token, scope = grant(c)
    gate = LiveGrants()
    store = SQLiteResearchStore(
        c.database, clock=lambda: c.now[0], runtime_authority=gate.allows
    )
    with pytest.raises(ResearchForbidden):
        store.authorize(token)
    gate.activate(scope.grant_id)
    assert store.authorize(token) == scope
    gate.withdraw(scope.grant_id)
    with pytest.raises(ResearchForbidden):
        store.authorize(token)
    gate.activate(scope.grant_id)
    with pytest.raises(ResearchForbidden):
        SQLiteResearchStore(
            c.database, clock=lambda: c.now[0], runtime_authority=LiveGrants().allows
        ).authorize(token)


async def test_cached_scope_waiting_for_sqlite_cannot_write_after_live_withdrawal(
    coordination, monkeypatch
):
    from backend.research import sqlite_store
    from backend.research.models import ResearchForbidden, SourceDraft
    from backend.runtime.live_grants import LiveGrants

    c = coordination
    token, scope = grant(c)
    gate = LiveGrants()
    gate.activate(scope.grant_id)
    store = sqlite_store.SQLiteResearchStore(
        c.database, clock=lambda: c.now[0], runtime_authority=gate.allows
    )
    assert store.authorize(token) == scope
    reached = threading.Event()
    connect = sqlite_store.connect

    def observe(database, **options):
        connection = connect(database, **options)
        connection.set_trace_callback(
            lambda sql: reached.set() if sql == "BEGIN IMMEDIATE" else None
        )
        return connection

    monkeypatch.setattr(sqlite_store, "connect", observe)
    c.conn.execute("BEGIN IMMEDIATE")
    pending = asyncio.create_task(
        asyncio.to_thread(
            store.capture_source,
            scope,
            "late",
            SourceDraft("web", "https://example.org/policy", "Policy", "Claim"),
            intent={"url": "https://example.org/policy"},
        )
    )
    try:
        assert await asyncio.to_thread(reached.wait, 1), (
            "Writer did not reach real SQLite admission"
        )
        gate.withdraw(scope.grant_id)
        assert not pending.done(), "Writer should still wait behind held DB lock"
    finally:
        c.conn.rollback()
    with pytest.raises(ResearchForbidden):
        await pending
    assert c.conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0
