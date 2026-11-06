"""Real gateway → HTTP authorization → SQLite tests preserve host-selected project boundaries without a model or a fabricated authorization port."""

import httpx

from backend.tests.research.test_acquisition import reference


async def test_mcp_gateway_uses_real_grant_scope_and_honors_withdrawal(
    research_store, research_scope, db_conn, tmp_path, monkeypatch
):
    """Only the actual grant's attachments are visible; forged arguments and invalid/retired grants never become another project's authority."""
    from backend.api import config
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.research.async_http_client import AsyncResearcherHTTPClient
    from backend.research.stdio_server import BusinessGateway

    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    _, _, own = reference(research_store, db_conn, tmp_path)
    _, _, foreign = reference(research_store, db_conn, tmp_path, project_id=202)
    token = research_store.issue_grant(
        project_id=101, task_id=1001, agent_id="native-mcp-fixture",
        permissions={"sources.read"},
    )
    scope = research_store.authorize(token)
    app = create_app(access=LocalAccess(pairing_key="synthetic-mcp-owner-pairing-code-at-least-32"))
    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1:8000", token, transport=httpx.ASGITransport(app=app)
    ) as client:
        gateway = BusinessGateway(client)
        listed = await gateway.call("researcher_reference_list", {})
        assert isinstance(listed, dict), listed
        assert [item["id"] for item in listed["references"]] == [own.id]
        assert own.id != foreign.id
        forged = await gateway.call("researcher_reference_list", {"project_id": 202})
        assert forged.isError
        research_store.revoke_grant(scope.grant_id)
        retired = await gateway.call("researcher_reference_list", {})
        assert retired.isError
    assert client.closed
    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1:8000", "invalid-host-token", transport=httpx.ASGITransport(app=app)
    ) as invalid:
        assert (await BusinessGateway(invalid).call("researcher_reference_list", {})).isError
