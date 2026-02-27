"""Web scraping tool using CrewAI's ScrapeWebsiteTool."""

import asyncio
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.web.rate_limiter import web_rate_limiter
from backend.tools.web.robots_checker import robots_checker


class ScrapeWebsiteInput(BaseModel):
    url: str = Field(..., description="URL to scrape content from")
    store_as_finding: bool = Field(
        default=False,
        description="If True, stores the scraped content as a finding for RAG retrieval",
    )
    topic: str = Field(
        default="",
        description="Topic/title for the finding (used when store_as_finding=True)",
    )


class ScrapeWebsitePabadaTool(PabadaBaseTool):
    name: str = "scrape_website"
    description: str = (
        "Scrape and extract content from a website. Returns clean text/markdown. "
        "Optionally stores the scraped content as a finding for RAG retrieval."
    )
    args_schema: Type[BaseModel] = ScrapeWebsiteInput

    def _run(
        self,
        url: str,
        store_as_finding: bool = False,
        topic: str = "",
    ) -> str:
        # Check robots.txt
        if not robots_checker.is_allowed(url, "PabadaBot/2.0"):
            return self._error("robots.txt disallows scraping this URL")

        # Rate limit
        web_rate_limiter.acquire()

        # Scrape using CrewAI tool
        from backend.tools.web._backends import scrape_with_crewai

        content = scrape_with_crewai(url)
        if not content:
            return self._error(f"Failed to scrape content from {url}")

        result: dict = {"content": content, "url": url}

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
                result["stored_as_finding_id"] = finding_id

        self._log_tool_usage(f"Scraped {url} ({len(content)} chars)")
        return self._success(result)

    async def _arun(
        self,
        url: str,
        store_as_finding: bool = False,
        topic: str = "",
    ) -> str:
        return await asyncio.to_thread(self._run, url, store_as_finding, topic)
