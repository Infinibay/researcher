"""Tool for reading academic papers from arXiv, DOI, or PDF URLs."""

import asyncio
import os
import re
import tempfile
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.web.rate_limiter import web_rate_limiter
from backend.tools.web.robots_checker import robots_checker


class ReadPaperInput(BaseModel):
    url: str | None = Field(default=None, description="Direct URL to the paper (PDF or HTML)")
    doi: str | None = Field(default=None, description="DOI identifier (e.g. '10.1234/example')")
    arxiv_id: str | None = Field(default=None, description="arXiv paper ID (e.g. '2301.07041')")


class ReadPaperTool(PabadaBaseTool):
    name: str = "read_paper"
    description: str = (
        "Read an academic paper from arXiv, DOI, or a PDF URL. "
        "Extracts and returns the text content."
    )
    args_schema: Type[BaseModel] = ReadPaperInput

    def _run(
        self,
        url: str | None = None,
        doi: str | None = None,
        arxiv_id: str | None = None,
    ) -> str:
        if not any([url, doi, arxiv_id]):
            return self._error("Provide at least one of: url, doi, or arxiv_id")

        # Resolve to a PDF URL
        pdf_url = self._resolve_url(url, doi, arxiv_id)
        if pdf_url.startswith('{"error"'):
            return pdf_url

        # Check robots.txt
        if not robots_checker.is_allowed(pdf_url, "PabadaBot/2.0"):
            return self._error("robots.txt disallows fetching this URL")

        # Rate limit
        web_rate_limiter.acquire()

        try:
            import httpx
        except ImportError:
            return self._error("httpx not installed. Run: pip install httpx")

        # Download PDF
        try:
            with httpx.Client(
                timeout=settings.WEB_TIMEOUT * 2,  # Papers can be large
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PabadaBot/2.0)"},
            ) as client:
                response = client.get(pdf_url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
        except Exception as e:
            return self._error(f"Failed to download paper: {e}")

        # If HTML, use trafilatura
        if "html" in content_type:
            try:
                import trafilatura
                text = trafilatura.extract(
                    response.text,
                    output_format="markdown",
                    include_links=True,
                    include_tables=True,
                )
                if text:
                    self._log_tool_usage(f"Read paper from {pdf_url}")
                    return text
            except Exception:
                pass

        # If PDF, extract text
        if "pdf" in content_type or pdf_url.endswith(".pdf"):
            return self._extract_pdf(response.content, pdf_url)

        # Fallback: return raw text
        return response.text[:50000]

    def _resolve_url(
        self, url: str | None, doi: str | None, arxiv_id: str | None
    ) -> str:
        """Resolve identifier to a fetchable URL."""
        if arxiv_id:
            # Clean up arXiv ID
            arxiv_id = arxiv_id.strip()
            if arxiv_id.startswith("arXiv:"):
                arxiv_id = arxiv_id[6:]
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        if doi:
            doi = doi.strip()
            return f"https://doi.org/{doi}"

        if url:
            return url

        return self._error("No URL could be resolved")

    def _extract_pdf(self, pdf_bytes: bytes, source: str) -> str:
        """Extract text from PDF bytes."""
        try:
            from pypdf import PdfReader
        except ImportError:
            return self._error("pypdf not installed. Run: pip install pypdf")

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            reader = PdfReader(tmp_path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)

            os.unlink(tmp_path)
        except Exception as e:
            return self._error(f"PDF extraction failed: {e}")

        if not pages:
            return self._error("No text could be extracted from PDF")

        full_text = "\n\n---\n\n".join(pages)
        self._log_tool_usage(
            f"Read paper from {source} ({len(pages)} pages, {len(full_text)} chars)"
        )
        return full_text

    async def _arun(
        self,
        url: str | None = None,
        doi: str | None = None,
        arxiv_id: str | None = None,
    ) -> str:
        """Async version."""
        return await asyncio.to_thread(self._run, url, doi, arxiv_id)
