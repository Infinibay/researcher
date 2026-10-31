"""Real HTTP → authorization → acquisition → SQLite → report retrieval."""

import pytest
from starlette.testclient import TestClient

from backend.tests.research.test_acquisition import reference


@pytest.fixture
def research_client(research_store, research_scope, monkeypatch, tmp_path):
    from backend.api import config
    from backend.api.main import create_app

    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return TestClient(create_app())


def credentials(store, project_id=101, task_id=1001, permissions=None):
    token = store.issue_grant(
        project_id=project_id,
        task_id=task_id,
        agent_id="native-researcher",
        permissions=permissions
        or {
            "sources.read",
            "sources.capture",
            "findings.read",
            "findings.write",
            "reports.read",
            "reports.write",
        },
    )
    return {"Authorization": "Bearer " + token}


def test_tool_routes_require_a_valid_host_issued_scope(research_client, research_store):
    assert research_client.get("/api/research-tools/references").status_code == 401
    assert (
        research_client.get(
            "/api/research-tools/references",
            headers={"Authorization": "Bearer invalid"},
        ).status_code
        == 401
    )
    assert (
        research_client.get(
            "/api/research-tools/references", headers=credentials(research_store)
        ).status_code
        == 200
    )


def test_attachment_to_finding_to_report_is_visible_through_the_product_artifact_api(
    research_client, research_store, db_conn, tmp_path
):
    _, _, ref = reference(research_store, db_conn, tmp_path)
    headers = credentials(research_store)
    response = research_client.post(
        "/api/research-tools/sources/reference",
        headers=headers,
        json={"operation_key": "attachment", "reference_file_id": ref.id},
    )
    assert response.status_code == 200, response.text
    source = response.json()["source_id"]
    response = research_client.post(
        "/api/research-tools/findings",
        headers=headers,
        json={
            "operation_key": "finding",
            "topic": "Policy",
            "content": "Rates are fractions.",
            "evidence": [{"source_id": source, "quote": "Tax rates are fractions."}],
        },
    )
    assert response.status_code == 200, response.text
    finding = response.json()["finding_id"]
    payload = {
        "operation_key": "report",
        "title": "Policy report",
        "content": "Rate notation is documented in the attachment.",
        "finding_ids": [finding],
    }
    response = research_client.post(
        "/api/research-tools/reports", headers=headers, json=payload
    )
    assert response.status_code == 200, response.text
    report = response.json()["artifact_id"]
    assert (
        research_client.post(
            "/api/research-tools/reports", headers=headers, json=payload
        ).json()
        == response.json()
    )
    listing = research_client.get("/api/artifacts?project_id=101&type=report").json()
    assert [row["id"] for row in listing] == [report]
    detail = research_client.get(f"/api/artifacts/{report}?project_id=101").json()
    assert (
        detail["content"]
        == "# Policy report\n\nRate notation is documented in the attachment."
    )
    scoped = research_client.get(
        f"/api/research-tools/reports/{report}", headers=headers
    ).json()
    assert scoped["evidence"][0]["quote"] == "Tax rates are fractions."
    assert scoped["status"] == "draft"


def test_tool_payload_cannot_override_project_task_or_actor(
    research_client, research_store, db_conn
):
    response = research_client.post(
        "/api/research-tools/reports",
        headers=credentials(research_store),
        json={
            "operation_key": "report",
            "title": "Unwanted",
            "content": "Claim",
            "finding_ids": [1],
            "project_id": 202,
            "task_id": 2002,
            "agent_id": "other",
        },
    )
    assert response.status_code == 422
    assert db_conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_readers_cannot_write_and_grant_revocation_has_an_http_error(
    research_client, research_store, db_conn, tmp_path
):
    _, _, ref = reference(research_store, db_conn, tmp_path)
    headers = credentials(research_store, permissions={"sources.read"})
    response = research_client.post(
        "/api/research-tools/sources/reference",
        headers=headers,
        json={"operation_key": "capture", "reference_file_id": ref.id},
    )
    assert response.status_code == 403
    token = headers["Authorization"].removeprefix("Bearer ")
    research_store.revoke_grant(research_store.authorize(token).grant_id)
    assert (
        research_client.get(
            "/api/research-tools/references", headers=headers
        ).status_code
        == 401
    )


