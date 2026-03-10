"""Web fetch tool for extracting readable content from URLs."""

import asyncio
import sqlite3
from typing import Literal, Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry
from backend.tools.web.rate_limiter import web_rate_limiter
from backend.tools.web.robots_checker import robots_checker


class WebFetchInput(BaseModel):
    url: str = Field(..., description="URL to fetch content from")
    format: Literal["markdown", "text"] = Field(
        default="markdown", description="Output format: 'markdown' or 'text'"
    )
    bypass_cache: bool = Field(
        default=False,
        description="Set to true to skip the cache and fetch fresh content",
    )


class WebFetchTool(InfinibayBaseTool):
    name: str = "web_fetch"
    description: str = (
        "Fetch and extract readable content from a URL. "
        "Returns clean text or markdown, stripping ads and navigation."
    )
    args_schema: Type[BaseModel] = WebFetchInput

    def _check_cache(self, url: str, format: str) -> str | None:
        """Return cached content if fresh enough, else None."""
        def _query(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                """\
                SELECT content, fetched_at
                FROM web_cache
                WHERE url = ? AND format = ?
                  AND fetched_at > datetime('now', ?)
                """,
                (url, format, f"-{settings.WEB_CACHE_TTL_SECONDS} seconds"),
            ).fetchone()
            return row["content"] if row else None
        try:
            return execute_with_retry(_query)
        except Exception:
            return None

    def _store_cache(self, url: str, format: str, content: str) -> None:
        """Store fetched content in the cache."""
        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """\
                INSERT INTO web_cache (url, format, content)
                VALUES (?, ?, ?)
                ON CONFLICT(url, format) DO UPDATE SET
                    content    = excluded.content,
                    fetched_at = CURRENT_TIMESTAMP
                """,
                (url, format, content),
            )
            conn.commit()
        try:
            execute_with_retry(_insert)
        except Exception:
            pass  # Cache write failure is non-fatal

    def _run(self, url: str, format: str = "markdown", bypass_cache: bool = False) -> str:
        # Check cache first
        if not bypass_cache:
            cached = self._check_cache(url, format)
            if cached is not None:
                self._log_tool_usage(f"Cache hit for {url} ({len(cached)} chars)")
                return cached

        try:
            import httpx
        except ImportError:
            return self._error("httpx not installed. Run: pip install httpx")

        try:
            import trafilatura
        except ImportError:
            return self._error(
                "trafilatura not installed. Run: pip install trafilatura"
            )

        # Check robots.txt
        if not robots_checker.is_allowed(url, "InfinibayBot/2.0"):
            return self._error("robots.txt disallows fetching this URL")

        # Rate limit
        web_rate_limiter.acquire()

        # Fetch URL
        try:
            with httpx.Client(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; InfinibayBot/2.0)"},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.TimeoutException:
            return self._error(f"Request timed out after {settings.WEB_TIMEOUT}s")
        except httpx.HTTPStatusError as e:
            return self._error(f"HTTP error {e.response.status_code}: {url}")
        except Exception as e:
            return self._error(f"Fetch failed: {e}")

        # Extract content
        output_format = "markdown" if format == "markdown" else "txt"
        try:
            content = trafilatura.extract(
                html,
                output_format=output_format,
                include_links=(format == "markdown"),
                include_tables=True,
                favor_recall=True,
            )
        except Exception as e:
            return self._error(f"Content extraction failed: {e}")

        if not content:
            return self._error(f"No readable content extracted from {url}")

        self._store_cache(url, format, content)
        self._log_tool_usage(f"Fetched {url} ({len(content)} chars)")
        return content

    async def _arun(self, url: str, format: str = "markdown", bypass_cache: bool = False) -> str:
        """Async version using httpx async client."""
        # Check cache first
        if not bypass_cache:
            cached = self._check_cache(url, format)
            if cached is not None:
                self._log_tool_usage(f"Cache hit for {url} ({len(cached)} chars)")
                return cached

        try:
            import httpx
            import trafilatura
        except ImportError as e:
            return self._error(f"Missing dependency: {e}")

        # Check robots.txt
        if not await robots_checker.is_allowed_async(url, "InfinibayBot/2.0"):
            return self._error("robots.txt disallows fetching this URL")

        # Rate limit
        await web_rate_limiter.acquire_async()

        try:
            async with httpx.AsyncClient(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; InfinibayBot/2.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.TimeoutException:
            return self._error(f"Request timed out after {settings.WEB_TIMEOUT}s")
        except httpx.HTTPStatusError as e:
            return self._error(f"HTTP error {e.response.status_code}: {url}")
        except Exception as e:
            return self._error(f"Fetch failed: {e}")

        output_format = "markdown" if format == "markdown" else "txt"
        try:
            content = await asyncio.to_thread(
                trafilatura.extract,
                html,
                output_format=output_format,
                include_links=(format == "markdown"),
                include_tables=True,
                favor_recall=True,
            )
        except Exception as e:
            return self._error(f"Content extraction failed: {e}")

        if not content:
            return self._error(f"No readable content extracted from {url}")

        self._store_cache(url, format, content)
        self._log_tool_usage(f"Fetched {url} ({len(content)} chars)")
        return content
