"""Context7 documentation retrieval — fetch up-to-date docs for a library."""

from __future__ import annotations

import os
from typing import Literal, Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool

_API_BASE = "https://context7.com/api/v2"


class Context7DocsInput(BaseModel):
    library_id: str = Field(
        ...,
        description=(
            "Context7-compatible library ID obtained from context7_search_library "
            "(e.g. '/vercel/next.js', '/facebook/react', '/tiangolo/fastapi'). "
            "Must start with '/'."
        ),
    )
    topic: str = Field(
        ...,
        description=(
            "Specific topic or question to search for in the documentation. "
            "Be specific — 'how to configure middleware' is better than 'middleware'. "
            "'authentication with JWT' is better than 'auth'."
        ),
    )
    format: Literal["json", "txt"] = Field(
        default="txt",
        description=(
            "Response format. 'txt' returns plain text optimized for LLM consumption "
            "(recommended). 'json' returns structured objects with title, content, and URL."
        ),
    )


class Context7DocsTool(PabadaBaseTool):
    name: str = "context7_get_docs"
    description: str = (
        "Fetch up-to-date documentation and code examples for a library from "
        "Context7. Use this to get current API references, usage examples, and "
        "guides. You must call context7_search_library first to get the library_id, "
        "unless you already know it. Provide a specific topic to get relevant "
        "documentation snippets."
    )
    args_schema: Type[BaseModel] = Context7DocsInput

    def _run(
        self,
        library_id: str,
        topic: str,
        format: str = "txt",
    ) -> str:
        if not library_id.startswith("/"):
            return self._error(
                f"Invalid library_id '{library_id}'. Must start with '/' "
                "(e.g. '/vercel/next.js'). Use context7_search_library to find "
                "the correct ID."
            )

        try:
            import httpx
        except ImportError:
            return self._error("httpx not installed. Run: pip install httpx")

        api_key = os.environ.get("PABADA_CONTEXT7_API_KEY", "")
        headers = {"User-Agent": "PabadaBot/2.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = f"{_API_BASE}/context"
        params = {
            "query": topic,
            "libraryId": library_id,
            "type": format,
        }

        try:
            with httpx.Client(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(url, params=params)

                # Handle special status codes
                if response.status_code == 202:
                    return self._error(
                        f"Library '{library_id}' is still being indexed by Context7. "
                        "Please retry in a few minutes."
                    )
                if response.status_code == 301:
                    new_id = response.headers.get("Location", "")
                    return self._error(
                        f"Library ID '{library_id}' has been moved to '{new_id}'. "
                        "Use the new ID."
                    )

                response.raise_for_status()
        except httpx.TimeoutException:
            return self._error(
                f"Context7 docs request timed out after {settings.WEB_TIMEOUT}s"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return self._error(
                    "Context7 rate limit exceeded. Set PABADA_CONTEXT7_API_KEY "
                    "for higher limits, or wait and retry."
                )
            if e.response.status_code == 400:
                return self._error(
                    f"Invalid parameters. Verify library_id '{library_id}' is correct "
                    "(use context7_search_library to check)."
                )
            return self._error(f"Context7 API error {e.response.status_code}")
        except Exception as e:
            return self._error(f"Context7 docs fetch failed: {e}")

        # Handle txt format (plain text response)
        if format == "txt":
            content = response.text.strip()
            if not content:
                return self._error(
                    f"No documentation found for topic '{topic}' in '{library_id}'. "
                    "Try a different topic or more general query."
                )
            self._log_tool_usage(
                f"Fetched Context7 docs for {library_id} topic='{topic}' "
                f"({len(content)} chars)"
            )
            return content

        # Handle json format
        try:
            data = response.json()
        except Exception:
            return self._error("Failed to parse Context7 response as JSON")

        if not data:
            return self._error(
                f"No documentation found for topic '{topic}' in '{library_id}'. "
                "Try a different topic or more general query."
            )

        # Format JSON results
        results = []
        for snippet in data[:15]:  # Cap at 15 snippets
            results.append({
                "title": snippet.get("title", ""),
                "content": snippet.get("content", ""),
                "url": snippet.get("url", ""),
            })

        self._log_tool_usage(
            f"Fetched Context7 docs for {library_id} topic='{topic}' "
            f"({len(results)} snippets)"
        )
        return self._success({"snippets": results, "count": len(results)})
