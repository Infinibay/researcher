"""Web fetch tool for extracting readable content from URLs."""

import asyncio
from typing import Literal, Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool


class WebFetchInput(BaseModel):
    url: str = Field(..., description="URL to fetch content from")
    format: Literal["markdown", "text"] = Field(
        default="markdown", description="Output format: 'markdown' or 'text'"
    )


class WebFetchTool(PabadaBaseTool):
    name: str = "web_fetch"
    description: str = (
        "Fetch and extract readable content from a URL. "
        "Returns clean text or markdown, stripping ads and navigation."
    )
    args_schema: Type[BaseModel] = WebFetchInput

    def _run(self, url: str, format: str = "markdown") -> str:
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

        # Fetch URL
        try:
            with httpx.Client(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PabadaBot/2.0)"},
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

        self._log_tool_usage(f"Fetched {url} ({len(content)} chars)")
        return content

    async def _arun(self, url: str, format: str = "markdown") -> str:
        """Async version using httpx async client."""
        try:
            import httpx
            import trafilatura
        except ImportError as e:
            return self._error(f"Missing dependency: {e}")

        try:
            async with httpx.AsyncClient(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PabadaBot/2.0)"},
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

        self._log_tool_usage(f"Fetched {url} ({len(content)} chars)")
        return content
