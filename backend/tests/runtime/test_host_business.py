"""The host owns business HTTP; schemas and handlers are transport independent."""

import asyncio
import json

import httpx
import pytest


async def test_host_catalog_keeps_credentials_and_authority_out_of_tool_arguments():
    from backend.runtime.business_mediation import BUSINESS_NAMES, BusinessTools
    from backend.runtime.host_business import host_business

    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"project_id": 101, "references": []})

    withdrawn = []
    async with host_business(
        api_url="http://127.0.0.1",
        token="HOST_ONLY_TOKEN",
        withdraw=lambda: withdrawn.append(True),
        transport=httpx.MockTransport(handle),
    ) as peer:
        tools = await BusinessTools.connect(peer)
        assert {t["name"] for t in tools.catalog} == BUSINESS_NAMES
        assert all(
            not {"token", "project_id", "task_id", "agent_id", "api_url"}
            & set(t["inputSchema"].get("properties", {}))
            for t in tools.catalog
        )
        result = await tools.call(
            {"tool": "researcher_reference_list", "arguments": {}}
        )
        assert (
            result["success"]
            and json.loads(result["contentItems"][0]["text"])["project_id"] == 101
        )
        invalid = await tools.call(
            {"tool": "researcher_reference_list", "arguments": {"project_id": 202}}
        )
        assert not invalid["success"] and len(seen) == 1
        assert seen[0].headers["Authorization"] == "Bearer HOST_ONLY_TOKEN"
    assert peer.closed and withdrawn == [True]


async def test_business_close_withdraws_server_authority_before_cancelling_io():
    from backend.runtime.host_business import host_business

    reached, cancelled = asyncio.Event(), asyncio.Event()
    withdrawn = [False]

    async def handle(request):
        reached.set()
        try:
            await asyncio.Event().wait()
        finally:
            assert withdrawn[0], "HTTP cancellation preceded authority withdrawal"
            cancelled.set()

    async with host_business(
        api_url="http://127.0.0.1",
        token="HOST_ONLY_TOKEN",
        withdraw=lambda: withdrawn.__setitem__(0, True),
        transport=httpx.MockTransport(handle),
    ) as peer:
        pending = asyncio.create_task(peer.call_tool("researcher_reference_list", {}))
        await asyncio.wait_for(reached.wait(), 1)
        await peer.aclose()
        result = await pending
        assert result.isError and cancelled.is_set() and peer.closed


async def test_business_withdrawn_scope_never_starts_another_request():
    from backend.runtime.host_business import host_business

    calls = []
    active = [True]

    async def handle(request):
        calls.append(request)
        return httpx.Response(200, json={})

    async with host_business(
        api_url="http://127.0.0.1",
        token="HOST_ONLY_TOKEN",
        active=lambda: active[0],
        withdraw=lambda: None,
        transport=httpx.MockTransport(handle),
    ) as peer:
        active[0] = False
        assert (await peer.call_tool("researcher_reference_list", {})).isError
        assert not calls


async def test_business_wire_schema_is_compact_but_keeps_real_title_field():
    from backend.runtime.host_business import host_business

    async with host_business(
        api_url="http://127.0.0.1", token="HOST_ONLY_TOKEN", withdraw=lambda: None
    ) as peer:
        catalog = {
            tool.name: tool.inputSchema for tool in (await peer.list_tools()).tools
        }
        questions = catalog["researcher_ask_user"]
        assert "$defs" not in questions and "$ref" not in json.dumps(questions)
        assert (
            questions["properties"]["questions"]["items"]["properties"]["id"]["type"]
            == "string"
        )
        report = catalog["researcher_report_write"]
        assert "title" in report["properties"] and "title" in report["required"]
        assert report["properties"]["title"] == {"type": "string"}


