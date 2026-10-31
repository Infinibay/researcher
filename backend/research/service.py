"""Acquire evidence once, then revalidate authority when committing it."""

from backend.research.models import ResearchScope, SourceUnavailable, positive_id
from backend.research.ports import ReferenceReader, ResearchRepository, WebFetcher


class ResearchService:
    def __init__(
        self,
        repository: ResearchRepository,
        *,
        reference_reader: ReferenceReader,
        web_fetcher: WebFetcher | None = None,
    ):
        self.repository = repository
        self.reference_reader = reference_reader
        self.web_fetcher = web_fetcher

    def capture_reference(
        self, scope: ResearchScope, key: str, reference_id: int
    ) -> dict:
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
        intent = {"url": url}
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
        return self.repository.capture_source(scope, key, snapshot, intent=intent)
