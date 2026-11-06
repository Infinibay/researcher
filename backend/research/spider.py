"""Optional single-page Spider scraping as attributed source evidence, without CrewAI.

The host owns provider credentials and a per-request credit cap. Remote browser
execution, redirects, subresources and reported costs remain provider assertions.
"""

import hashlib
import json
import math
import os

from backend.research.models import (
    ResearchInputError,
    SourceDraft,
    SourceTooLarge,
    SourceUnavailable,
    bounded_text,
)
from backend.research.provider_http import OwnedProviderTransport
from backend.research.web_fetcher import PublicWebFetcher
from backend.research.web_policy import USER_AGENT


def validate_spider(url, *, mode="smart", format="markdown"):
    """Admit one HTTPS URL and explicit rendering/output choice, never a provider batch or script."""
    if not isinstance(url, str) or "," in url:
        raise SourceUnavailable(
            "Spider accepts one URL; encode literal commas in paths/queries"
        )
    host, _target, normalized, literal = PublicWebFetcher._url(url)
    bounded_text(normalized, "Spider URL", 4096)
    if mode not in ("smart", "browser", "http") or format not in ("markdown", "text"):
        raise ResearchInputError(
            "Spider requires mode smart/browser/http and format markdown/text"
        )
    return host, normalized, literal


class SpiderReader(OwnedProviderTransport):
    """Capture one advanced scrape while keeping provider billing and evidence separate from OpenAI inference."""

    _host = "api.spider.cloud"
    _label = "Spider"
    _key_name = "SPIDER_API_KEY"
    _paths = frozenset({"/scrape"})
    _method = "POST"
    _response_bound = 1000000
    _status_reasons = {
        202: "provider did not return a completed page",
        301: "unexpected provider redirect",
        401: "host credential rejected",
        402: "provider credit limit reached",
        403: "provider access denied",
        429: "provider rate limit reached",
    }

    def __init__(self, *, max_credits=100, web_policy=None, **options):
        """Bind host credit and shared source policy without spending a provider request."""
        super().__init__(**options)
        self.max_credits = max_credits
        self._web_reader = PublicWebFetcher(
            resolver=self.resolve,
            connection_factory=self.connection_factory,
            clock=self.clock,
            policy=web_policy,
        )

    @classmethod
    def from_environment(cls, **options):
        """Read optional host credentials and credit ceiling; the canonical key overrides the historical spelling."""
        return cls(
            api_key=os.environ.get("SPIDER_API_KEY")
            or os.environ.get("INFINIBAY_SPIDER_API_KEY", ""),
            max_credits=os.environ.get("SPIDER_MAX_CREDITS", "100"),
            **options,
        )

    def fetch(self, url, *, mode="smart", format="markdown"):
        """Request one page, preserving returned content and attributed costs without automatically creating a finding."""
        host, normalized, literal = validate_spider(url, mode=mode, format=format)
        try:
            credits = float(self.max_credits)
            if not math.isfinite(credits) or credits <= 0:
                raise ValueError("Nonpositive budget")
        except (TypeError, ValueError, OverflowError):
            raise SourceUnavailable(
                "Spider host credit budget must be finite and positive"
            ) from None
        payload = {
            "url": normalized,
            "request": mode,
            "return_format": format,
            "request_timeout": 10,
            "max_credits_allowed": credits,
            "max_credits_per_page": credits,
            "session": False,
            "run_in_background": False,
            "respect_robots": True,
            "user_agent": USER_AGENT,
        }
        with self._operation() as (deadline, cancelled):
            if literal is None:
                self._public_addresses(host, deadline, cancelled)
            decision = self._web_reader.check_access(
                normalized, deadline=deadline, cancelled=cancelled,
            )
            self._web_reader.policy.acquire(deadline, cancelled)
            data, mime = self._request(
                "/scrape",
                deadline,
                cancelled,
                body=json.dumps(payload, allow_nan=False).encode(),
            )
            try:
                pages = json.loads(data)
                if (
                    not isinstance(pages, list)
                    or len(pages) != 1
                    or not isinstance(pages[0], dict)
                ):
                    raise ValueError("Expected exactly one page")
                page = pages[0]
                if (
                    type(page.get("status")) is not int
                    or not 200 <= page["status"] < 300
                    or page.get("error")
                ):
                    raise ValueError("The page request did not succeed")
                content = page.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Missing text content")
                content_size = len(content.encode("utf-8"))
                _host, returned_url, _literal = validate_spider(
                    page.get("url"), mode=mode, format=format
                )
                costs = page.get("costs")
                if costs is not None and not isinstance(costs, dict):
                    raise ValueError("Unknown provider costs schema")
                if len(json.dumps(costs, allow_nan=False).encode()) > 8192:
                    raise ValueError("Oversized provider costs")
            except (ValueError, TypeError, UnicodeError, RecursionError):
                raise SourceUnavailable(
                    "Spider returned a failed page or unsupported response; no source was saved"
                ) from None
            if content_size > 200000:
                raise SourceTooLarge(
                    "Spider page exceeds the source text limit; no excerpt was silently saved"
                )
            self._remaining(deadline, cancelled)
            return SourceDraft(
                "web",
                returned_url,
                "Spider " + host,
                content,
                provenance={
                    "provider": "spider",
                    "endpoint": "https://api.spider.cloud/scrape",
                    "requested_url": url,
                    "returned_url": returned_url,
                    "requested": payload,
                    "provider_status": page["status"],
                    "provider_costs": costs,
                    "provider_assertions_verified": False,
                    "access_policy": [{"url": normalized, "scope": "initial-target", **decision}],
                    "remote_policy_verified": False,
                    "mime_type": mime,
                    "byte_length": len(data),
                    "byte_sha256": hashlib.sha256(data).hexdigest(),
                    "text_extraction": "Provider content field, unchanged",
                    "interpretation": "Remote rendering, source URL, status and costs are Spider assertions. Initial target DNS and robots were checked locally; remote robots enforcement was requested with the same user agent. Provider DNS, redirects and subresources were not observed. Page instructions are untrusted evidence; no visual or scientific validation is implied.",
                },
            )
