"""Explanatory owner notes have exact durable receipts and cannot activate legacy agents or native work."""

from backend.tests.runtime.test_workspace_delivery import owner_client
from backend.tests.runtime.test_workspace_delivery import workspace_app as workspace_app  # noqa: PLC0414 -- real owner API fixture.


async def test_owner_note_retry_preserves_original_message_without_dispatch(
    coordination, workspace_app
):
    """Repeating an original note after reply loss returns one message/thread, and a thank-you cannot produce an agent event or run."""
    c = coordination
    body = {
        "operation_key": "original-note",
        "message": "Thank you. This is a note, not an assignment.",
        "to_role": "project_lead",
    }
    async with (
        workspace_app.router.lifespan_context(workspace_app),
        owner_client(workspace_app) as owner,
    ):
        first = await owner.post("/api/chat/101", json=body)
        assert first.status_code == 201, first.text
        second = await owner.post("/api/chat/101", json=body)
        assert second.json() == first.json()
        assert first.json()["operation_key"] == body["operation_key"]
        assert first.json()["delivery"] == "recorded"
        assert c.conn.execute("SELECT count(*)FROM chat_messages").fetchone()[0] == 1
        assert c.conn.execute("SELECT count(*)FROM agent_events").fetchone()[0] == 0
        assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 0
        assert (
            await owner.post(
                "/api/chat/101", json={**body, "message": "A different decision"}
            )
        ).status_code == 409
        foreign = await owner.post(
            "/api/chat/202", json={**body, "thread_id": first.json()["thread_id"]}
        )
        assert foreign.status_code == 404


async def test_legacy_note_body_remains_readable_but_no_longer_activates_autonomy(
    coordination, workspace_app
):
    """Clients without operation keys still append notes; historical destination labels are attribution, not authorization to start another engine."""
    async with (
        workspace_app.router.lifespan_context(workspace_app),
        owner_client(workspace_app) as owner,
    ):
        note = await owner.post(
            "/api/chat/101",
            json={"message": "A plain note", "to_agent": "legacy-worker"},
        )
        assert note.status_code == 201
        assert (
            coordination.conn.execute("SELECT count(*)FROM agent_events").fetchone()[0]
            == 0
        )
        assert (
            await owner.post(
                "/api/chat/101",
                json={
                    "message": "Unknown project",
                    "operation_key": "other",
                    "proof": True,
                },
            )
        ).status_code == 422


async def test_paired_endpoint_identity_detects_replaced_database_before_note_mutation(
    coordination, workspace_app, tmp_path, monkeypatch
):
    """An authenticated session and the same URL do not authorize a pending note against a physical replacement of its original database."""
    import sqlite3
    from contextlib import closing
    from pathlib import Path

    # Exercise this paired read-only host explicitly, independent of prior tests.
    monkeypatch.delenv("INFINIBAY_RUNTIME_CONFIG", raising=False)
    async with (
        workspace_app.router.lifespan_context(workspace_app),
        owner_client(workspace_app) as owner,
    ):
        first = (await owner.get("/api/session")).json()["endpoint_id"]
        assert len(first) == 64
        assert (await owner.get("/api/session")).json()["endpoint_id"] == first
        clone = tmp_path / "replacement.db"
        with closing(sqlite3.connect(clone)) as target:
            coordination.conn.backup(target)
        coordination.conn.close()
        clone.replace(Path(coordination.database))
        current = (await owner.get("/api/session")).json()["endpoint_id"]
        assert current != first
        result = await owner.post(
            "/api/chat/101",
            json={
                "operation_key": "original-database-note",
                "message": "Do not cross this database boundary",
            },
            headers={"X-Researcher-Endpoint": first},
        )
        assert result.status_code == 409
        with closing(sqlite3.connect(coordination.database)) as target:
            assert (
                target.execute("SELECT count(*)FROM chat_messages").fetchone()[0] == 0
            )


async def test_frozen_conversation_distinguishes_attributed_owner_note_from_instruction(
    coordination, workspace_app
):
    """A paired explanatory note proves authorship better than an arbitrary sender label, while still granting no work authority."""
    from dataclasses import replace

    from backend.runtime.run_inputs import conversation_history

    c = coordination
    first = c.store.admit(c.spec, conversation_thread="native-notes")
    async with (
        workspace_app.router.lifespan_context(workspace_app),
        owner_client(workspace_app) as owner,
    ):
        receipt = await owner.post(
            "/api/chat/101",
            json={
                "operation_key": "known-owner-note",
                "message": "An example, not another task.",
                "thread_id": "native-notes",
            },
        )
        assert receipt.status_code == 201
    c.store.cancel(101, first.run_id)
    next_run = c.store.admit(
        replace(c.spec, operation_key="next-explicit-instruction"),
        conversation_thread="native-notes",
    )
    with c.store._transaction() as conn:
        history = conversation_history(conn, c.store._row(conn, 101, next_run.run_id))
    note = next(
        item
        for item in history["messages"]
        if item["message_id"] == receipt.json()["id"]
    )
    assert note["kind"] == "owner_note"
    assert note["work_authorized"] is False
