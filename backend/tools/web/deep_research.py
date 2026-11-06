"""Retired outside-runtime deep-research entry; actual native research owns discovery, captured sources, cited findings and report synthesis."""

import json
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool


class DeepWebResearchInput(BaseModel):
    """Historical query fields identify an old request; they do not grant network or model authority."""

    query: str = Field(..., description="Historical research question")
    num_search_results: int = Field(default=10, ge=3, le=20)
    max_sources: int = Field(default=5, ge=1, le=10)


class DeepWebResearchTool(InfinibayBaseTool):
    """Return the actual scoped owner entry before web search, fetching or synthesis; no hint is represented as completed research."""

    name: str = "deep_web_research"
    description: str = "Retired entry: open the native task workspace for explicitly admitted research with captured sources and reports. This tool does not search or synthesize."
    args_schema: Type[BaseModel] = DeepWebResearchInput

    def _run(self, query: str, num_search_results: int = 10, max_sources: int = 5) -> str:
        """Resolve the explicit old project scope without adopting the query as a new native command or spending a provider call."""
        from backend.runtime.legacy_handoff import legacy_project_handoff

        return json.dumps(legacy_project_handoff(self.project_id))

    async def _arun(self, query: str, num_search_results: int = 10, max_sources: int = 5) -> str:
        """Return the same owner hint without starting background web jobs, model requests or an independent synthesis loop."""
        return self._run(query, num_search_results, max_sources)
