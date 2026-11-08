"""Acquisition ports owned by the research use cases."""

from typing import Protocol

from backend.research.models import ReferenceRecord, ResearchScope, SourceDraft


class ResearchRepository(Protocol):
    """Define scoped operation reconciliation, reference lookup and captured-source persistence for acquisition."""
    def lookup_operation(
        self, scope: ResearchScope, key: str, kind: str, intent: dict
    ) -> dict | None:
        """Look up an exact prior intent receipt in the supplied scope instead of repeating its effect."""
        ...
    def get_reference(
        self, scope: ResearchScope, reference_id: int
    ) -> ReferenceRecord:
        """Resolve an uploaded reference within the caller scope before reading its bytes."""
        ...
    def capture_source(
        self, scope: ResearchScope, key: str, draft: SourceDraft, *, intent: dict
    ) -> dict:
        """Persist an acquired source and its operation receipt under the original key and intent."""
        ...


class ReferenceReader(Protocol):
    """Convert an already resolved upload into a source draft independently of database persistence."""
    def read(self, reference: ReferenceRecord) -> SourceDraft:
        """Read the supplied reference and return its captured content and provenance as a draft."""
        ...


class WebFetcher(Protocol):
    """Acquire a source draft from a URL independently of the persistence adapter."""
    def fetch(self, url: str) -> SourceDraft:
        """Fetch the requested source and return captured content and acquisition provenance."""
        ...
