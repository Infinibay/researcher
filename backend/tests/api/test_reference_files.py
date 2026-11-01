"""Owner upload/preview/download contracts preserve project and source boundaries."""

import hashlib
from pathlib import Path

import pytest

from backend.tests.research.pdf_fixtures import pdf_bytes
from backend.tests.research.structured_fixtures import formats


@pytest.fixture
def uploads(client, seeded_project, monkeypatch, tmp_path):
    """Bind a private synthetic upload root without altering the user's files."""
    from backend.api import config

    root = tmp_path / "references"
    monkeypatch.setattr(config, "UPLOAD_DIR", str(root))
    return client, root


def upload(
    client,
    data=b"Tax rates are fractions.",
    name="policy.txt",
    mime="text/plain",
    project=1,
):
    """Submit a real multipart body through owner authentication and route validation."""
    return client.post(
        f"/api/files?project_id={project}",
        files={"file": (name, data, mime)},
        data={"description": "Policy fixture"},
    )


def test_pdf_upload_preview_and_download_do_not_create_a_captured_source(
    uploads, db_conn
):
    """Catch fake source receipts, changed binary downloads and loss of page provenance."""
    client, root = uploads
    data = pdf_bytes("Tax rates are fractions.", "Rate: 0.21.")
    response = upload(client, data, "política fiscal.pdf", "application/pdf")
    assert response.status_code == 201, response.text
    file_id = response.json()["id"]
    before = db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0]
    preview = client.get(f"/api/files/{file_id}/preview?project_id=1")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["persisted_source"] is False and "source_id" not in body
    assert (
        body["content"] == "[Page 1]\nTax rates are fractions.\n\n[Page 2]\nRate: 0.21."
    )
    assert body["provenance"]["byte_sha256"] == hashlib.sha256(data).hexdigest()
    assert body["provenance"]["page_count"] == 2
    assert (
        db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == before
    )
    download = client.get(f"/api/files/{file_id}/download?project_id=1")
    assert download.status_code == 200 and download.content == data
    assert "attachment" in download.headers["content-disposition"]
    assert client.delete(f"/api/files/{file_id}?project_id=1").status_code == 204
    assert client.get(f"/api/files/{file_id}?project_id=1").status_code == 404
    assert not list(root.rglob("*")) or not [p for p in root.rglob("*") if p.is_file()]


def test_foreign_project_metadata_preview_download_and_delete_are_rejected(
    uploads, db_conn
):
    """Catch deep links acting on a file outside the visibly chosen project."""
    client, _ = uploads
    db_conn.execute("INSERT INTO projects(id,name) VALUES(2,'Other')")
    db_conn.commit()
    file_id = upload(client).json()["id"]
    for suffix in ["", "/preview", "/download"]:
        assert (
            client.get(f"/api/files/{file_id}{suffix}?project_id=2").status_code == 404
        )
    assert client.delete(f"/api/files/{file_id}?project_id=2").status_code == 404
    assert (
        client.get(f"/api/files/{file_id}/download?project_id=1").content
        == b"Tax rates are fractions."
    )


@pytest.mark.parametrize("size", [1000001, 1100000])
def test_upload_size_is_rejected_without_a_reference_or_file(uploads, db_conn, size):
    """Enforce both the file-byte and pre-multipart total body limits."""
    client, root = uploads
    response = upload(client, b"x" * size)
    assert response.status_code == 413, response.text
    assert db_conn.execute("SELECT count(*) FROM reference_files").fetchone()[0] == 0
    assert not root.exists() or not [p for p in root.rglob("*") if p.is_file()]


def test_missing_project_is_rejected_before_creating_storage(uploads):
    """Reject orphan uploads instead of creating an unowned project directory."""
    client, root = uploads
    assert upload(client, project=999).status_code == 404
    assert not root.exists()


def test_upload_never_follows_a_project_upload_directory_symlink(
    uploads, tmp_path, db_conn
):
    """Catch a project directory redirect writing outside the configured root."""
    client, root = uploads
    (root / "1").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "1/uploads").symlink_to(outside, target_is_directory=True)
    response = upload(client)
    assert response.status_code in (400, 422), response.text
    assert not list(outside.iterdir())
    assert db_conn.execute("SELECT count(*) FROM reference_files").fetchone()[0] == 0


def test_download_and_delete_refuse_legacy_paths_outside_project_uploads(
    uploads, tmp_path, db_conn
):
    """A corrupt legacy metadata row cannot make owner actions read/remove another file."""
    client, _ = uploads
    outside = tmp_path / "private.txt"
    outside.write_text("DO NOT LEAK OR DELETE")
    cursor = db_conn.execute(
        "INSERT INTO reference_files(project_id,file_name,file_path,file_type) VALUES(1,'private.txt',?,'text/plain')",
        (str(outside),),
    )
    db_conn.commit()
    file_id = cursor.lastrowid
    assert client.get(f"/api/files/{file_id}/download?project_id=1").status_code == 422
    assert client.delete(f"/api/files/{file_id}?project_id=1").status_code == 422
    assert outside.read_text() == "DO NOT LEAK OR DELETE"
    assert (
        db_conn.execute(
            "SELECT count(*) FROM reference_files WHERE id=?", (file_id,)
        ).fetchone()[0]
        == 1
    )


