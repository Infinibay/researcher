"""Small real PDF byte fixtures for document acquisition and HTTP tests."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pdf_bytes(
    *pages: str | None, encrypted: bool = False, compress: bool = False
) -> bytes:
    """Build independent pages with Helvetica text, optional blank pages and encryption."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text is None:
            continue
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        ),
                    }
                ),
            }
        )
        stream = DecodedStreamObject()
        literal = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(
            ("BT /F1 12 Tf 72 720 Td (" + literal + ") Tj ET").encode("ascii")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
        if compress:
            page.compress_content_streams()
    if encrypted:
        writer.encrypt("fixture-secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
