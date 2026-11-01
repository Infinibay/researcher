"""Extract bounded structured snapshots with normalized text and recoverable locators.

Quotes address the canonical snapshot, not original serialization or Word layout.
This module runs in the host-owned parser worker, without model/tool credentials.
"""

import csv
import json
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from backend.research.models import SourceTooLarge, SourceUnavailable

MAX_TEXT = 200000
MAX_UNITS = 5000
MAX_DEPTH = 64
MAX_NODES = 20000
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class Units:
    """Build canonical text and exact character offsets without silent truncation."""

    def __init__(self):
        """Start an empty bounded document; no external storage or model is involved."""
        self.chunks, self.units = [], []
        self.length = self.bytes = 0

    def add(self, kind, locator, text):
        """Append one complete semantic unit or reject the entire oversized snapshot."""
        if len(self.units) >= MAX_UNITS or len(locator.encode("utf-8")) > 1024:
            raise SourceTooLarge("Document exceeds structural unit or locator limits")
        chunk = ("\n\n" if self.chunks else "") + f"[{kind} {locator}]\n" + text
        self.bytes += len(chunk.encode("utf-8"))
        if self.bytes > MAX_TEXT:
            raise SourceTooLarge("Document normalized text exceeds its byte limit")
        start = self.length + len(chunk) - len(text)
        # Empty values have explicit serialized representations, never empty ranges.
        self.units.append(
            {
                "index": len(self.units),
                "kind": kind,
                "locator": locator,
                "start_offset": start,
                "end_offset": start + len(text),
            }
        )
        self.chunks.append(chunk)
        self.length += len(chunk)

    def finish(self, kind, **metadata):
        """Return complete extraction provenance, including its declared interpretation."""
        if not self.units:
            raise SourceUnavailable(
                "Document contains no supported extractable content"
            )
        return "".join(self.chunks), {
            "format": kind,
            "extraction": f"structured-{kind}-v1",
            "units": self.units,
            "unit_count": len(self.units),
            "quote_scope": "normalized_snapshot",
            "limits": {
                "max_text_bytes": MAX_TEXT,
                "max_units": MAX_UNITS,
                "max_depth": MAX_DEPTH,
                "max_nodes": MAX_NODES,
            },
            **metadata,
        }


def quoted(value):
    """Serialize strings visibly, preserving empty cells, line breaks and Unicode."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def pointer(value):
    """Escape one RFC 6901 component without changing its source identifier."""
    return value.replace("~", "~0").replace("/", "~1")


def csv_text(data):
    """Retain every CSV record; label the first-record header interpretation as assumed."""
    text = data.decode("utf-8-sig")
    try:
        delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    csv.field_size_limit(65536)
    rows = csv.reader(StringIO(text, newline=""), delimiter=delimiter, strict=True)
    units, header = Units(), None
    for index, row in enumerate(rows):
        if len(row) > 256:
            raise SourceTooLarge("CSV exceeds its column limit")
        if header is None:
            header = row
            rendered = "First record; header interpretation is ASSUMED: " + quoted(row)
        else:
            cells = []
            for column in range(max(len(header), len(row))):
                name = quoted(header[column]) if column < len(header) else "[NO HEADER]"
                value = quoted(row[column]) if column < len(row) else "[MISSING]"
                cells.append(f"column[{column + 1}] header={name} value={value}")
            rendered = "\n".join(cells) or "[EMPTY RECORD]"
        units.add("record", f"/record[{index + 1}]", rendered)
    return units.finish(
        "csv",
        delimiter=delimiter,
        header_assumed=True,
        extraction_note="First record is retained and assumed to be headers; missing and empty cells differ. Record numbers are logical CSV records, not physical lines.",
    )


class JsonNumber(str):
    """Distinguish original JSON numeric lexemes from ordinary string values."""


def json_pairs(pairs):
    """Reject duplicate object keys instead of silently discarding earlier evidence."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise SourceUnavailable(
                "JSON duplicate keys are ambiguous; capture rejected"
            )
        result[key] = value
    return result


def reject_constant(value):
    """Reject nonstandard NaN/Infinity tokens without numeric coercion."""
    raise SourceUnavailable(f"JSON nonfinite value {value} is unsupported")


def check_json_depth(text):
    """Bound nesting before the standard decoder allocates a deeply recursive tree."""
    depth, inside, escaped = 0, False, False
    for char in text:
        if inside:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                inside = False
        elif char == '"':
            inside = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise SourceTooLarge("JSON exceeds its nesting limit")
        elif char in "]}":
            depth -= 1


def json_text(data):
    """Flatten scalar/empty-container JSON values with pointers and exact numeric tokens."""
    text = data.decode("utf-8-sig")
    check_json_depth(text)
    root = json.loads(
        text,
        object_pairs_hook=json_pairs,
        parse_int=JsonNumber,
        parse_float=JsonNumber,
        parse_constant=reject_constant,
    )
    units = Units()
    stack, count = [("", root)], 0
    while stack:
        path, value = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise SourceTooLarge("JSON exceeds its node limit")
        if isinstance(value, dict) and value:
            stack.extend(
                reversed([(path + "/" + pointer(k), v) for k, v in value.items()])
            )
        elif isinstance(value, list) and value:
            stack.extend(reversed([(f"{path}/{i}", v) for i, v in enumerate(value)]))
        else:
            kind = "number" if isinstance(value, JsonNumber) else "value"
            rendered = str(value) if isinstance(value, JsonNumber) else quoted(value)
            units.add(kind, path, rendered)
    return units.finish(
        "json",
        extraction_note="RFC 6901 pointers address normalized values; numeric tokens are preserved. Whitespace/escaping of the original serialization is not quoted.",
    )