@pytest.mark.parametrize(
    "media_type",
    [
        "text/plain",
        "application/pdf",
        "application/pdf-url",
        "application/pdf-paper-arxiv",
        "application/pdf-paper-doi",
        "application/pdf-semantic",
    ],
)
async def test_host_business_uses_real_api_scope_and_persists_one_report(
    coordination, tmp_path, monkeypatch, media_type
):
    """Exercise native tool dispatch through real HTTP, source capture and draft reports."""
    import time

    from backend.api import config
    from backend.api.main import create_app
    from backend.research.models import PERMISSIONS
    from backend.runtime.business_mediation import BusinessTools
    from backend.runtime.host_business import host_business

    c = coordination
    c.now[0] = time.time()
    uploads = tmp_path / "uploads"
    directory = uploads / "101/uploads"
    directory.mkdir(parents=True)
    source = directory / "policy.txt"
    if media_type.startswith("application/pdf"):
        from backend.tests.research.pdf_fixtures import pdf_bytes

        source.write_bytes(pdf_bytes("Tax rates are fractions."))
    else:
        source.write_text("Tax rates are fractions.")
    c.conn.execute(
        "INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) VALUES(7,101,'policy.txt',?,?,?)",
        (
            str(source),
            source.stat().st_size,
            "application/pdf"
            if media_type.startswith("application/pdf")
            else media_type,
        ),
    )
    c.conn.execute(
        "INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) VALUES(8,202,'policy.txt',?,?,'text/plain')",
        (str(source), source.stat().st_size),
    )
    c.conn.commit()
    monkeypatch.setattr(config, "UPLOAD_DIR", str(uploads))
    capture_tool = "researcher_capture_reference"
    capture_arguments = {"reference_file_id": 7}
    if media_type in (
        "application/pdf-url",
        "application/pdf-paper-arxiv",
        "application/pdf-paper-doi",
        "application/pdf-semantic",
    ):
        from backend.api import research_dependencies
        from backend.tests.research.test_pdf_web import pdf_response
        from backend.tests.research.test_web_fetcher import fetcher

        responses = [pdf_response(source.read_bytes())]

        def configured(**options):
            """Use real URL policy and owned parser, replacing only DNS/socket I/O."""
            return fetcher(responses, **options)[0]

        monkeypatch.setattr(research_dependencies, "PublicWebFetcher", configured)
        capture_tool = "researcher_capture_web"
        capture_arguments = {"url": "https://docs.example.org/policy.pdf"}
        if media_type.startswith("application/pdf-paper"):
            capture_tool = "researcher_capture_paper"
            capture_arguments = (
                {"arxiv_id": "2301.07041v2"}
                if media_type.endswith("arxiv")
                else {"doi": "10.1000/policy"}
            )
    app = create_app()
    if media_type == "application/pdf-semantic":
        from backend.research.semantic import SemanticRetriever
        from backend.tests.research.test_semantic_retrieval import assets

        app.state.retrieval = SemanticRetriever(assets())
    token = c.research.issue_grant(
        project_id=101, task_id=1001, agent_id="fixture", permissions=set(PERMISSIONS)
    )
    scope = c.research.authorize(token)
    app.state.live_grants.activate(scope.grant_id)
    async with host_business(
        api_url="http://127.0.0.1",
        token=token,
        withdraw=lambda: app.state.live_grants.withdraw(scope.grant_id),
        transport=httpx.ASGITransport(app=app),
    ) as peer:
        facade = await BusinessTools.connect(peer)

        async def call(name, **arguments):
            response = await facade.call({"tool": name, "arguments": arguments})
            assert response["success"], response
            return json.loads(response["contentItems"][0]["text"])

        captured = await call(
            capture_tool,
            operation_key="attachment",
            **capture_arguments,
        )
        assert captured == await call(
            capture_tool,
            operation_key="attachment",
            **capture_arguments,
        )
        snapshot = await call("researcher_source_read", source_id=captured["source_id"])
        assert "Tax rates are fractions." in snapshot["content"]
        if media_type.startswith("application/pdf"):
            assert snapshot["provenance"]["pages"][0]["page_number"] == 1
            assert snapshot["provenance"]["ocr_performed"] is False
        matches = await call(
            "researcher_source_search",
            source_id=captured["source_id"],
            needle="Tax rates",
        )
        if media_type == "application/pdf-semantic":
            ranked = await call(
                "researcher_source_query",
                source_id=captured["source_id"],
                query="¿Cómo se expresan las tasas de impuestos?",
                limit=1,
            )
            assert ranked["search_kind"] == "semantic_cosine"
            assert (
                ranked["full_coverage"] is True
                and ranked["execution"]["worker_closed"] is True
            )
            assert ranked["matches"][0]["page_numbers"] == [1]
            assert "Tax rates are fractions." in ranked["matches"][0]["excerpt"]
        assert matches["search_kind"] == "exact_text"
        assert "Tax rates are fractions." in matches["matches"][0]["excerpt"]
        source.unlink()
        assert captured == await call(
            capture_tool,
            operation_key="attachment",
            **capture_arguments,
        )
        finding = await call(
            "researcher_finding_record",
            operation_key="finding",
            topic="Policy",
            content="Rates are fractions.",
            evidence=[
                {
                    "source_id": captured["source_id"],
                    "quote": "Tax rates are fractions.",
                }
            ],
        )
        arguments = {
            "operation_key": "report",
            "title": "Policy",
            "content": "Rates are fractions.",
            "finding_ids": [finding["finding_id"]],
        }
        report = await call("researcher_report_write", **arguments)
        assert report == await call("researcher_report_write", **arguments)
        recovered = await call(
            "researcher_report_read", artifact_id=report["artifact_id"]
        )
        assert (
            recovered["status"] == "draft"
            and recovered["evidence"][0]["quote"] == "Tax rates are fractions."
        )
        denied = await facade.call(
            {
                "tool": "researcher_capture_reference",
                "arguments": {"operation_key": "cross-project", "reference_file_id": 8},
            }
        )
        assert not denied["success"]
        assert (
            c.conn.execute(
                "SELECT COUNT(*) FROM artifacts WHERE project_id=101"
            ).fetchone()[0]
            == 1
        )
        assert (
            c.conn.execute(
                "SELECT COUNT(*) FROM artifacts WHERE project_id=202"
            ).fetchone()[0]
            == 0
        )
        assert (
            c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            != "done"
        )
        c.research.revoke_grant(scope.grant_id)
        assert not (
            await facade.call({"tool": "researcher_reference_list", "arguments": {}})
        )["success"]
