"""Tool for semantic search within JSON files."""

import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.rag.base import validate_path_in_sandbox

logger = logging.getLogger(__name__)


class JSONSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    json_path: str = Field(..., description="Absolute path to the JSON file")


class JSONSearchInfinibayTool(InfinibayBaseTool):
    name: str = "json_search"
    description: str = (
        "Search within JSON files using semantic RAG. "
        "Embeds and indexes the JSON content, then returns the most "
        "relevant sections for your query."
    )
    args_schema: Type[BaseModel] = JSONSearchInput

    def _run(self, query: str, json_path: str) -> str:
        # Validate path
        json_path = os.path.expanduser(json_path)
        if not os.path.isabs(json_path):
            json_path = os.path.abspath(json_path)

        error = validate_path_in_sandbox(json_path)
        if error:
            return self._error(error)

        if not os.path.exists(json_path):
            return self._error(f"File not found: {json_path}")
        if not json_path.lower().endswith(".json"):
            return self._error(f"Not a JSON file: {json_path}")

        try:
            from crewai_tools import JSONSearchTool
        except ImportError:
            return self._error(
                "crewai_tools not installed. Run: pip install crewai-tools"
            )

        from backend.tools.web.crewai_tool_config import build_crewai_tools_config

        config = build_crewai_tools_config()

        try:
            tool = JSONSearchTool(json_path=json_path, config=config)
            result = tool.run(search_query=query)
        except Exception as e:
            return self._error(f"JSON search failed: {e}")

        if not result:
            return self._error(f"No results found for: {query}")

        self._log_tool_usage(
            f"JSON search in {os.path.basename(json_path)}: '{query[:50]}'"
        )
        return self._success({
            "query": query,
            "json_path": json_path,
            "result": result,
        })
