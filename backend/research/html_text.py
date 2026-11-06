"""Extract readable local HTML snapshots inside the bounded document worker.

This module only parses supplied markup. It does not fetch links, execute page
scripts or treat extracted content as trusted instructions or verified findings.
"""

from importlib.metadata import version

from trafilatura import extract

from backend.research.models import SourceTooLarge, SourceUnavailable


def extract_html(data):
    """Keep readable text, link targets and tables in one bounded Markdown snapshot."""
    content = extract(
        data.decode("utf-8"),
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_formatting=True,
        include_comments=False,
        favor_recall=True,
    )
    if not content or not content.strip():
        raise SourceUnavailable("HTML contains no readable content; no source was saved")
    if len(content.encode("utf-8")) > 200000:
        raise SourceTooLarge("Readable HTML exceeds the source text limit")
    return content, {
        "format": "html",
        "text_format": "markdown",
        "extraction": "html-readability-v1",
        "parser": "trafilatura",
        "parser_version": version("trafilatura"),
        "quote_scope": "normalized_snapshot",
        "interpretation": "Readable Markdown extracted from decoded HTML. Links are retained references, not fetched evidence. Layout, scripts and omitted page chrome are not represented.",
    }
