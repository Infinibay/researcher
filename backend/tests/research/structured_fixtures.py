"""Small original document bytes for structured capture, without model or office dependencies."""

import io
import zipfile

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_bytes(body=None, extra=None):
    """Create a minimal WordprocessingML package with actual paragraph/table structure."""
    if body is None:
        body = "<w:p><w:r><w:t>Preliminary assumption.</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>No improvement</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
        )
        for name, value in (extra or {}).items():
            archive.writestr(name, value)
    return buffer.getvalue()


def formats():
    """Return four real formats sharing one decisive phrase for native citation checks."""
    return [
        ("csv", "text/csv", b'name,result\ncontrol,"No improvement"\n'),
        (
            "json",
            "application/json",
            b'{"trials":[{"result":"No improvement","rate":0.10000000000000001}]}',
        ),
        (
            "xml",
            "application/xml",
            b'<trials><trial id="control"><result>No improvement</result></trial></trials>',
        ),
        ("docx", DOCX, docx_bytes()),
    ]
