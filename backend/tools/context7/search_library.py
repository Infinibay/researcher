"""Context7 library search — resolve a library name to a Context7 library ID."""

from __future__ import annotations

import os
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool

_API_BASE = "https://context7.com/api/v2"


class Context7SearchInput(BaseModel):
    library_name: str = Field(
        ...,
        description=(
            "Library or framework name to search for (e.g. 'react', 'fastapi', "
            "'langchain', 'next.js'). Be specific — 'react' not 'frontend framework'."
        ),
    )


class Context7SearchTool(PabadaBaseTool):
    name: str = "context7_search_library"
    description: str = (
        "Search for a library or framework in Context7 to get its library ID. "
        "You MUST call this tool first before using context7_get_docs, unless "
        "you already know the exact Context7 library ID (format: '/org/project'). "
        "Returns a list of matching libraries with their IDs, descriptions, "
        "and documentation coverage."
    )
    args_schema: Type[BaseModel] = Context7SearchInput

    def _run(self, library_name: str) -> str:
        try:
            import httpx
        except ImportError:
            return self._error("httpx not installed. Run: pip install httpx")

        api_key = os.environ.get("PABADA_CONTEXT7_API_KEY", "")
        headers = {"User-Agent": "PabadaBot/2.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = f"{_API_BASE}/libs/search"
        params = {
            "query": library_name,
            "libraryName": library_name,
        }

        try:
            with httpx.Client(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            return self._error(f"Context7 search timed out after {settings.WEB_TIMEOUT}s")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return self._error(
                    "Context7 rate limit exceeded. Set PABADA_CONTEXT7_API_KEY "
                    "for higher limits, or wait and retry."
                )
            return self._error(f"Context7 API error {e.response.status_code}")
        except Exception as e:
            return self._error(f"Context7 search failed: {e}")

        if not data:
            return self._error(
                f"No libraries found for '{library_name}'. "
                "Try a more specific name (e.g. 'next.js' instead of 'next')."
            )

        # Format results for the agent
        results = []
        for lib in data[:10]:  # Cap at 10 results
            entry = {
                "library_id": lib.get("id", ""),
                "name": lib.get("name", ""),
                "description": lib.get("description", "")[:200],
                "code_snippets": lib.get("codeSnippetCount", 0),
                "trust_score": lib.get("trustScore", ""),
            }
            versions = lib.get("versions", [])
            if versions:
                entry["versions"] = versions[:5]
            results.append(entry)

        self._log_tool_usage(
            f"Searched Context7 for '{library_name}' — {len(results)} results"
        )
        return self._success({"results": results, "count": len(results)})
