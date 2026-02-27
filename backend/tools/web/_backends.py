"""Shared web search and fetch backends for PABADA web tools.

Provides pure functions (no PabadaBaseTool dependency) that can be reused
by WebSearchTool, DeepWebResearchTool, and any future tool that needs
web search or content fetching.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config.settings import settings
from backend.tools.web.rate_limiter import web_rate_limiter

logger = logging.getLogger(__name__)


def search_serper(query: str, num_results: int = 10) -> list[dict] | None:
    """Search via SerperDev API.

    Returns list of ``{title, url, snippet}`` dicts, or ``None`` if the
    search fails (triggering fallback to DDG).
    """
    if not settings.SERPER_API_KEY:
        return None

    try:
        from crewai_tools import SerperDevTool
    except ImportError:
        logger.debug("crewai_tools not installed, skipping Serper search")
        return None

    web_rate_limiter.acquire()

    try:
        kwargs: dict[str, Any] = {"n_results": num_results}
        if settings.SERPER_COUNTRY:
            kwargs["country"] = settings.SERPER_COUNTRY

        tool = SerperDevTool(**kwargs)
        raw = tool.run(search_query=query)

        # SerperDevTool returns a string with results; parse it
        if not raw or not isinstance(raw, str):
            return None

        # The tool returns formatted text; convert to structured results.
        # Each result block typically has "Title:", "Link:", "Snippet:" lines.
        results: list[dict] = []
        import json
        try:
            # Try JSON first (some versions return JSON)
            data = json.loads(raw)
            if isinstance(data, list):
                for item in data:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", item.get("url", "")),
                        "snippet": item.get("snippet", item.get("description", "")),
                    })
            elif isinstance(data, dict) and "organic" in data:
                for item in data["organic"]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    })
        except (json.JSONDecodeError, TypeError):
            # Fallback: return the raw text as a single result
            results.append({
                "title": "Search Results",
                "url": "",
                "snippet": raw[:500],
            })

        if results:
            logger.debug("Serper search returned %d results for: %s", len(results), query[:60])
            return results
        return None

    except Exception as exc:
        logger.warning("Serper search failed: %s", exc)
        return None


def search_ddg(query: str, num_results: int = 10) -> list[dict]:
    """Search via DuckDuckGo (fallback).

    Returns list of ``{title, url, snippet}`` dicts.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.warning("Neither ddgs nor duckduckgo_search installed")
            return []

    web_rate_limiter.acquire()

    try:
        ua_headers = {"User-Agent": "Mozilla/5.0 (compatible; PabadaBot/2.0)"}
        try:
            ddgs = DDGS(headers=ua_headers)
        except TypeError:
            ddgs = DDGS()
        raw_results = list(ddgs.text(query, max_results=num_results))
    except Exception as exc:
        logger.warning("DDG search failed: %s", exc)
        return []

    results = []
    for r in raw_results:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("href", r.get("link", "")),
            "snippet": r.get("body", r.get("snippet", "")),
        })
    return results


def unified_search(query: str, num_results: int = 10) -> list[dict]:
    """Serper -> DDG fallback transparent search.

    If ``SERPER_API_KEY`` is configured, tries Serper first.
    Falls back to DDG if Serper fails or is not configured
    (and ``WEB_SEARCH_FALLBACK_ENABLED`` is True).
    """
    # Try Serper first
    if settings.SERPER_API_KEY:
        results = search_serper(query, num_results)
        if results:
            return results
        logger.debug("Serper returned no results, falling back to DDG")

    # Fallback to DDG
    if settings.WEB_SEARCH_FALLBACK_ENABLED or not settings.SERPER_API_KEY:
        return search_ddg(query, num_results)

    return []


def fetch_with_trafilatura(url: str, timeout: int | None = None) -> str | None:
    """Fetch URL and extract content with trafilatura.

    Returns extracted text or ``None`` on failure.
    """
    try:
        import httpx
    except ImportError:
        return None

    try:
        import trafilatura
    except ImportError:
        return None

    if timeout is None:
        timeout = settings.WEB_TIMEOUT

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PabadaBot/2.0)"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except Exception:
        return None

    try:
        content = trafilatura.extract(html, output_format="txt", favor_recall=True)
    except Exception:
        return None

    return content


def scrape_with_crewai(url: str) -> str | None:
    """Scrape URL using CrewAI's ScrapeWebsiteTool.

    Returns extracted text or ``None`` on failure.
    """
    try:
        from crewai_tools import ScrapeWebsiteTool
    except ImportError:
        logger.debug("crewai_tools not installed, cannot scrape")
        return None

    try:
        tool = ScrapeWebsiteTool(website_url=url)
        result = tool.run()
        if result and isinstance(result, str) and len(result.strip()) > 0:
            return result.strip()
        return None
    except Exception as exc:
        logger.warning("CrewAI scrape failed for %s: %s", url, exc)
        return None