def xml_tree(data):
    """Parse XML with DTD/entities/external access forbidden and incremental depth limits."""
    depth = count = 0
    parser = ElementTree.iterparse(
        BytesIO(data),
        events=("start", "end"),
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    for event, _ in parser:
        if event == "start":
            depth += 1
            count += 1
            if depth > MAX_DEPTH or count > MAX_NODES:
                raise SourceTooLarge("XML exceeds its depth or node limit")
        else:
            depth -= 1
    return parser.root


def xml_text(data):
    """Preserve XML attributes, text and tails in document order using expanded-name paths."""
    root, units = xml_tree(data), Units()

    def visit(node, path):
        """Walk only an already depth-bounded tree and retain mixed-content positions."""
        for name, value in node.attrib.items():
            units.add("attribute", path + "/@" + pointer(name), quoted(value))
        if node.text is not None:
            units.add("text", path + "/text()[1]", quoted(node.text))
        if not node.attrib and not len(node) and node.text is None:
            units.add("element", path, "[EMPTY ELEMENT]")
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            child_path = path + "/" + pointer(child.tag) + f"[{counts[child.tag]}]"
            visit(child, child_path)
            if child.tail is not None:
                units.add("tail", child_path + "/tail()", quoted(child.tail))

    visit(root, "/" + pointer(root.tag) + "[1]")
    return units.finish(
        "xml",
        extraction_note="Paths use namespace-expanded names escaped as pointer components. Attributes, text, tails and empty elements are retained; comments/processing instructions and original markup serialization are outside extraction scope.",
    )


def docx_text(data):
    """Read only bounded DOCX main-body XML; never extract ZIP members onto disk."""
    with ZipFile(BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > 512 or sum(i.file_size for i in infos) > 8000000:
            raise SourceTooLarge("DOCX exceeds its ZIP member or expansion limit")
        names = set()
        for info in infos:
            name = info.filename
            if (
                name in names
                or name.startswith("/")
                or "\\" in name
                or ".." in PurePosixPath(name).parts
                or info.flag_bits & 1
                or info.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
            ):
                raise SourceUnavailable(
                    "DOCX contains unsupported or unsafe ZIP members"
                )
            names.add(name)

        def part(name):
            """Read one known part with both declared and actual expansion bounds."""
            info = archive.getinfo(name)
            if info.file_size > 4000000:
                raise SourceTooLarge("DOCX XML part exceeds its expansion limit")
            with archive.open(info) as stream:
                content = stream.read(4000001)
            if len(content) > 4000000:
                raise SourceTooLarge("DOCX XML part exceeds its expansion limit")
            return xml_tree(content)

        types = part("[Content_Types].xml")
        expected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if not any(
            n.attrib.get("PartName") == "/word/document.xml"
            and n.attrib.get("ContentType") == expected
            for n in types
        ):
            raise SourceUnavailable("DOCX is missing its main-document content type")
        root = part("word/document.xml")
    if root.tag != W + "document":
        raise SourceUnavailable("DOCX main part has an unsupported document namespace")
    body = root.find(W + "body")
    if body is None:
        raise SourceUnavailable("DOCX has no main document body")
    units = Units()
    excluded = {W + name for name in ("del", "moveFrom", "drawing", "pict", "object")}

    def paragraph(node):
        """Collect displayed text without deleted runs, drawings or field instructions."""
        if node.tag in excluded:
            return ""
        if node.tag == W + "t":
            return node.text or ""
        if node.tag == W + "tab":
            return "\t"
        if node.tag in (W + "br", W + "cr"):
            return "\n"
        return "".join(paragraph(child) for child in node)

    def visit(node, path):
        """Retain body paragraph order and table cell locators without inventing pages."""
        if node.tag in excluded:
            return
        if node.tag == W + "p":
            text = paragraph(node)
            if text:
                units.add("paragraph", path, text)
            return
        counts = {}
        for child in node:
            tag = child.tag.removeprefix(W)
            counts[tag] = counts.get(tag, 0) + 1
            visit(child, path + f"/{tag}[{counts[tag]}]")

    visit(body, "/body")
    return units.finish(
        "docx",
        extraction_note="Main document body paragraphs and table cell text only; no page layout, headers/footers, footnotes, comments, images, embedded objects, deleted revisions or field instructions. Displayed field results may be cached and stale; extraction is not full-document review.",
    )


def extract_structured(data, kind):
    """Dispatch one host-selected format and redact syntax errors at the source boundary."""
    extractors = {
        "csv": csv_text,
        "json": json_text,
        "xml": xml_text,
        "docx": docx_text,
    }
    if kind not in extractors:
        raise SourceUnavailable("Unsupported structured document format")
    try:
        return extractors[kind](data)
    except (SourceTooLarge, SourceUnavailable):
        raise
    except csv.Error as exc:
        if "field larger than field limit" in str(exc):
            raise SourceTooLarge("CSV field exceeds its 65536-character limit") from exc
        raise SourceUnavailable("Malformed CSV; no partial source was saved") from exc
    except (
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
        BadZipFile,
        ElementTree.ParseError,
        DefusedXmlException,
    ) as exc:
        raise SourceUnavailable(
            f"Malformed or unsupported {kind.upper()} document; no partial source was saved"
        ) from exc
