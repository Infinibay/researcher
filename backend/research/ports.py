"""Acquisition ports owned by the research use cases."""

from typing import Protocol

from backend.research.models import ReferenceRecord, ResearchScope, SourceDraft


class ResearchRepository(Protocol):
    def lookup_operation(
        self, scope: ResearchScope, key: str, kind: str, intent: dict
    ) -> dict | None: ...
    def get_reference(
        self, scope: ResearchScope, reference_id: int
    ) -> ReferenceRecord: ...
    def capture_source(
        self, scope: ResearchScope, key: str, draft: SourceDraft, *, intent: dict
    ) -> dict: ...


class ReferenceReader(Protocol):
    def read(self, reference: ReferenceRecord) -> SourceDraft: ...


class WebFetcher(Protocol):
    def fetch(self, url: str) -> SourceDraft: ...