def test_large_legacy_files_remain_downloadable_but_not_silently_truncated_for_preview(
    uploads, db_conn
):
    """Keep existing large downloads while enforcing the stricter extraction budget."""
    client, root = uploads
    directory = root / "1/uploads"
    directory.mkdir(parents=True)
    file = directory / "legacy.txt"
    data = b"x" * 1000001
    file.write_bytes(data)
    cursor = db_conn.execute(
        "INSERT INTO reference_files(project_id,file_name,file_path,file_type,file_size) VALUES(1,'legacy.txt',?,'text/plain',?)",
        (str(file), len(data)),
    )
    db_conn.commit()
    file_id = cursor.lastrowid
    response = client.get(f"/api/files/{file_id}/download?project_id=1")
    assert response.status_code == 200 and response.content == data
    assert client.get(f"/api/files/{file_id}/preview?project_id=1").status_code == 413


def test_catalog_filter_and_paging_are_project_scoped(uploads, db_conn):
    """Catch catalog truncation, unstable same-time ordering and cross-project search."""
    client, root = uploads
    db_conn.execute("INSERT INTO projects(id,name) VALUES(2,'Other')")
    for index in range(55):
        db_conn.execute(
            "INSERT INTO reference_files(project_id,file_name,file_path,file_type) VALUES(1,?,?,'text/plain')",
            (f"policy-{index}.txt", str(root / f"1/uploads/{index}")),
        )
    db_conn.execute(
        "INSERT INTO reference_files(project_id,file_name,file_path,file_type) VALUES(2,'FOREIGN.txt','/not-for-this-project','text/plain')"
    )
    db_conn.commit()
    first = client.get("/api/files?project_id=1&limit=50").json()
    second = client.get("/api/files?project_id=1&limit=50&offset=50").json()
    assert len(first) == 50 and len(second) == 5
    assert {row["id"] for row in first}.isdisjoint(row["id"] for row in second)
    assert client.get("/api/files?project_id=1&q=FOREIGN").json() == []
    assert len(client.get("/api/files?project_id=1&q=policy-54").json()) == 1


def test_missing_runtime_database_is_not_recreated_by_catalog(uploads, _isolated_db):
    """Preserve source-loss semantics for newly migrated owner file readers."""
    import sqlite3

    client, _ = uploads
    Path(_isolated_db).unlink()
    with pytest.raises(sqlite3.OperationalError):
        client.get("/api/files?project_id=1")
    assert not Path(_isolated_db).exists()


def test_deleting_a_reference_preserves_its_captured_source_and_report(
    uploads, db_conn, _isolated_db
):
    """Prove the deletion dialog's promise using real acquisition, finding and report persistence."""
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import EvidenceReference, FindingDraft, ReportDraft
    from backend.research.service import ResearchService
    from backend.research.sqlite_store import SQLiteResearchStore

    client, root = uploads
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title,status) VALUES(24,1,'research','Review','in_progress')"
    )
    db_conn.commit()
    store = SQLiteResearchStore(_isolated_db)
    token = store.issue_grant(
        project_id=1,
        task_id=24,
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
    scope = store.authorize(token)
    service = ResearchService(store, reference_reader=BoundedReferenceReader(root))
    file_id = upload(client).json()["id"]
    receipt = service.capture_reference(scope, "capture-before-delete", file_id)
    finding = store.record_finding(
        scope,
        "finding-before-delete",
        FindingDraft(
            "Tax policy",
            "Rates are fractions.",
            (EvidenceReference(receipt["source_id"], "Tax rates are fractions."),),
        ),
    )
    report = store.write_report(
        scope,
        "report-before-delete",
        ReportDraft(
            "Policy",
            "The source states that rates are fractions.",
            (finding["finding_id"],),
        ),
    )
    before = store.read_source(scope, receipt["source_id"])
    assert client.delete(f"/api/files/{file_id}?project_id=1").status_code == 204
    assert store.read_source(scope, receipt["source_id"]) == before
    assert service.capture_reference(scope, "capture-before-delete", file_id) == receipt
    assert (
        store.read_report(scope, report["artifact_id"])["content"]
        == "# Policy\n\nThe source states that rates are fractions."
    )


@pytest.mark.parametrize(
    "data", [b"%PDF-broken", pdf_bytes(None), pdf_bytes("Private", encrypted=True)]
)
def test_unreadable_preview_fails_without_registering_a_source(uploads, db_conn, data):
    """Scanned, malformed and encrypted PDF previews must not create false source receipts."""
    client, _ = uploads
    file_id = upload(client, data, "unreadable.pdf", "application/pdf").json()["id"]
    assert client.get(f"/api/files/{file_id}/preview?project_id=1").status_code == 422
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0
    assert client.get(f"/api/files/{file_id}/download?project_id=1").content == data


def test_missing_upload_is_not_reported_as_a_successful_download(uploads):
    """Metadata alone cannot stand in for a missing physical attachment."""
    client, root = uploads
    file_id = upload(client).json()["id"]
    next(p for p in root.rglob("*") if p.is_file()).unlink()
    assert client.get(f"/api/files/{file_id}/download?project_id=1").status_code == 404
    assert client.delete(f"/api/files/{file_id}?project_id=1").status_code == 204


@pytest.mark.parametrize("kind,mime,data", formats())
def test_structured_owner_preview_keeps_original_download_without_a_research_source(
    uploads, db_conn, kind, mime, data
):
    """Owner preview uses the same normalization yet cannot masquerade as captured research."""
    client, _ = uploads
    response = upload(client, data, "evidence." + kind, mime)
    assert response.status_code == 201, response.text
    file_id = response.json()["id"]
    response = client.get(f"/api/files/{file_id}/preview?project_id=1")
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["persisted_source"] is False and "source_id" not in preview
    assert preview["provenance"]["format"] == kind
    assert preview["provenance"]["byte_sha256"] == hashlib.sha256(data).hexdigest()
    assert (
        "units" not in preview["provenance"] and preview["provenance"]["unit_count"] > 0
    )
    assert "No improvement" in preview["content"]
    assert client.get(f"/api/files/{file_id}/download?project_id=1").content == data
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0
