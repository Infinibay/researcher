"""A bounded wiki corpus reuses exact source citations and existing offline semantic recovery."""

import pytest


def wiki_scope(store):
    """Issue explicit fixture permissions; old grants do not acquire new wiki rights implicitly."""
    from backend.research.models import PERMISSIONS

    return store.authorize(
        store.issue_grant(
            project_id=101,
            task_id=1001,
            agent_id="fixture",
            permissions=set(PERMISSIONS),
        )
    )


def wiki_page(store, path, content, project=101):
    """Create one synthetic owner page through the same revision/receipt adapter as the product."""
    from backend.knowledge.wiki import WikiStore

    receipt = WikiStore(store.database).write(
        project_id=project,
        namespace="project",
        path=path,
        title=path,
        content=content,
        actor="fixture",
        operation_key="fixture-" + path,
        expected_revision=0,
    )
    return {
        "page_id": receipt["page_id"],
        "revision": receipt["revision"],
        "namespace": "project",
    }


def test_wiki_collection_preserves_every_requested_revision_with_structural_offsets(
    research_store,
):
    """Keep late counterevidence and historical versions without silently sampling a corpus."""
    from backend.knowledge.wiki import WikiStore

    scope = wiki_scope(research_store)
    first = wiki_page(research_store, "background", "General background. " * 800)
    last = wiki_page(
        research_store, "counterevidence", "No improvement in the control group."
    )
    wiki = WikiStore(research_store.database)
    wiki.write(
        project_id=101,
        namespace="project",
        path="counterevidence",
        title="counterevidence",
        content="A later changed statement.",
        actor="fixture",
        operation_key="edit",
        expected_revision=1,
        page_id=last["page_id"],
    )
    captured = research_store.capture_wiki_collection(
        scope, "collection", members=[first, last]
    )
    source = research_store.read_source(scope, captured["source_id"])
    assert (
        source["kind"] == "wiki"
        and source["provenance"]["collection_member_count"] == 2
    )
    assert source["content"].index("No improvement") > 12000
    assert "A later changed statement" not in source["content"]
    units = source["provenance"]["units"]
    assert len(units) == 2
    assert (
        units[-1]["wiki_page_id"] == last["page_id"] and units[-1]["wiki_revision"] == 1
    )
    assert (
        source["content"][units[-1]["start_offset"] : units[-1]["end_offset"]]
        == "No improvement in the control group."
    )
    assert (
        research_store.capture_wiki_collection(
            scope, "collection", members=[first, last]
        )
        == captured
    )


def test_wiki_collection_rejects_foreign_duplicate_and_over_limit_members(
    research_store,
):
    """A collection is all requested authorized members or explicit failure, never a partial capture."""
    from backend.research.models import (
        ResearchInputError,
        ResearchNotFound,
        SourceTooLarge,
    )

    scope = wiki_scope(research_store)
    own = wiki_page(research_store, "own", "Context. " * 14000)
    foreign = wiki_page(research_store, "foreign", "Private.", project=202)
    with pytest.raises(ResearchNotFound):
        research_store.capture_wiki_collection(scope, "foreign", members=[own, foreign])
    with pytest.raises(ResearchInputError):
        research_store.capture_wiki_collection(scope, "duplicate", members=[own, own])
    other = wiki_page(research_store, "other", "Other context. " * 8000)
    with pytest.raises(SourceTooLarge):
        research_store.capture_wiki_collection(scope, "oversize", members=[own, other])
    with research_store._transaction() as conn:
        assert conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0