def test_source_windows_and_search_preserve_counterevidence_at_the_end(
    research_client, research_store, db_conn, tmp_path
):
    _, _, ref = reference(
        research_store,
        db_conn,
        tmp_path,
        content=(
            "Intro. " * 2500 + "Counterevidence: rounding is conditional."
        ).encode(),
    )
    headers = credentials(research_store)
    source = research_client.post(
        "/api/research-tools/sources/reference",
        headers=headers,
        json={"operation_key": "capture", "reference_file_id": ref.id},
    ).json()["source_id"]
    first = research_client.get(
        f"/api/research-tools/sources/{source}?max_chars=100", headers=headers
    ).json()
    assert len(first["content"]) == 100
    assert first["next_offset"] == 100 and first["total_chars"] > 100
    result = research_client.get(
        f"/api/research-tools/sources/{source}/search?needle=Counterevidence",
        headers=headers,
    ).json()
    assert (
        "Counterevidence: rounding is conditional." in result["matches"][0]["excerpt"]
    )
    assert result["sha256"] == first["sha256"]


def test_tool_scope_in_query_is_rejected_instead_of_silently_ignored(
    research_client, research_store
):
    response = research_client.get(
        "/api/research-tools/references?project_id=202",
        headers=credentials(research_store),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("streamed", [False, True])
def test_tool_ingress_rejects_large_json_before_parsing_or_persistence(
    research_client, research_store, db_conn, streamed
):
    headers = {**credentials(research_store), "Content-Type": "application/json"}
    data = (
        (part for part in [b"x" * 600000, b"x" * 600000])
        if streamed
        else b"x" * 1200000
    )
    response = research_client.post(
        "/api/research-tools/reports", headers=headers, content=data
    )
    assert response.status_code == 413
    assert db_conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_large_report_evidence_is_paginated_without_silently_dropping_citations(
    research_client, research_store, research_scope
):
    from backend.research.models import (
        EvidenceReference,
        FindingDraft,
        ReportDraft,
        SourceDraft,
    )

    source = research_store.capture_source(
        research_scope,
        "many-source",
        SourceDraft(
            kind="web",
            locator="https://docs.example.org/policy",
            title="Policy",
            content=" ".join(f"quote-{n}" for n in range(11)),
        ),
        intent={"url": "https://docs.example.org/policy"},
    )
    ids = []
    for n in range(2):
        finding = research_store.record_finding(
            research_scope,
            f"finding-{n}",
            FindingDraft(
                topic=f"Finding {n}",
                content="Supported claim",
                evidence=tuple(
                    EvidenceReference(source["source_id"], f"quote-{k}")
                    for k in range(11)
                ),
            ),
        )
        ids.append(finding["finding_id"])
    report = research_store.write_report(
        research_scope,
        "long-basis",
        ReportDraft(title="Report", content="Claim", finding_ids=tuple(ids)),
    )
    headers = credentials(research_store)
    first = research_client.get(
        f"/api/research-tools/reports/{report['artifact_id']}", headers=headers
    ).json()
    assert len(first["evidence"]) == 20
    assert first["total_evidence"] == 22 and first["next_evidence_offset"] == 20
    rest = research_client.get(
        f"/api/research-tools/reports/{report['artifact_id']}?evidence_offset=20",
        headers=headers,
    ).json()
    assert len(rest["evidence"]) == 2 and rest["next_evidence_offset"] is None


def test_product_artifact_detail_requires_its_current_project(
    research_client, research_store, research_scope
):
    from backend.research.models import ReportDraft
    from backend.tests.research.test_persistence import record

    finding = record(research_store, research_scope)
    report = research_store.write_report(
        research_scope,
        "scoped-report",
        ReportDraft(
            title="Alpha report",
            content="Provisional claim",
            finding_ids=(finding["finding_id"],),
        ),
    )
    artifact = report["artifact_id"]
    assert (
        research_client.get(f"/api/artifacts/{artifact}?project_id=202").status_code
        == 404
    )
    assert research_client.get(f"/api/artifacts/{artifact}").status_code == 422
    detail = research_client.get(f"/api/artifacts/{artifact}?project_id=101").json()
    assert detail["title"] == "Alpha report"
    assert detail["research_status"] == "draft"
