"""Extract bounded PDF text and page offsets without OCR or external executables.

The caller supplies a byte snapshot already confined to project uploads. Parser
budgets bound pages, decoded streams, object work and resulting UTF-8 text; they
are not an OS CPU/RSS sandbox. Production acquisition calls this inside PDFParser's
OS-limited worker. Captured text may differ from visual reading order.
"""

from io import BytesIO

from pypdf import PdfReader, __version__, apply_configuration
from pypdf.errors import LimitReachedError, PyPdfError

from backend.research.models import SourceTooLarge, SourceUnavailable


def extract_pdf(
    data: bytes,
    *,
    max_pages: int = 100,
    max_text_bytes: int = 200000,
    max_stream_bytes: int = 1000000,
) -> tuple[str, dict]:
    """Return complete extracted text plus page provenance, or reject the capture.

    Offsets address Python characters in the returned source (the same convention
    as source_read/search). Empty pages are retained and identified, encrypted or
    wholly textless documents fail explicitly, and limits never yield partial text.
    Configuration is local to this execution context and restored even on failure.
    """
    if any(
        type(limit) is not int or limit <= 0
        for limit in (max_pages, max_text_bytes, max_stream_bytes)
    ):
        raise ValueError("PDF extraction limits must be positive integers")
    if not data.startswith(b"%PDF-"):
        raise SourceUnavailable("PDF is malformed: missing PDF header")
    try:
        with (
            apply_configuration(
                maximum_declared_stream_length=max_stream_bytes,
                array_based_stream_maximum_output_length=max_stream_bytes,
                zlib_maximum_output_length=max_stream_bytes,
                lzw_maximum_output_length=max_stream_bytes,
                run_length_maximum_output_length=max_stream_bytes,
                brotli_maximum_output_length=max_stream_bytes,
                jbig2_maximum_output_length=max_stream_bytes,
                stream_decoding_work_maximum_length=max_stream_bytes * 4,
                stream_parsing_work_maximum_count=200000,
                stream_filters_maximum_length=8,
                array_maximum_element_count=10000,
                dictionary_maximum_element_count=10000,
                page_tree_maximum_entries=max_pages * 4 + 16,
                page_tree_maximum_depth=30,
                page_tree_maximum_page_entries=max_pages * 100,
                xform_maximum_invocations_per_extraction=100,
                jbig2dec_binary=None,
            ),
            BytesIO(data) as stream,
        ):
            reader = PdfReader(
                stream,
                strict=True,
                root_object_recovery_limit=1000,
                xref_stream_maximum_entries=100000,
            )
            if reader.is_encrypted:
                raise SourceUnavailable(
                    "PDF is encrypted; provide a decrypted copy without sending its password"
                )
            count = len(reader.pages)
            if count > max_pages:
                raise SourceTooLarge(
                    "PDF exceeds the configured page limit; split it into smaller documents"
                )
            chunks, pages, empty = [], [], []
            offset = byte_count = 0
            for number, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                prefix = ("\n\n" if number > 1 else "") + f"[Page {number}]\n"
                chunk = prefix + text
                byte_count += len(chunk.encode("utf-8"))
                if byte_count > max_text_bytes:
                    raise SourceTooLarge(
                        "PDF extracted text exceeds the configured limit; no partial source was saved"
                    )
                start = offset + len(prefix)
                offset += len(chunk)
                pages.append(
                    {
                        "page_number": number,
                        "text_start_offset": start,
                        "end_offset": offset,
                        "has_text": bool(text),
                    }
                )
                if not text:
                    empty.append(number)
                chunks.append(chunk)
            if len(empty) == count:
                raise SourceUnavailable(
                    "PDF has no extractable text; OCR is required before it can be cited"
                )
            return "".join(chunks), {
                "extraction": "pypdf-text-v1",
                "parser_version": __version__,
                "limits": {
                    "max_pages": max_pages,
                    "max_text_bytes": max_text_bytes,
                    "max_decoded_stream_bytes": max_stream_bytes,
                },
                "page_count": count,
                "pages": pages,
                "pages_without_text": empty,
                "ocr_performed": False,
                "extraction_note": "Text extraction only; visual reading order, tables and images are not verified. Pages without text may require OCR.",
            }
    except SourceTooLarge:
        raise
    except LimitReachedError as exc:
        raise SourceTooLarge(
            "PDF exceeds the configured decoding or object-work limit; no partial source was saved"
        ) from exc
    except (
        PyPdfError,
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        RecursionError,
    ) as exc:
        raise SourceUnavailable(
            "PDF is malformed or cannot be extracted reliably; provide a valid text-bearing copy"
        ) from exc
