"""The host owns business HTTP; schemas and handlers are transport independent."""

import asyncio
import json

import httpx
import pytest


@pytest.mark.parametrize("semantic", [False, True])
async def test_native_finding_registry_facade_preserves_filters_cursors_and_exact_evidence(
    coordination, semantic
):
    """Cross the actual admitted schema/HTTP boundary without a model-generated canned result."""
    import time

    from backend.api.main import create_app
    from backend.research.models import (
        PERMISSIONS,
        EvidenceReference,
        FindingDraft,
        SourceDraft,
    )
    from backend.runtime.business_mediation import BusinessTools
    from backend.runtime.host_business import host_business

    c = coordination
    c.now[0] = time.time()
    app = create_app()
    token = c.research.issue_grant(
        project_id=101, task_id=1001, agent_id="fixture", permissions=set(PERMISSIONS)
    )
    scope = c.research.authorize(token)
    app.state.live_grants.activate(scope.grant_id)
    source = c.research.capture_source(
        scope,
        "registry-source",
        SourceDraft(
            "web", "https://example.org/policy", "Policy", "Tax rates are fractions."
        ),
        intent={},
    )["source_id"]
    finding = c.research.record_finding(
        scope,
        "registry-finding",
        FindingDraft(
            "Tax convention",
            "The convention uses fractions.",
            (EvidenceReference(source, "Tax rates are fractions."),),
        ),
    )["finding_id"]
    if semantic:
        from backend.research.semantic import SemanticRetriever
        from backend.tests.research.test_semantic_retrieval import assets

        app.state.retrieval = SemanticRetriever(assets())
    async with host_business(
        api_url="http://127.0.0.1",
        token=token,
        withdraw=lambda: app.state.live_grants.withdraw(scope.grant_id),
        transport=httpx.ASGITransport(app=app),
    ) as peer:
        facade = await BusinessTools.connect(peer)

        async def call(name, **arguments):
            """Decode a successful real facade result while preserving the full failure on assertion."""
            response = await facade.call({"tool": name, "arguments": arguments})
            assert response["success"], response
            return json.loads(response["contentItems"][0]["text"])

        page = await call(
            "researcher_finding_list", query="fractions", status="provisional", limit=1
        )
        assert page["items"][0]["id"] == finding and page["next_after_id"] is None
        summary = await call("researcher_finding_summary", status="provisional")
        assert summary["total_count"] == 1 and summary["scientific_confidence"] is None
        other_task = await call("researcher_finding_list", for_task_id=2002)
        assert other_task["items"] == []
        read = await call("researcher_finding_read", finding_id=finding, max_chars=10)
        assert read["next_offset"] == 10 and read["evidence"][0]["quote_is_exact"]
        if semantic:
            ranked = await call(
                "researcher_finding_query",
                query="How are tax rates represented?",
                finding_ids=[finding],
                limit=3,
            )
            assert ranked["finding_ids"] == [finding] and ranked["full_coverage"]
            assert (
                ranked["execution"]["worker_closed"]
                and ranked["matches"][0]["finding_id"] == finding
            )
            assert "source_id" not in ranked
            continued = await call(
                "researcher_finding_query",
                query="How are tax rates represented?",
                finding_ids=[finding],
                limit=3,
                after_rank=1,
                expected_corpus_sha256=ranked["corpus_sha256"],
                expected_record_set_sha256=ranked["record_set_sha256"],
            )
            assert continued["corpus_sha256"] == ranked["corpus_sha256"]
            assert (
                continued["full_coverage"] and continued["execution"]["worker_closed"]
            )

    assert peer.closed and not app.state.live_grants.allows(scope.grant_id)


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
        "text/csv",
        "application/json",
        "application/xml",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/json-semantic",
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
    elif media_type in (
        "text/csv",
        "application/json",
        "application/xml",
        "application/json-semantic",
    ):
        source.write_bytes(
            {
                "text/csv": b"topic,result\npolicy,Tax rates are fractions.\n",
                "application/json": b'{"result":"Tax rates are fractions."}',
                "application/json-semantic": b'{"result":"Tax rates are fractions."}',
                "application/xml": b"<policy><result>Tax rates are fractions.</result></policy>",
            }[media_type]
        )
    elif media_type.endswith("wordprocessingml.document"):
        from backend.tests.research.structured_fixtures import docx_bytes

        source.write_bytes(
            docx_bytes("<w:p><w:r><w:t>Tax rates are fractions.</w:t></w:r></w:p>")
        )
    else:
        source.write_text("Tax rates are fractions.")
    c.conn.execute(
        "INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) VALUES(7,101,'policy.txt',?,?,?)",
        (
            str(source),
            source.stat().st_size,
            "application/pdf"
            if media_type.startswith("application/pdf")
            else media_type.removesuffix("-semantic"),
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
        from backend.tests.research.test_web_policy import response as robots_response

        responses = [robots_response(status=404), pdf_response(source.read_bytes())]

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
    if media_type.endswith("-semantic"):
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
        structured = media_type in (
            "text/csv",
            "application/json",
            "application/xml",
            "application/json-semantic",
        ) or media_type.endswith("wordprocessingml.document")
        if structured:
            assert "units" not in snapshot["provenance"]
            page = await call(
                "researcher_source_structure", source_id=captured["source_id"], limit=1
            )
            units = page["units"]
            while page["next_index"] is not None:
                page = await call(
                    "researcher_source_structure",
                    source_id=captured["source_id"],
                    after_index=page["next_index"],
                    limit=1,
                )
                units.extend(page["units"])
            assert len(units) == snapshot["provenance"]["unit_count"]
            assert any(
                "Tax rates are fractions."
                in snapshot["content"][u["start_offset"] : u["end_offset"]]
                for u in units
            )
        matches = await call(
            "researcher_source_search",
            source_id=captured["source_id"],
            needle="Tax rates",
        )
        if media_type.endswith("-semantic"):
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
            if structured:
                assert ranked["matches"][0]["unit_indices"]
            else:
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


@pytest.mark.parametrize("semantic", [False, True])
async def test_native_wiki_facade_keeps_revision_scope_and_exact_report_citations(
    coordination, tmp_path, monkeypatch, semantic
):
    """Use the actual shared tool schemas/API and optional real local encoder, never an LLM stub reply."""
    import time

    from backend.api.main import create_app
    from backend.knowledge.wiki import WikiStore
    from backend.research.models import PERMISSIONS
    from backend.runtime.business_mediation import BusinessTools
    from backend.runtime.host_business import host_business

    c = coordination
    c.now[0] = time.time()
    wiki = WikiStore(c.research.database)
    tricky_path = "guide/a?b#c"
    quote = "The controlled trial found no improvement in the treatment group compared with placebo."
    first = wiki.write(
        project_id=101,
        namespace="project",
        path=tricky_path,
        title="Trial result",
        content="Methods and background. " * 600 + "\n" + quote,
        expected_revision=0,
        actor="fixture",
        operation_key="wiki-fixture",
    )
    other = wiki.write(
        project_id=101,
        namespace="project",
        path="astronomy",
        title="Orbital mechanics",
        content="Galaxies and orbital mechanics. " * 400,
        expected_revision=0,
        actor="fixture",
        operation_key="astro-fixture",
    )
    app = create_app()
    if semantic:
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
            """Dispatch through native business mediation and decode its actual HTTP result."""
            result = await facade.call({"tool": name, "arguments": arguments})
            assert result["success"], result
            return json.loads(result["contentItems"][0]["text"])

        page = await call("researcher_wiki_read", path=tricky_path, max_chars=20000)
        assert (
            page["id"] == first["page_id"]
            and page["revision"] == 1
            and quote in page["content"]
        )
        listing = await call("researcher_wiki_list", limit=1)
        assert len(listing["pages"]) == 1 and listing["next_after_id"] is not None
        updated = await call(
            "researcher_wiki_write",
            operation_key="wiki-edit",
            path=tricky_path,
            title=page["title"],
            content=page["content"] + "\nScope corrected.",
            expected_revision=page["revision"],
            page_id=page["id"],
        )
        assert updated["revision"] == 2
        if semantic:
            captured = await call(
                "researcher_capture_wiki_collection",
                operation_key="corpus",
                members=[
                    {
                        "page_id": other["page_id"],
                        "revision": 1,
                        "namespace": "project",
                    },
                    {
                        "page_id": first["page_id"],
                        "revision": 1,
                        "namespace": "project",
                    },
                ],
            )
            ranked = await call(
                "researcher_source_query",
                source_id=captured["source_id"],
                query="¿Qué encontró el ensayo controlado sobre la mejora del tratamiento frente al placebo?",
                limit=3,
            )
            assert ranked["full_coverage"] and ranked["execution"]["worker_closed"]
            assert any(
                quote in match["excerpt"] and 1 in match["unit_indices"]
                for match in ranked["matches"]
            )
            structure = await call(
                "researcher_source_structure", source_id=captured["source_id"]
            )
            assert structure["units"][1]["wiki_revision"] == 1
        else:
            captured = await call(
                "researcher_capture_wiki",
                operation_key="wiki-source",
                page_id=page["id"],
                revision=1,
            )
        snapshot = await call(
            "researcher_source_read",
            source_id=captured["source_id"],
            offset=0,
            max_chars=20000,
        )
        assert (
            snapshot["kind"] == "wiki" and "Scope corrected." not in snapshot["content"]
        )
        finding = await call(
            "researcher_finding_record",
            operation_key="wiki-finding",
            topic="Controlled trial",
            content="No improvement was reported; not independent scientific validation.",
            evidence=[{"source_id": captured["source_id"], "quote": quote}],
        )
        report = await call(
            "researcher_report_write",
            operation_key="wiki-report",
            title="Trial notes",
            content="The saved revision reported no improvement; this is a provisional reading.",
            finding_ids=[finding["finding_id"]],
        )
        recovered = await call(
            "researcher_report_read", artifact_id=report["artifact_id"]
        )
        assert (
            recovered["status"] == "draft"
            and recovered["evidence"][0]["quote"] == quote
        )
        assert (
            c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            != "done"
        )
        denied = await facade.call(
            {
                "tool": "researcher_wiki_write",
                "arguments": {
                    "operation_key": "global-denied",
                    "path": "global",
                    "title": "Global",
                    "content": "Forbidden",
                    "expected_revision": 0,
                    "namespace": "global",
                },
            }
        )
        assert not denied["success"]
