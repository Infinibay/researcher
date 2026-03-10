"""Deep web research tool — searches, fetches top sources, and synthesizes via LLM."""

import asyncio
import json
import math
import re
from collections import Counter
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.web.rate_limiter import web_rate_limiter
from backend.tools.web.robots_checker import robots_checker

_CONTENT_LIMIT = 3000  # max chars per source sent to the LLM
_MIN_CONTENT_LENGTH = 200  # minimum extracted chars to consider a source usable


class DeepWebResearchInput(BaseModel):
    query: str = Field(..., description="Research question")
    num_search_results: int = Field(
        default=10, ge=3, le=20, description="URLs to retrieve from search"
    )
    max_sources: int = Field(
        default=5, ge=1, le=10, description="Sources to read and synthesize"
    )


class DeepWebResearchTool(InfinibayBaseTool):
    name: str = "deep_web_research"
    description: str = (
        "Conduct deep web research on a query. Searches the web, reads the best "
        "sources, and returns a synthesized research summary with references. "
        "Use this for in-depth investigation. For quick lookups, use web_search."
    )
    args_schema: Type[BaseModel] = DeepWebResearchInput

    # ── Private helpers ───────────────────────────────────────────────

    def _search(self, query: str, num_results: int) -> list[dict]:
        """Search the web via unified backend (Serper → DDG fallback)."""
        from backend.tools.web._backends import unified_search

        return unified_search(query, num_results)

    def _fetch_content(self, url: str, title: str) -> dict | None:
        """Fetch and extract readable text from a single URL (sync)."""
        if not robots_checker.is_allowed(url, "InfinibayBot/2.0"):
            return None

        web_rate_limiter.acquire()

        from backend.tools.web._backends import fetch_with_trafilatura

        content = fetch_with_trafilatura(url, timeout=settings.WEB_TIMEOUT)

        if not content or len(content) < _MIN_CONTENT_LENGTH:
            return None

        return {"title": title, "url": url, "content": content}

    async def _fetch_content_async(self, url: str, title: str) -> dict | None:
        """Fetch and extract readable text from a single URL (async)."""
        try:
            import httpx
            import trafilatura
        except ImportError:
            return None

        if not await robots_checker.is_allowed_async(url, "InfinibayBot/2.0"):
            return None

        await web_rate_limiter.acquire_async()

        try:
            async with httpx.AsyncClient(
                timeout=settings.WEB_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; InfinibayBot/2.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except Exception:
            return None

        try:
            content = await asyncio.to_thread(
                trafilatura.extract, html, output_format="txt", favor_recall=True
            )
        except Exception:
            return None

        if not content or len(content) < _MIN_CONTENT_LENGTH:
            return None

        return {"title": title, "url": url, "content": content}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase split into alphanumeric tokens."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def _relevance_score(self, query: str, source: dict) -> float:
        """Score a source's relevance to *query* via TF-IDF-style keyword matching.

        Considers both the full content and the title. Returns a float in
        [0, 1] where higher means more relevant.
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.0

        # Build a combined text from title (weighted higher) and content
        title_tokens = self._tokenize(source.get("title", ""))
        content_tokens = self._tokenize(source["content"][:_CONTENT_LIMIT])

        if not content_tokens and not title_tokens:
            return 0.0

        # Term frequencies in combined document (title counted 3x for emphasis)
        doc_tokens = title_tokens * 3 + content_tokens
        doc_freq = Counter(doc_tokens)
        doc_len = len(doc_tokens)

        # Score: for each query term, compute its normalized frequency in the doc.
        # Use sub-linear TF (1 + log(tf)) to avoid long documents dominating
        # purely from repetition.
        score = 0.0
        query_term_set = set(query_tokens)
        for term in query_term_set:
            tf = doc_freq.get(term, 0)
            if tf > 0:
                score += 1.0 + math.log(tf)

        # Normalize by the number of unique query terms so score ∈ [0, ~1]
        max_possible = len(query_term_set) * (1.0 + math.log(doc_len)) if doc_len else 1.0
        return min(score / max_possible, 1.0) if max_possible > 0 else 0.0

    def _select_best_sources(
        self, query: str, sources: list[dict], max_sources: int
    ) -> list[dict]:
        """Return the top sources ranked by relevance to *query*, then by length."""
        for src in sources:
            src["_relevance"] = self._relevance_score(query, src)

        sources.sort(
            key=lambda s: (s["_relevance"], len(s["content"])),
            reverse=True,
        )

        # Strip transient scoring key before returning
        selected = sources[:max_sources]
        for src in selected:
            src.pop("_relevance", None)
        return selected

    def _build_synthesis_prompt(self, query: str, sources: list[dict]) -> str:
        """Build the LLM prompt for research synthesis."""
        source_blocks = []
        for i, src in enumerate(sources, 1):
            truncated = src["content"][:_CONTENT_LIMIT]
            source_blocks.append(f"[{i}] {src['title']} | {src['url']}\n{truncated}")

        sources_text = "\n\n".join(source_blocks)

        return (
            "You are a research synthesizer. Analyze the provided web sources "
            "and answer the research query.\n\n"
            f"RESEARCH QUERY: {query}\n\n"
            f"SOURCES ({len(sources)} total):\n{sources_text}\n\n"
            "TASK:\n"
            "Produce a JSON object with this exact structure:\n"
            "{\n"
            '  "synthesis": "<3+ paragraph research summary that directly answers the query. '
            "Cite sources inline as [1], [2], etc. Note contradictions between sources if any. "
            'State what evidence is missing if sources are insufficient.>",\n'
            '  "key_findings": ["<concise finding 1>", "<concise finding 2>", ...],\n'
            '  "references": [\n'
            '    {"index": 1, "title": "<source title>", "url": "<source url>", '
            '"excerpt": "<most relevant quote, max 200 chars>"},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            "RULES:\n"
            "- Output ONLY the JSON object. No markdown fences, no preamble, no explanation.\n"
            "- Use only information from the provided sources. Do not hallucinate facts.\n"
            "- Every claim in synthesis must be traceable to a cited source index.\n"
            "- If a source is not useful for the query, omit it from references."
        )

    # ── Public interface ──────────────────────────────────────────────

    def _run(
        self,
        query: str,
        num_search_results: int = 10,
        max_sources: int = 5,
    ) -> str:
        # 1. Search
        results = self._search(query, num_search_results)
        if not results:
            return self._error(f"No search results found for: {query}")

        # 2. Fetch content from each URL
        sources = []
        for result in results:
            fetched = self._fetch_content(result["url"], result["title"])
            if fetched:
                sources.append(fetched)

        if not sources:
            return self._error(f"No accessible sources found for: {query}")

        # 3. Select best sources
        best = self._select_best_sources(query, sources, max_sources)

        # 4. Build prompt and call LLM
        prompt = self._build_synthesis_prompt(query, best)

        try:
            import litellm
            from backend.config.llm import get_litellm_params

            llm_params = get_litellm_params()
            if llm_params is None:
                return self._error(
                    "No LLM configured for synthesis. "
                    "Ensure INFINIBAY_LLM_MODEL is set. Use WebSearch + manual analysis."
                )
            response = litellm.completion(
                **llm_params,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
        except Exception as e:
            return self._error(f"LLM synthesis failed: {e}")

        # 5. Parse response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"synthesis": raw, "key_findings": [], "references": []}

        data["sources_checked"] = len(results)
        data["sources_used"] = len(best)

        self._log_tool_usage(
            f"Deep research: '{query[:60]}' — {len(best)}/{len(results)} sources used"
        )
        return self._success(data)

    async def _arun(
        self,
        query: str,
        num_search_results: int = 10,
        max_sources: int = 5,
    ) -> str:
        """Async version with concurrent fetches."""
        # 1. Search (DDGS is sync, run in thread)
        results = await asyncio.to_thread(self._search, query, num_search_results)
        if not results:
            return self._error(f"No search results found for: {query}")

        # 2. Fetch content concurrently
        tasks = [
            self._fetch_content_async(r["url"], r["title"]) for r in results
        ]
        fetched_list = await asyncio.gather(*tasks, return_exceptions=True)
        sources = [f for f in fetched_list if isinstance(f, dict)]

        if not sources:
            return self._error(f"No accessible sources found for: {query}")

        # 3. Select best sources
        best = self._select_best_sources(query, sources, max_sources)

        # 4. Build prompt and call LLM (async)
        prompt = self._build_synthesis_prompt(query, best)

        try:
            import litellm
            from backend.config.llm import get_litellm_params

            llm_params = get_litellm_params()
            if llm_params is None:
                return self._error(
                    "No LLM configured for synthesis. "
                    "Ensure INFINIBAY_LLM_MODEL is set. Use WebSearch + manual analysis."
                )
            response = await litellm.acompletion(
                **llm_params,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
        except Exception as e:
            return self._error(f"LLM synthesis failed: {e}")

        # 5. Parse response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"synthesis": raw, "key_findings": [], "references": []}

        data["sources_checked"] = len(results)
        data["sources_used"] = len(best)

        self._log_tool_usage(
            f"Deep research: '{query[:60]}' — {len(best)}/{len(results)} sources used"
        )
        return self._success(data)
