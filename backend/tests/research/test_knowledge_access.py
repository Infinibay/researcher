"""Native cross-source discovery retains historical content, scope and honest coverage without granting scientific authority."""

import json

import pytest

from backend.tests.research.test_finding_registry import legacy_finding
from backend.tests.research.test_http import credentials, research_client

__all__ = ["research_client"]
ROOT = "/api/research-tools"
READS = {"sources.read", "findings.read", "wiki.read", "reports.read"}


@pytest.fixture
def knowledge_records(research_store, db_conn):
    """Mix native-readable history with foreign and explicit global records, including a report tail."""
    finding = legacy_finding(db_conn, content="SharedEvidence is an unverified old observation.")
    legacy_finding(db_conn, project=202, task=2002, content="SharedEvidence FOREIGN SECRET")
    db_conn.execute("INSERT INTO wiki_pages(id,project_id,path,title,content) VALUES(61,101,'own','SharedEvidence','Project note'),(62,NULL,'global','SharedEvidence','Global note'),(63,202,'foreign','SharedEvidence','FOREIGN SECRET')")
    db_conn.execute("INSERT INTO reference_files(id,project_id,file_name,file_path,description) VALUES(71,101,'SharedEvidence.txt','/not-opened','Attachment metadata'),(72,202,'SharedEvidence-secret.txt','/foreign','FOREIGN SECRET')")
    body = "SharedEvidence " + "áβ" * 900 + " Unknown measurement conditions."
    db_conn.execute("INSERT INTO artifacts(id,project_id,task_id,type,file_path,description,content) VALUES(81,101,1001,'report','/not-opened/report.md','Old report',?),(82,202,2002,'report','/foreign','SharedEvidence','FOREIGN SECRET'),(83,101,1001,'report','/not-opened/missing.md','Missing retained bytes',NULL)", (body,))
    db_conn.commit()
    return {"finding": finding, "report": 81, "body": body}


