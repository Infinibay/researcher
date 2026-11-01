"""PDF sources retain page provenance and reject incomplete or oversized extraction."""

from dataclasses import replace

import pytest

from backend.research.acquisition import BoundedReferenceReader
from backend.research.models import (
    EvidenceReference,
    FindingDraft,
    SourceTooLarge,
    SourceUnavailable,
)
from backend.research.service import ResearchService
from backend.tests.research.pdf_fixtures import pdf_bytes
from backend.tests.research.test_acquisition import reference


def test_pdf_capture_keeps_original_byte_identity_pages_and_exact_citations(
    research_store,
    research_scope,
    db_conn,
    tmp_path,
):
    """Catch binary rejection, lost page boundaries and citations detached from saved text."""
    data = pdf_bytes("Tax rates are fractions.", "Rate: 0.21.")
    root, file, record = reference(research_store, db_conn, tmp_path, content=data)
    db_conn.execute(
        "UPDATE reference_files SET file_type='application/pdf',file_name='policy.pdf' WHERE id=?",
        (record.id,),
    )
    db_conn.commit()
    service = ResearchService(
        research_store, reference_reader=BoundedReferenceReader(root)
    )
    receipt = service.capture_reference(research_scope, "pdf-policy", record.id)
    source = research_store.read_source(research_scope, receipt["source_id"])
    assert (
        source["content"]
        == "[Page 1]\nTax rates are fractions.\n\n[Page 2]\nRate: 0.21."
    )
    import hashlib

    assert source["provenance"]["byte_sha256"] == hashlib.sha256(data).hexdigest()
    assert source["provenance"]["extraction"] == "pypdf-text-v1"
    assert source["provenance"]["page_count"] == 2
    assert source["provenance"]["pages"][1]["page_number"] == 2
    start = source["provenance"]["pages"][1]["text_start_offset"]
    end = source["provenance"]["pages"][1]["end_offset"]
    assert source["content"][start:end] == "Rate: 0.21."
    finding = research_store.record_finding(
        research_scope,
        "pdf-finding",
        FindingDraft(
            "Tax", "Observed rate", (EvidenceReference(source["id"], "Rate: 0.21."),)
        ),
    )
    assert finding["status"] == "provisional"
    file.unlink()
    assert service.capture_reference(research_scope, "pdf-policy", record.id) == receipt


def test_mixed_pdf_marks_pages_without_text_instead_of_claiming_ocr(
    research_store,
    db_conn,
    tmp_path,
):
    """Catch silent omission of pages without extractable text in a mixed document."""
    root, _, record = reference(
        research_store,
        db_conn,
        tmp_path,
        content=pdf_bytes("Tax rates are fractions.", None),
    )
    source = BoundedReferenceReader(root).read(
        replace(record, mime_type="application/pdf")
    )
    assert source.provenance["pages_without_text"] == [2]
    assert source.provenance["ocr_performed"] is False
    assert source.provenance["pages"][1]["has_text"] is False
    assert "[Page 2]" in source.content


@pytest.mark.parametrize(
    "data,reason",
    [
        (pdf_bytes(None), "extractable text"),
        (pdf_bytes("Private", encrypted=True), "encrypted"),
        (b"%PDF-not-a-real-document", "malformed"),
    ],
)
def test_unreadable_pdf_is_a_failed_capture_not_an_empty_or_partial_source(
    research_store,
    research_scope,
    db_conn,
    tmp_path,
    data,
    reason,
):
    """Catch false successful capture of scanned, encrypted or malformed PDF input."""
    root, _, record = reference(research_store, db_conn, tmp_path, content=data)
    db_conn.execute(
        "UPDATE reference_files SET file_type='application/pdf' WHERE id=?",
        (record.id,),
    )
    db_conn.commit()
    service = ResearchService(
        research_store, reference_reader=BoundedReferenceReader(root)
    )
    with pytest.raises(SourceUnavailable, match=reason):
        service.capture_reference(research_scope, "bad-pdf", record.id)
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


def test_pdf_extraction_refuses_text_page_and_decoding_limits_without_truncation():
    """Catch silent truncation or unbounded compressed-stream expansion before persistence."""
    from backend.research.pdf_text import extract_pdf

    with pytest.raises(SourceTooLarge):
        extract_pdf(pdf_bytes("Tax rates are fractions."), max_text_bytes=8)
    with pytest.raises(SourceTooLarge):
        extract_pdf(pdf_bytes("Page one", "Page two"), max_pages=1)
    with pytest.raises(SourceTooLarge):
        extract_pdf(pdf_bytes("A" * 2000, compress=True), max_stream_bytes=256)


def test_pdf_configuration_does_not_leak_between_captures():
    """Catch global parser-configuration changes that contaminate another request."""
    from pypdf import get_configuration

    from backend.research.pdf_text import extract_pdf

    before = get_configuration()
    with pytest.raises(SourceTooLarge):
        extract_pdf(pdf_bytes("A" * 2000, compress=True), max_stream_bytes=256)
    assert get_configuration() == before
    content, _ = extract_pdf(pdf_bytes("Valid after failure"))
    assert "Valid after failure" in content


def test_pdf_capture_revalidates_scope_after_extraction(
    research_store,
    research_scope,
    db_conn,
    tmp_path,
):
    """Catch a stale grant committing PDF text after Stop/correction revoked authority."""
    from backend.research.models import ResearchForbidden

    root, _, record = reference(
        research_store, db_conn, tmp_path, content=pdf_bytes("Tax rates are fractions.")
    )
    db_conn.execute(
        "UPDATE reference_files SET file_type='application/pdf' WHERE id=?",
        (record.id,),
    )
    db_conn.commit()

    class RevokingPDFReader(BoundedReferenceReader):
        """Withdraw the real grant at the boundary between extraction and commit."""

        def read(self, record):
            """Finish real extraction before simulating concurrent Stop/correction."""
            result = super().read(record)
            research_store.revoke_grant(research_scope.grant_id)
            return result

    service = ResearchService(research_store, reference_reader=RevokingPDFReader(root))
    with pytest.raises(ResearchForbidden):
        service.capture_reference(research_scope, "revoked-pdf", record.id)
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


def test_valid_first_page_does_not_hide_a_later_pdf_extraction_limit():
    """Catch a reader returning the first page after a later compressed page exceeds limits."""
    from backend.research.pdf_text import extract_pdf

    with pytest.raises(SourceTooLarge):
        extract_pdf(
            pdf_bytes("Valid first page", "A" * 2000, compress=True),
            max_stream_bytes=256,
        )
