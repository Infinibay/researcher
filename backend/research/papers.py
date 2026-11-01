"""Resolve a supplied paper locator without treating identifiers as verified metadata.

This module performs no I/O. Actual URL/redirect policy, extraction, ownership and
source persistence remain in the existing acquisition service and public fetcher.
"""

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

from backend.research.models import ResearchInputError, bounded_text


@dataclass(frozen=True)
class PaperLocator:
    """One normalized owner/model-supplied locator and the HTTPS target to capture."""

    kind: Literal["url", "doi", "arxiv"]
    value: str
    url: str
    version_selection: Literal["explicit", "latest_at_capture"] | None = None

    def provenance(self) -> dict[str, str | bool | None]:
        """Record supplied identity/version policy without claiming registration or authorship."""
        return {
            "kind": self.kind,
            "value": self.value,
            "version_selection": self.version_selection,
            "identifier_verified": False,
        }


def resolve_paper(*, url=None, doi=None, arxiv_id=None) -> PaperLocator:
    """Require exactly one locator; percent-encode DOI URI syntax and preserve arXiv versions.

    DOI length and allowed whitespace are application bounds, not a complete DOI
    registry validator. arXiv accepts modern and archival ids with an optional
    positive version. Syntax does not establish existence or scientific quality.
    Explicit URLs still require the public fetcher's complete destination policy.
    """
    supplied = [
        (kind, value)
        for kind, value in [("url", url), ("doi", doi), ("arxiv", arxiv_id)]
        if value is not None
    ]
    if len(supplied) != 1:
        raise ResearchInputError("Provide exactly one of url, doi or arxiv_id")
    kind, value = supplied[0]
    bounded_text(value, "paper locator", 4096 if kind == "url" else 2048)
    value = value.strip()
    if kind == "url":
        return PaperLocator(kind, value, value)
    if kind == "doi":
        if value[:4].lower() == "doi:":
            value = value[4:].strip()
        if not re.fullmatch(r"10\.[0-9]+(?:\.[0-9]+)*/.+", value) or any(
            c.isspace() or not c.isprintable() for c in value
        ):
            raise ResearchInputError(
                "Expected a bare DOI beginning with 10. and a nonempty suffix"
            )
        prefix, suffix = value.split("/", 1)
        encoded = quote(suffix, safe="")
        if suffix in (".", ".."):
            encoded = encoded.replace(".", "%2E")
        target = "https://doi.org/" + prefix + "/" + encoded
        bounded_text(target, "encoded paper URL", 4096)
        return PaperLocator(kind, value, target)
    if value[:6].lower() == "arxiv:":
        value = value[6:].strip()
    month = r"[0-9]{2}(?:0[1-9]|1[0-2])"
    modern = month + r"\.[0-9]{4,5}"
    archival = r"[a-z][a-z-]*(?:\.[A-Z]{2})?/" + month + r"[0-9]{3}"
    if (
        not re.fullmatch("(?:" + modern + "|" + archival + r")(?:v[1-9][0-9]*)?", value)
        or len(value) > 256
    ):
        raise ResearchInputError(
            "Expected a modern or archival arXiv id with an optional positive version"
        )
    version = "explicit" if re.search(r"v[1-9][0-9]*$", value) else "latest_at_capture"
    return PaperLocator(kind, value, "https://arxiv.org/pdf/" + value, version)