def test_knowledge_query_preserves_source_coverage_and_explicit_global_scope(research_client, research_store, knowledge_records, db_conn):
    """All four sources retain own identities; missing indexes remain failures, never empty successful searches."""
    headers = credentials(research_store, permissions=READS)
    response = research_client.post(ROOT + "/knowledge-query", headers=headers, json={"query":"SharedEvidence"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert {row["source_type"] for row in data["results"]} == {"findings", "wiki", "reference_files", "reports"}
    assert all(c["status"] == "searched" for c in data["coverage"].values())
    assert data["partial"] is False and data["scientific_confidence"] is None
    assert "FOREIGN SECRET" not in json.dumps(data)
    assert [row["id"] for row in data["results"] if row["source_type"] == "wiki"] == [61]
    global_page = research_client.post(ROOT + "/knowledge-query", headers=headers, json={"query":"SharedEvidence", "sources":["wiki"], "namespace":"global"}).json()
    assert [row["id"] for row in global_page["results"]] == [62]
    db_conn.execute("DROP TABLE reference_files_fts")
    db_conn.commit()
    partial = research_client.post(ROOT + "/knowledge-query", headers=headers, json={"query":"SharedEvidence", "sources":["findings", "reference_files"]}).json()
    assert partial["partial"] is True and partial["coverage"]["reference_files"]["status"] == "failed"
    assert partial["coverage"]["reference_files"]["total_matching"] is None
    assert [row["id"] for row in partial["results"]] == [knowledge_records["finding"]]
    later = legacy_finding(db_conn, content="SharedEvidence later observation")
    first = research_client.post(ROOT + "/knowledge-query", headers=headers, json={"query":"SharedEvidence", "sources":["findings"], "limit":1}).json()
    assert first["results"][0]["scientific_confidence"] is None
    cursor = first["coverage"]["findings"]["next_after_id"]
    following = research_client.post(ROOT + "/knowledge-query", headers=headers, json={"query":"SharedEvidence", "sources":["findings"], "limit":1, "cursors":{"findings":cursor}}).json()
    assert [row["id"] for row in following["results"]] == [later]
    assert following["coverage"]["findings"]["next_after_id"] is None


def test_knowledge_query_checks_every_requested_permission_and_live_context(research_client, research_store, knowledge_records, db_conn):
    """A unified reader cannot use one capability to expose another source or revive a stale grant."""
    path = ROOT + "/knowledge-query"
    assert research_client.post(path, json={"query":"SharedEvidence"}).status_code == 401
    headers = credentials(research_store, permissions={"findings.read"})
    assert research_client.post(path, headers=headers, json={"query":"SharedEvidence"}).status_code == 403
    assert research_client.post(path, headers=headers, json={"query":"SharedEvidence", "sources":["findings"]}).status_code == 200
    for change in ({"project_id":202}, {"sources":["findings", "findings"]}, {"cursors":{"wiki":1}}, {"limit":0}):
        response = research_client.post(path, headers=headers, json={"query":"SharedEvidence", "sources":["findings"], **change})
        assert response.status_code == 422, response.text
    scope = research_store.authorize(headers["Authorization"].split()[1])
    db_conn.execute("UPDATE task_contexts SET version=version+1 WHERE task_id=1001")
    db_conn.commit()
    from backend.research.models import ResearchForbidden

    with pytest.raises(ResearchForbidden):
        research_store.query_knowledge(scope, "SharedEvidence", sources=["findings"])


def test_historical_report_is_readable_without_native_status_or_automatic_file_access(research_client, research_store, knowledge_records):
    """Recover complete saved legacy bytes while marking their origin and refusing a guessed filesystem fallback."""
    headers = credentials(research_store, permissions={"reports.read"})
    path = ROOT + "/reports/81"
    first = research_client.get(path, headers=headers, params={"max_chars":1000})
    assert first.status_code == 200, first.text
    data = first.json()
    tail = research_client.get(path, headers=headers, params={"offset":data["next_offset"]}).json()
    assert data["content"] + tail["content"] == knowledge_records["body"]
    assert data["record_origin"] == data["status"] == "legacy_unverified"
    assert data["hash_origin"] == "observed_legacy_content"
    assert data["evidence"] == [] and data["finding_ids"] == []
    assert research_client.get(ROOT + "/reports/82", headers=headers).status_code == 404
    missing = research_client.get(ROOT + "/reports/83", headers=headers)
    assert missing.status_code == 404 and "retained" in missing.text


async def test_real_mcp_search_discovers_and_reads_historical_report(research_client, research_store, knowledge_records):
    """Use the actual MCP/HTTP/SQLite route and declared role catalog to recover discovered content."""
    import anyio
    import httpx
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    from backend.research.async_http_client import AsyncResearcherHTTPClient
    from backend.research.stdio_server import BusinessGateway, create_server
    from backend.runtime.business_definitions import definitions
    from backend.runtime.business_mediation import CODE_REVIEW_NAMES, DEVELOPMENT_NAMES, INVESTIGATION_NAMES, RESEARCH_NAMES, REVIEW_NAMES

    name = "researcher_knowledge_search"
    for names in (CODE_REVIEW_NAMES, DEVELOPMENT_NAMES, INVESTIGATION_NAMES, RESEARCH_NAMES, REVIEW_NAMES):
        assert name in names
    schema = next(tool for tool in definitions(None) if tool.name == name)
    assert schema.annotations["readOnlyHint"] is True
    assert not {"project_id", "task_id", "agent_id", "token"} & schema.wire_schema()["properties"].keys()
    headers = credentials(research_store, permissions=READS)
    async with AsyncResearcherHTTPClient("http://127.0.0.1", headers["Authorization"].split()[1], transport=httpx.ASGITransport(app=research_client.app)) as port:
        server = create_server(BusinessGateway(port))
        async with create_client_server_memory_streams() as (client_streams, server_streams), anyio.create_task_group() as group:
            group.start_soon(server.run, *server_streams, server.create_initialization_options())
            async with ClientSession(*client_streams) as client:
                await client.initialize()
                query = await client.call_tool(name, {"query":"SharedEvidence", "sources":["reports"]})
                assert not query.isError, query
                row = query.structuredContent["results"][0]
                report = await client.call_tool("researcher_report_read", {"artifact_id":row["id"]})
                assert not report.isError, report
                assert report.structuredContent["content"] == knowledge_records["body"]
                assert report.structuredContent["record_origin"] == "legacy_unverified"
            group.cancel_scope.cancel()
