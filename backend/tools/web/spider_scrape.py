"""Advanced web scraping tool using Spider service (for JS-heavy sites)."""

import asyncio
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.web.rate_limiter import web_rate_limiter


class SpiderScrapeInput(BaseModel):
    url: str = Field(..., description="URL to scrape")
    store_as_finding: bool = Field(
        default=False,
        description="If True, stores the scraped content as a finding for RAG retrieval",
    )
    topic: str = Field(
        default="",
        description="Topic/title for the finding (used when store_as_finding=True)",
    )


class SpiderScrapeTool(PabadaBaseTool):
    name: str = "spider_scrape"
    description: str = (
        "Advanced web scraping for JS-heavy or anti-bot protected sites using "
        "Spider service. Requires SPIDER_API_KEY to be configured. Use this "
        "when regular scraping fails on dynamic websites."
    )
    args_schema: Type[BaseModel] = SpiderScrapeInput

    def _run(
        self,
        url: str,
        store_as_finding: bool = False,
        topic: str = "",
    ) -> str:
        if not settings.SPIDER_API_KEY:
            return self._error(
                "SPIDER_API_KEY is not configured. "
                "Set PABADA_SPIDER_API_KEY in your environment."
            )

        try:
            from crewai_tools import SpiderTool
        except ImportError:
            return self._error(
                "crewai_tools or spider-client not installed. "
                "Run: pip install crewai-tools spider-client"
            )

        web_rate_limiter.acquire()

        try:
            tool = SpiderTool()
            result = tool.run(url=url)
        except Exception as e:
            return self._error(f"Spider scrape failed: {e}")

        if not result or not isinstance(result, str) or not result.strip():
            return self._error(f"No content scraped from {url}")

        content = result.strip()
        output: dict = {"content": content, "url": url}

        # Optionally store as finding
        if store_as_finding:
            from backend.tools.web.knowledge_ingest import store_scraped_content_as_finding

            finding_id = store_scraped_content_as_finding(
                project_id=self.project_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                agent_run_id=self.agent_run_id,
                url=url,
                content=content,
                topic=topic,
            )
            if finding_id:
                output["stored_as_finding_id"] = finding_id

        self._log_tool_usage(f"Spider scraped {url} ({len(content)} chars)")
        return self._success(output)

    async def _arun(
        self,
        url: str,
        store_as_finding: bool = False,
        topic: str = "",
    ) -> str:
        return await asyncio.to_thread(self._run, url, store_as_finding, topic)
