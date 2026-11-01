"""Owner reads cite original records and remain scoped/paged, without tool grants."""

import pytest


@pytest.fixture
def report(client, db_conn, seeded_project):
    """Seed 21 linked citations, an uncited source and a second isolated project."""
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title) VALUES(10,1,'research','Invoice')"
    )
    db_conn.execute("INSERT INTO projects(id,name) VALUES(2,'Other')")
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title) VALUES(20,2,'research','Other')"
    )
    db_conn.execute(
        "INSERT INTO artifacts(id,project_id,task_id,type,file_path,content) VALUES(1,1,10,'report','reports/1.md','# Invoice\nOriginal text')"
    )
    db_conn.execute(
        "INSERT INTO research_reports VALUES(1,'Invoice','research','draft',?)",
        ("a" * 64,),
    )
    db_conn.execute(
        "INSERT INTO findings(id,project_id,task_id,topic,content,agent_id) VALUES(1,1,10,'Tax','Observed','fixture')"
    )
    db_conn.execute("INSERT INTO report_findings VALUES(1,1,1)")
    for index in range(21):
        db_conn.execute(
            "INSERT INTO research_sources VALUES(?,1,10,'attachment',?,'policy.txt',?,?,'{}',1793550000)",
            (100 + index, f"reference:{index}", f"Exact quote {index}", "b" * 64),
        )
        db_conn.execute(
            "INSERT INTO finding_sources VALUES(1,1,?,?)",
            (100 + index, f"Exact quote {index}"),
        )
    db_conn.execute(
        "INSERT INTO research_sources VALUES(999,1,10,'attachment','reference:uncited','NOT CITED','not cited',?,'{}',1793550000)",
        ("c" * 64,),
    )
    db_conn.execute(
        "INSERT INTO artifacts(id,project_id,task_id,type,file_path,content) VALUES(90,2,20,'report','reports/90.md','PRIVATE OTHER PROJECT')"
    )
    db_conn.commit()
    return client, db_conn


def test_owner_reads_exact_paged_citations_and_original_report_hash(report):
    """Verify 20+1 citation paging preserves quotes, hash, draft and saved body."""
    client, _ = report
    first = client.get("/api/artifacts/1/evidence?project_id=1")
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["total_evidence"] == 21 and data["next_offset"] == 20
    assert data["content_sha256"] == "a" * 64
    assert [x["source_id"] for x in data["evidence"]] == list(range(100, 120))
    assert data["evidence"][0]["quote"] == "Exact quote 0"
    assert data["evidence"][0]["locator"] == "reference:0"
    second = client.get("/api/artifacts/1/evidence?project_id=1&offset=20").json()
    assert second["next_offset"] is None and second["offset"] == 20
    assert [x["source_id"] for x in second["evidence"]] == [120]
    assert all(x["source_id"] != 999 for x in data["evidence"] + second["evidence"])
    original = client.get("/api/artifacts/1?project_id=1").json()
    assert (
        original["content"] == "# Invoice\nOriginal text"
        and original["research_status"] == "draft"
    )


def test_evidence_not_found_for_wrong_project_and_anonymous_is_unauthorized(report):
    """Reject foreign project reads, invalid offsets and unauthenticated owners."""
    client, _ = report
    assert client.get("/api/artifacts/1/evidence?project_id=2").status_code == 404
    assert client.get("/api/artifacts/90/evidence?project_id=1").status_code == 404
    assert (
        client.get("/api/artifacts/1/evidence?project_id=1&offset=-1").status_code
        == 422
    )
    client.delete("/api/session")
    assert client.get("/api/artifacts/1/evidence?project_id=1").status_code == 401


def test_evidence_reader_excludes_cross_project_associations_even_in_legacy_data(
    report,
):
    """Exclude legacy foreign-project associations even when IDs exist globally."""
    client, conn = report
    # Legacy SQLite can contain foreign-key-invalid associations. Every read join
    # must constrain project rather than trust globally unique IDs alone.
    conn.execute(
        "INSERT INTO findings(id,project_id,task_id,topic,content,agent_id) VALUES(2,2,20,'Secret','Secret','other')"
    )
    conn.execute(
        "INSERT INTO research_sources VALUES(888,2,20,'web','https://example.com','Secret','Secret',?,'{}',1793550000)",
        ("d" * 64,),
    )
    conn.execute("INSERT INTO finding_sources VALUES(2,2,888,'SECRET QUOTE')")
    conn.execute("INSERT INTO report_findings VALUES(2,1,2)")
    conn.commit()
    response = client.get("/api/artifacts/1/evidence?project_id=1")
    assert response.status_code == 200, response.text
    assert response.json()["total_evidence"] == 21
    assert "SECRET QUOTE" not in response.text


def test_artifact_catalog_pages_and_filters_without_returning_other_project(report):
    """Check stable catalog paging and scoped literal title/status filtering."""
    client, conn = report
    for identity in (2, 3, 4):
        conn.execute(
            "INSERT INTO artifacts(id,project_id,type,file_path) VALUES(?,1,'report',?)",
            (identity, f"reports/{identity}.md"),
        )
        conn.execute(
            "INSERT INTO research_reports VALUES(?,?,'research',?,?)",
            (
                identity,
                f"Invoice {identity}",
                "accepted" if identity == 4 else "draft",
                "a" * 64,
            ),
        )
    conn.commit()
    first = client.get("/api/artifacts?project_id=1&limit=2").json()
    second = client.get("/api/artifacts?project_id=1&limit=2&offset=2").json()
    assert [x["id"] for x in first] == [4, 3]
    assert [x["id"] for x in second] == [2, 1]
    draft = client.get(
        "/api/artifacts?project_id=1&q=invoice&research_status=draft"
    ).json()
    assert [x["id"] for x in draft] == [3, 2, 1]
    assert client.get("/api/artifacts?project_id=1&q=PRIVATE").json() == []


def test_task_read_for_report_link_requires_matching_project_when_supplied(report):
    """Resolve a report-linked task only in its explicitly requested project."""
    client, _ = report
    assert client.get("/api/tasks/10?project_id=1").status_code == 200
    assert client.get("/api/tasks/10?project_id=2").status_code == 404
