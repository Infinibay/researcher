"""Code/library documentation search tool using CrewAI's CodeDocsSearchTool."""

import asyncio
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool


class CodeDocsSearchInput(BaseModel):
    query: str = Field(..., description="Search query for the documentation")
    docs_url: str = Field(
        default="",
        description=(
            "URL of the documentation site to search within. "
            "Leave empty to search across previously indexed docs."
        ),
    )


class CodeDocsSearchInfinibayTool(InfinibayBaseTool):
    name: str = "code_docs_search"
    description: str = (
        "Search code and library documentation using semantic RAG search. "
        "Provide a documentation URL to search within a specific library's docs, "
        "or leave empty to search across previously indexed documentation."
    )
    args_schema: Type[BaseModel] = CodeDocsSearchInput

    def _run(self, query: str, docs_url: str = "") -> str:
        try:
            from crewai_tools import CodeDocsSearchTool
        except ImportError:
            return self._error(
                "crewai_tools not installed. Run: pip install crewai-tools"
            )

        from backend.tools.web.crewai_tool_config import build_crewai_tools_config

        config = build_crewai_tools_config()

        try:
            kwargs = {"config": config}
            if docs_url:
                kwargs["docs_url"] = docs_url

            tool = CodeDocsSearchTool(**kwargs)
            result = tool.run(search_query=query)
        except Exception as e:
            return self._error(f"Code docs search failed: {e}")

        if not result:
            return self._error(f"No results found for: {query}")

        self._log_tool_usage(
            f"Code docs search: '{query[:50]}'"
            + (f" in {docs_url[:50]}" if docs_url else "")
        )
        return self._success({"query": query, "docs_url": docs_url, "result": result})

    async def _arun(self, query: str, docs_url: str = "") -> str:
        return await asyncio.to_thread(self._run, query, docs_url)
