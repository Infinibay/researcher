"""Owner inspection remains available without starting a runtime or minting tokens."""

from contextlib import asynccontextmanager

import httpx
import pytest


@asynccontextmanager
async def owner_client(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        paired = await client.post(
            "/api/session",
            json={"code": "workspace-owner-key-at-least-32-characters"},
            headers={"X-Researcher-Client": "web"},
        )
        assert paired.status_code == 200
        client.headers["X-Researcher-CSRF"] = paired.json()["csrf_token"]
        yield client


async def test_generic_reply_keeps_scope_without_activating_native_work(
    coordination, workspace_app
):
    c = coordination
    c.store.admit(c.spec, conversation_thread="native-owner")
    async with (
        workspace_app.router.lifespan_context(workspace_app),
        owner_client(workspace_app) as owner,
    ):
        reply = await owner.post(
            "/api/chat/101",
            json={
                "message": "A note for the history",
                "thread_id": "native-owner",
                "to_agent": "researcher",
            },
        )
        assert reply.status_code == 201, reply.text
        assert reply.json()["thread_id"] == "native-owner"
        assert reply.json()["delivery"] == "recorded"
        assert c.conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 0
        foreign = await owner.post(
            "/api/chat/202", json={"message": "Foreign", "thread_id": "native-owner"}
        )
        assert foreign.status_code == 404
        assert c.conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == 2
        legacy = await owner.post(
            "/api/chat/101",
            json={"message": "Legacy message", "to_agent": "legacy-worker"},
        )
        assert legacy.status_code == 201
        assert c.conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0] == 1


@pytest.fixture
def workspace_app(coordination):
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    return create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )


async def test_owner_can_inspect_sources_and_closed_task_runs_without_runtime_config(
    coordination, workspace_app
):
    from backend.research.models import SourceDraft

    c = coordination
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="researcher-a",
        permissions={"sources.capture", "sources.read"},
    )
    scope = c.research.authorize(token)
    source = c.research.capture_source(
        scope,
        "capture",
        SourceDraft(
            "attachment", "reference:1", "Policy", "Tax 0.21 means 21 percent."
        ),
        intent={"reference_id": 1},
    )
    run = c.store.admit(c.spec)
    c.store.cancel(101, run.run_id)
    c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    c.conn.commit()
    async with workspace_app.router.lifespan_context(workspace_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=workspace_app),
            base_url="http://localhost",
        ) as anonymous:
            assert (
                await anonymous.get(
                    "/api/projects/101/tasks/1001/workspace",
                    headers={"Authorization": "Bearer " + token},
                )
            ).status_code == 401
        async with owner_client(workspace_app) as owner:
            response = await owner.get("/api/projects/101/tasks/1001/workspace")
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["runtime"]["configured"] is False
            assert data["runs"][0]["run_id"] == run.run_id
            assert data["context"]["context_version"] == 1
            assert str(c.database) not in response.text
            assert (
                await owner.get("/api/projects/202/tasks/1001/workspace")
            ).status_code == 404
            sid = source["source_id"]
            read = await owner.get(
                f"/api/projects/101/research-sources/{sid}?offset=4&max_chars=4"
            )
            assert read.status_code == 200, read.text
            assert read.json()["content"] == "0.21"
            assert read.json()["sha256"] == source["sha256"]
            assert read.json()["next_offset"] == 8
            assert (
                await owner.get(f"/api/projects/202/research-sources/{sid}")
            ).status_code == 404
            assert read.headers.get("Cache-Control") == "no-store"
            assert (
                await owner.get(f"/api/projects/101/runs/{run.run_id}")
            ).status_code == 200


async def test_forward_chat_pages_do_not_skip_middle_messages(
    coordination, workspace_app
):
    c = coordination
    c.conn.execute(
        "INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES('history',101,'user_chat')"
    )
    for n in range(105):
        c.conn.execute(
            "INSERT INTO chat_messages(project_id,thread_id,from_agent,message) VALUES(101,'history','user',?)",
            (f"Message {n}",),
        )
    c.conn.commit()
    async with (
        workspace_app.router.lifespan_context(workspace_app),
        owner_client(workspace_app) as owner,
    ):
        messages = (await owner.get("/api/chat/101?after_id=1&limit=5")).json()
        assert [row["id"] for row in messages] == [2, 3, 4, 5, 6]
