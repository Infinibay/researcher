"""Structured attachment text retains source identity, exact locators and complete evidence."""

import hashlib
from dataclasses import replace

import pytest

from backend.research.acquisition import BoundedReferenceReader
from backend.research.service import ResearchService
from backend.tests.research.structured_fixtures import DOCX, docx_bytes, formats
from backend.tests.research.test_acquisition import reference


@pytest.mark.parametrize("kind,mime,data", formats())
def test_structured_capture_keeps_units_original_hash_and_retry_snapshot(
    research_store, research_scope, db_conn, tmp_path, kind, mime, data
):
    """Catch unsupported Word, raw markup without structure, numeric loss and silent retry reparse."""
    root, file, record = reference(research_store, db_conn, tmp_path, content=data)
    db_conn.execute(
        "UPDATE reference_files SET file_type=? WHERE id=?", (mime, record.id)
    )
    db_conn.commit()
    service = ResearchService(
        research_store, reference_reader=BoundedReferenceReader(root)
    )
    captured = service.capture_reference(research_scope, "structured", record.id)
    saved = research_store.read_source(research_scope, captured["source_id"])
    assert saved["provenance"]["format"] == kind
    assert saved["provenance"]["byte_sha256"] == hashlib.sha256(data).hexdigest()
    units = saved["provenance"]["units"]
    assert units
    assert any(
        "No improvement" in saved["content"][u["start_offset"] : u["end_offset"]]
        for u in units
    )
    assert all(
        u["index"] == index
        and 0 <= u["start_offset"] < u["end_offset"] <= len(saved["content"])
        for index, u in enumerate(units)
    )
    if kind == "json":
        assert "0.10000000000000001" in saved["content"]
    if kind == "docx":
        assert any("/tc[" in u["locator"] for u in units)
    file.unlink()
    assert (
        service.capture_reference(research_scope, "structured", record.id) == captured
    )


@pytest.mark.parametrize(
    "mime,data",
    [
        ("application/json", b'{"x":1,"x":2}'),
        ("application/json", b'{"x":NaN}'),
        ("application/json", b"{"),
        (
            "application/xml",
            b'<!DOCTYPE root [<!ENTITY x "replaced">]><root>&x;</root>',
        ),
        (
            "application/xml",
            '<!DOCTYPE root SYSTEM "https://example.org/external"><root/>'.encode(
                "utf-16"
            ),
        ),
        ("application/xml", b"<root>"),
        (DOCX, b"not a ZIP"),
        (DOCX, docx_bytes(extra={"../escape": "ignored"})),
        ("text/csv", b'name,result\ncontrol,"unclosed'),
    ],
)
def test_invalid_structured_documents_do_not_commit_partial_sources(
    research_store, research_scope, db_conn, tmp_path, mime, data
):
    """Malformed/ambiguous/active document syntax cannot become an apparently successful source."""
    from backend.research.models import SourceUnavailable

    root, _, record = reference(research_store, db_conn, tmp_path, content=data)
    db_conn.execute(
        "UPDATE reference_files SET file_type=? WHERE id=?", (mime, record.id)
    )
    db_conn.commit()
    with pytest.raises(SourceUnavailable):
        ResearchService(
            research_store, reference_reader=BoundedReferenceReader(root)
        ).capture_reference(research_scope, "bad", record.id)
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


def test_csv_preserves_duplicate_header_context_extra_and_missing_cells(
    research_store, db_conn, tmp_path
):
    """Do not zip away extra values or equate an absent cell with an empty cell."""
    data = b"name,name,other\nAlice,Bob\nCarol,,D,EXTRA\n"
    root, _, record = reference(research_store, db_conn, tmp_path, content=data)
    result = BoundedReferenceReader(root).read(replace(record, mime_type="text/csv"))
    assert result.provenance["header_assumed"] is True
    assert "EXTRA" in result.content and "[MISSING]" in result.content
    assert len(result.provenance["units"]) == 3


