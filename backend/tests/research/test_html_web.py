"""Preserve readable HTML evidence through the owned parser instead of a legacy scraper."""

import re

import pytest

from backend.research.models import SourceUnavailable
from backend.tests.research.test_web_fetcher import fetcher


def test_html_capture_keeps_links_tables_and_closed_parser_provenance():
    """A text-only fallback loses source links that the native capture must preserve."""
    body = b'''<html><head><title>Reference policy</title></head><body><article>
    <h1>Reference policy</h1><p>The documented timeout is five seconds.
    Consult the <a href="https://manual.example.org/timeouts">timeout source</a>
    for the exact behavior.</p><table><tr><th>Setting</th><th>Value</th></tr>
    <tr><td>Timeout</td><td>5 seconds</td></tr></table>
    <p>These settings apply to each individual request.</p></article>
    <script>Never turn this script into evidence.</script></body></html>'''
    wire = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: "
        + str(len(body)).encode() + b"\r\n\r\n" + body
    )
    web, _, _ = fetcher([wire])
    source = web.fetch("https://docs.example.org/policy")
    assert "https://manual.example.org/timeouts" in source.content
    assert "Timeout" in source.content and "5 seconds" in source.content
    assert re.search(r"\|\s*Timeout\s*\|\s*5 seconds\s*\|", source.content)
    assert "Never turn this script" not in source.content
    assert source.title == "Reference policy"
    assert source.provenance["text_format"] == "markdown"
    assert source.provenance["execution"]["worker_closed"] is True


def test_html_without_readable_content_does_not_return_a_successful_partial_source():
    """Script-only or empty documents must not become apparently valid research evidence."""
    from backend.research.parser_process import DocumentParser

    with pytest.raises(SourceUnavailable):
        DocumentParser(format="html").read(b"<html><script>private()</script></html>")
