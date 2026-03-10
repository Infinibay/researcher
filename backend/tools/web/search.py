"""Web search tool using SerperDev (with DuckDuckGo fallback)."""

import asyncio
import hashlib
import time
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import InfinibayBaseTool

# Simple in-memory cache
_search_cache: dict[str, tuple[float, list]] = {}


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    num_results: int = Field(
        default=10, ge=1, le=20, description="Number of results to return"
    )


class WebSearchTool(InfinibayBaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web using SerperDev (with DuckDuckGo fallback). "
        "Returns a list of results with title, URL, and snippet."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, num_results: int = 10) -> str:
        # Check cache
        cache_key = hashlib.md5(f"{query}:{num_results}".encode()).hexdigest()
        if cache_key in _search_cache:
            cached_time, cached_results = _search_cache[cache_key]
            if time.time() - cached_time < settings.WEB_CACHE_TTL_SECONDS:
                return self._success({"results": cached_results, "cached": True})

        from backend.tools.web._backends import unified_search

        try:
            results = unified_search(query, num_results)
        except Exception as e:
            return self._error(f"Search failed: {e}")

        # Cache results
        _search_cache[cache_key] = (time.time(), results)

        self._log_tool_usage(f"Searched: {query[:60]} ({len(results)} results)")
        return self._success({"results": results, "count": len(results)})

    async def _arun(self, query: str, num_results: int = 10) -> str:
        """Async version using asyncio.to_thread."""
        return await asyncio.to_thread(self._run, query, num_results)