def test_structured_depth_and_expansion_are_limits_not_truncation(
    research_store, db_conn, tmp_path
):
    """A too-deep tree or compressed XML bomb must fail without a saved prefix."""
    from backend.research.models import SourceTooLarge

    for mime, data in [
        ("application/json", b"[" * 80 + b"0" + b"]" * 80),
        ("application/xml", b"<x>" * 80 + b"data" + b"</x>" * 80),
        (DOCX, docx_bytes("<w:p><w:r><w:t>" + "X" * 5000000 + "</w:t></w:r></w:p>")),
    ]:
        root, _, record = reference(research_store, db_conn, tmp_path, content=data)
        with pytest.raises(SourceTooLarge):
            BoundedReferenceReader(root).read(replace(record, mime_type=mime))


def test_docx_keeps_late_table_counterevidence_and_labels_extraction_scope():
    """Evidence after the first read window remains in a table unit, without including deleted text."""
    from backend.research.parser_process import DocumentParser

    prefix = "".join(
        "<w:p><w:r><w:t>" + "Background context. " * 10 + "</w:t></w:r></w:p>"
        for _ in range(80)
    )
    table = "<w:tbl><w:tr><w:tc><w:p><w:del><w:r><w:t>Obsolete positive result.</w:t></w:r></w:del><w:r><w:t>No improvement in the control group.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    content, provenance = DocumentParser(format="docx").read(docx_bytes(prefix + table))
    assert content.index("No improvement") > 12000
    assert "Obsolete positive" not in content
    unit = provenance["units"][-1]
    assert "/tc[1]/p[1]" in unit["locator"]
    assert (
        content[unit["start_offset"] : unit["end_offset"]]
        == "No improvement in the control group."
    )
    assert "headers/footers" in provenance["extraction_note"]
    assert provenance["execution"]["worker_closed"] is True


@pytest.mark.parametrize("kind,mime,data", formats())
def test_format_selection_keeps_host_withdrawal_and_cpu_authority(kind, mime, data):
    """Changing the fixed format cannot drop the host operation or revive withdrawn authority."""
    from backend.research.models import ResearchForbidden
    from backend.research.parser_process import PDFParser
    from backend.runtime.live_grants import LiveGrants

    gate = LiveGrants()
    gate.activate("structured-owner")
    parser = PDFParser(owner=gate, grant_id="structured-owner").for_format(kind)
    _, provenance = parser.read(data)
    assert provenance["execution"]["worker_closed"] is True
    assert provenance["execution"]["cpu_limit_seconds"] == 2
    gate.withdraw("structured-owner")
    with pytest.raises(ResearchForbidden):
        parser.read(data)


def test_json_pointer_namespace_xml_and_csv_multiline_identity_are_not_flattened_away():
    """Retain escaped keys, expanded namespaces, mixed text and logical multiline records."""
    from backend.research.parser_process import DocumentParser

    content, provenance = DocumentParser(format="json").read(
        b'{"a/b":{"~x":["",null,1e+03,{}]}}'
    )
    assert [u["locator"] for u in provenance["units"]] == [
        "/a~1b/~0x/0",
        "/a~1b/~0x/1",
        "/a~1b/~0x/2",
        "/a~1b/~0x/3",
    ]
    assert "1e+03" in content and "null" in content and "{}" in content
    content, provenance = DocumentParser(format="xml").read(
        '<x xmlns="urn:trial">Antes<result id="A">否定</result>Después</x>'.encode(
            "utf-16"
        )
    )
    assert "Antes" in content and "否定" in content and "Después" in content
    assert any("{urn:trial}result[1]/@id" in u["locator"] for u in provenance["units"])
    content, provenance = DocumentParser(format="csv").read(
        b'key;result\ncontrol;"line one\nNo improvement"\n'
    )
    assert provenance["delimiter"] == ";" and len(provenance["units"]) == 2
    assert "No improvement" in content


def test_csv_field_budget_is_reported_as_a_limit_without_a_partial_capture():
    """A valid oversized CSV field should request smaller input, not claim malformed syntax."""
    from backend.research.models import SourceTooLarge
    from backend.research.parser_process import DocumentParser

    with pytest.raises(SourceTooLarge):
        DocumentParser(format="csv").read(b"header\n" + b"X" * 65537 + b"\n")
