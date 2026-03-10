"""Tool for semantic search within Word (.docx) documents."""

import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.rag.base import validate_path_in_sandbox

logger = logging.getLogger(__name__)


class DOCXSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    docx_path: str = Field(..., description="Absolute path to the .docx file")


class DOCXSearchInfinibayTool(InfinibayBaseTool):
    name: str = "docx_search"
    description: str = (
        "Search within Word (.docx) documents using semantic RAG. "
        "Embeds and indexes the document content, then returns the most "
        "relevant passages for your query."
    )
    args_schema: Type[BaseModel] = DOCXSearchInput

    def _run(self, query: str, docx_path: str) -> str:
        # Validate path
        docx_path = os.path.expanduser(docx_path)
        if not os.path.isabs(docx_path):
            docx_path = os.path.abspath(docx_path)

        error = validate_path_in_sandbox(docx_path)
        if error:
            return self._error(error)

        if not os.path.exists(docx_path):
            return self._error(f"File not found: {docx_path}")
        if not docx_path.lower().endswith(".docx"):
            return self._error(f"Not a DOCX file: {docx_path}")

        try:
            from crewai_tools import DOCXSearchTool
        except ImportError:
            return self._error(
                "crewai_tools not installed. Run: pip install crewai-tools"
            )

        from backend.tools.web.crewai_tool_config import build_crewai_tools_config

        config = build_crewai_tools_config()

        try:
            tool = DOCXSearchTool(docx=docx_path, config=config)
            result = tool.run(search_query=query)
        except Exception as e:
            return self._error(f"DOCX search failed: {e}")

        if not result:
            return self._error(f"No results found for: {query}")

        self._log_tool_usage(
            f"DOCX search in {os.path.basename(docx_path)}: '{query[:50]}'"
        )
        return self._success({
            "query": query,
            "docx_path": docx_path,
            "result": result,
        })
