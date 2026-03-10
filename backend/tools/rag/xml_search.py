"""Tool for semantic search within XML files."""

import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.rag.base import validate_path_in_sandbox

logger = logging.getLogger(__name__)


class XMLSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    xml_path: str = Field(..., description="Absolute path to the XML file")


class XMLSearchInfinibayTool(InfinibayBaseTool):
    name: str = "xml_search"
    description: str = (
        "Search within XML files using semantic RAG. "
        "Embeds and indexes the XML content, then returns the most "
        "relevant sections for your query."
    )
    args_schema: Type[BaseModel] = XMLSearchInput

    def _run(self, query: str, xml_path: str) -> str:
        # Validate path
        xml_path = os.path.expanduser(xml_path)
        if not os.path.isabs(xml_path):
            xml_path = os.path.abspath(xml_path)

        error = validate_path_in_sandbox(xml_path)
        if error:
            return self._error(error)

        if not os.path.exists(xml_path):
            return self._error(f"File not found: {xml_path}")
        if not xml_path.lower().endswith(".xml"):
            return self._error(f"Not an XML file: {xml_path}")

        try:
            from crewai_tools import XMLSearchTool
        except ImportError:
            return self._error(
                "crewai_tools not installed. Run: pip install crewai-tools"
            )

        from backend.tools.web.crewai_tool_config import build_crewai_tools_config

        config = build_crewai_tools_config()

        try:
            tool = XMLSearchTool(xml_path=xml_path, config=config)
            result = tool.run(search_query=query)
        except Exception as e:
            return self._error(f"XML search failed: {e}")

        if not result:
            return self._error(f"No results found for: {query}")

        self._log_tool_usage(
            f"XML search in {os.path.basename(xml_path)}: '{query[:50]}'"
        )
        return self._success({
            "query": query,
            "xml_path": xml_path,
            "result": result,
        })
