"""Mutable findings are inspected through current scoped readers, not unversioned vector injection."""

import pytest

from backend.knowledge.service import KnowledgeService
from backend.knowledge.sources import FindingsKnowledgeSource


@pytest.mark.parametrize(
    "role", ["researcher", "research_reviewer", "team_lead", "project_lead"]
)
def test_role_context_does_not_select_mutable_finding_vector_sources(role):
    """Retained roles use current finding tools instead of selecting a stale source collection."""
    assert not any(
        isinstance(source, FindingsKnowledgeSource)
        for source in KnowledgeService.get_sources_for_role(role, 101)
    )


def test_project_source_builder_leaves_findings_to_scoped_readers():
    """Project context enumeration cannot silently opt back into the retired mutable index."""
    assert not any(
        isinstance(source, FindingsKnowledgeSource)
        for source in KnowledgeService.get_sources_for_project(101)
    )


@pytest.mark.parametrize("method", ["load_content", "add"])
def test_direct_legacy_finding_index_call_fails_before_loading_or_embedding(
    monkeypatch, method
):
    """An obsolete direct caller gets a migration error rather than stale context or false emptiness."""
    from backend.knowledge import sources

    calls = []

    def forbidden(*args, **kwargs):
        """Record any attempt to enter the old database/index-building path."""
        calls.append(True)
        raise AssertionError("Retired finding index must not read or embed")

    monkeypatch.setattr(sources, "execute_with_retry", forbidden)
    source = FindingsKnowledgeSource(project_id=101)
    with pytest.raises(RuntimeError, match="read_findings"):
        getattr(source, method)()
    assert calls == []
