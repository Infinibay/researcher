import pytest


def reference(
    research_store,
    db_conn,
    tmp_path,
    *,
    project_id=101,
    content=b"Tax rates are fractions.",
):
    from backend.research.models import ReferenceRecord

    root = tmp_path / "uploads"
    directory = root / str(project_id) / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    file = directory / "policy.md"
    file.write_bytes(content)
    row = db_conn.execute(
        "INSERT INTO reference_files(project_id,file_name,file_path,file_size,file_type) VALUES(?,?,?,?,?)",
        (project_id, "policy.md", str(file), len(content), "text/markdown"),
    )
    db_conn.commit()
    return (
        root,
        file,
        ReferenceRecord(
            row.lastrowid, project_id, "policy.md", str(file), "text/markdown"
        ),
    )


def test_reference_retry_reads_the_committed_snapshot_even_if_original_file_disappears(
    research_store, research_scope, db_conn, tmp_path
):
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.service import ResearchService

    root, file, ref = reference(research_store, db_conn, tmp_path)
    service = ResearchService(
        research_store, reference_reader=BoundedReferenceReader(root)
    )
    first = service.capture_reference(research_scope, "read-policy", ref.id)
    file.unlink()
    assert service.capture_reference(research_scope, "read-policy", ref.id) == first
    source = research_store.read_source(research_scope, first["source_id"])
    assert source["content"] == "Tax rates are fractions."
    assert source["locator"] == f"reference:{ref.id}"
    assert source["provenance"]["reference_file_id"] == ref.id
    assert len(source["provenance"]["byte_sha256"]) == 64


def test_scope_revoked_during_file_read_cannot_commit_a_source(
    research_store, research_scope, db_conn, tmp_path
):
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import ResearchForbidden
    from backend.research.service import ResearchService

    root, _, ref = reference(research_store, db_conn, tmp_path)

    class RevokingReader(BoundedReferenceReader):
        def read(self, record):
            result = super().read(record)
            research_store.revoke_grant(research_scope.grant_id)
            return result

    service = ResearchService(research_store, reference_reader=RevokingReader(root))
    with pytest.raises(ResearchForbidden):
        service.capture_reference(research_scope, "late-source", ref.id)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0


def test_cross_project_reference_is_rejected_before_acquisition(
    research_store, research_scope, db_conn, tmp_path
):
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import ResearchNotFound
    from backend.research.service import ResearchService

    root, _, ref = reference(
        research_store, db_conn, tmp_path, project_id=202, content=b"BETA PRIVATE"
    )
    service = ResearchService(
        research_store, reference_reader=BoundedReferenceReader(root)
    )
    with pytest.raises(ResearchNotFound):
        service.capture_reference(research_scope, "foreign-source", ref.id)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0


@pytest.mark.parametrize(
    "escape", ["symlink-file", "symlink-directory", "outside", "parent-traversal"]
)
def test_reference_reader_cannot_follow_paths_outside_its_project_upload_root(
    research_store, db_conn, tmp_path, escape
):
    from dataclasses import replace

    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import SourceUnavailable

    root, file, ref = reference(research_store, db_conn, tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("Not an attachment")
    if escape == "symlink-file":
        file.unlink()
        file.symlink_to(secret)
    elif escape == "symlink-directory":
        file.unlink()
        file.parent.rmdir()
        file.parent.symlink_to(tmp_path, target_is_directory=True)
    elif escape == "outside":
        ref = replace(ref, path=str(secret))
    else:
        ref = replace(ref, path=str(file.parent / ".." / ".." / ".." / "secret.txt"))
    with pytest.raises(SourceUnavailable):
        BoundedReferenceReader(root).read(ref)


def test_reader_rejects_oversize_data_instead_of_presenting_a_truncated_source(
    research_store, db_conn, tmp_path
):
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import SourceTooLarge

    root, _, ref = reference(research_store, db_conn, tmp_path, content=b"x" * 129)
    with pytest.raises(SourceTooLarge):
        BoundedReferenceReader(root, max_bytes=128).read(ref)


def test_non_text_attachment_is_reported_as_unsupported_not_misdecoded(
    research_store, db_conn, tmp_path
):
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import SourceUnavailable

    root, _, ref = reference(
        research_store, db_conn, tmp_path, content=b"%PDF-not-a-text-source"
    )
    from dataclasses import replace

    with pytest.raises(SourceUnavailable):
        BoundedReferenceReader(root).read(replace(ref, mime_type="application/pdf"))
