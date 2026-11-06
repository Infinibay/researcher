"""Acquire evidence once, then revalidate authority when committing it."""

from dataclasses import replace

from backend.research.models import ResearchScope, SourceUnavailable, positive_id
from backend.research.papers import resolve_paper
from backend.research.ports import ReferenceReader, ResearchRepository, WebFetcher


class ResearchService:
    """Coordinate scoped acquisition and receipt reuse, revalidating authority at commit."""

    def __init__(
        self,
        repository: ResearchRepository,
        *,
        reference_reader: ReferenceReader,
        web_fetcher: WebFetcher | None = None,
        context7=None,
        spider=None,
    ):
        """Bind persistence and bounded readers without acquiring data at construction."""
        self.repository = repository
        self.reference_reader = reference_reader
        self.web_fetcher = web_fetcher
        self.context7 = context7
        self.spider = spider

    def capture_spider(self, scope, key, url, *, mode="smart", format="markdown"):
        """Capture an explicitly selected advanced scraper with receipt reuse and authority revalidation at commit."""
        from backend.research.spider import validate_spider

        validate_spider(url, mode=mode, format=format)
        intent = {"provider": "spider", "url": url, "mode": mode, "format": format}
        existing = self.repository.lookup_operation(scope, key, "source.capture", intent)
        if existing is not None:
            return existing
        if self.spider is None:
            raise SourceUnavailable("Spider is not configured")
        snapshot = self.spider.fetch(url, mode=mode, format=format)
        return self.repository.capture_source(scope, key, snapshot, intent=intent)

    def capture_context7(self, scope, key, *, operation, query, library_name=None,
                         library_id=None, format="json"):
        """Capture one explicit provider lookup with scoped receipt reuse and commit-time authority checks.

        A saved receipt avoids another external request. Concurrent or interrupted
        requests before commit may still consume provider quota; no retry is automatic.
        """
        from backend.research.context7 import validate_context7

        validate_context7(query=query, library_name=library_name, library_id=library_id, format=format)
        if operation == "search" and library_name is not None and library_id is None:
            request = {"library_name": library_name, "query": query}
        elif operation == "docs" and library_id is not None and library_name is None:
            request = {"library_id": library_id, "query": query, "format": format}
        else:
            raise SourceUnavailable("Unsupported Context7 operation")
        intent = {"provider": "context7", "operation": operation, **request}
        existing = self.repository.lookup_operation(scope, key, "source.capture", intent)
        if existing is not None:
            return existing
        if self.context7 is None:
            raise SourceUnavailable("Context7 is not configured")
        snapshot = getattr(self.context7, operation)(**request)
        return self.repository.capture_source(scope, key, snapshot, intent=intent)

    def capture_reference(
        self, scope: ResearchScope, key: str, reference_id: int
    ) -> dict:
        """Capture an attachment once; a committed retry does not reopen its original bytes."""
        positive_id(reference_id)
        intent = {"reference_file_id": reference_id}
        existing = self.repository.lookup_operation(
            scope, key, "source.capture", intent
        )
        if existing is not None:
            return existing
        reference = self.repository.get_reference(scope, reference_id)
        snapshot = self.reference_reader.read(reference)
        if snapshot.kind != "attachment":
            raise SourceUnavailable("Reference reader returned an invalid source kind")
        return self.repository.capture_source(scope, key, snapshot, intent=intent)

    def capture_web(self, scope: ResearchScope, key: str, url: str) -> dict:
        """Capture a public URL once, preserving its original requested intent on retry."""
        return self._capture_remote(scope, key, url, intent={"url": url})

    def capture_paper(
        self, scope: ResearchScope, key: str, *, url=None, doi=None, arxiv_id=None
    ) -> dict:
        """Capture one paper locator through the same vetted web/PDF acquisition boundary.

        A DOI can resolve to HTML instead of full text. Provenance records what was
        requested, not verified publication metadata or scientific acceptance.
        """
        locator = resolve_paper(url=url, doi=doi, arxiv_id=arxiv_id)
        paper = locator.provenance()
        return self._capture_remote(
            scope,
            key,
            locator.url,
            intent={"paper_request": paper},
            paper_request=paper,
        )

    def _capture_remote(self, scope, key, url, *, intent, paper_request=None):
        """Share receipt lookup, bounded acquisition and authority-checked commit for remote sources."""
        existing = self.repository.lookup_operation(
            scope, key, "source.capture", intent
        )
        if existing is not None:
            return existing
        if self.web_fetcher is None:
            raise SourceUnavailable("Web acquisition is not configured")
        snapshot = self.web_fetcher.fetch(url)
        if snapshot.kind != "web":
            raise SourceUnavailable("Web fetcher returned an invalid source kind")
        if paper_request is not None:
            snapshot = replace(
                snapshot,
                provenance={**snapshot.provenance, "paper_request": paper_request},
            )
        return self.repository.capture_source(scope, key, snapshot, intent=intent)
