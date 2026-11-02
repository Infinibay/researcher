"""Wiki identity separates project/global pages and keeps corrections recoverable."""

import sqlite3

import pytest

from backend.tests.research.test_http import credentials
from backend.tests.research.test_http import research_client as client_fixture

research_client = client_fixture


def test_wiki_namespace_allows_same_path_in_two_projects_and_global(
    research_store, db_conn
):
    """Catch the old global UNIQUE(path), which makes one project's page block another."""
    for project in (101, 202, None):
        db_conn.execute(
            "INSERT INTO wiki_pages(project_id,path,title,content) VALUES(?,?,?,?)",
            (project, "architecture/overview", "Overview", str(project)),
        )
    db_conn.commit()
    assert (
        db_conn.execute(
            "SELECT count(*) FROM wiki_pages WHERE path=?", ("architecture/overview",)
        ).fetchone()[0]
        == 3
    )
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO wiki_pages(project_id,path,title,content) VALUES(NULL,?,?,?)",
            ("architecture/overview", "Duplicate", "must fail"),
        )


def test_project_wiki_never_selects_or_changes_a_global_page_implicitly(
    research_client, research_store, db_conn
):
    """A project lookup/write/delete cannot silently turn into a global document operation."""
    from backend.knowledge.wiki import WikiStore

    receipt = WikiStore(research_store.database).write(
        project_id=101,
        namespace="global",
        path="shared",
        title="Global",
        content="Original global text",
        actor="owner",
        operation_key="global-create",
        expected_revision=0,
    )
    page_id = receipt["page_id"]
    path = "/api/wiki/shared?project_id=101"
    assert research_client.get(path).status_code == 404
    assert (
        research_client.put(
            path,
            json={
                "title": "Global",
                "page_id": page_id,
                "content": "Wrong scope",
                "expected_revision": 1,
                "operation_key": "bad-edit",
            },
        ).status_code
        == 404
    )
    assert (
        research_client.delete(
            path + f"&expected_revision=1&page_id={page_id}&operation_key=bad-delete"
        ).status_code
        == 404
    )
    assert (
        db_conn.execute(
            "SELECT content FROM wiki_pages WHERE path='shared'"
        ).fetchone()[0]
        == "Original global text"
    )
    response = research_client.get(path + "&namespace=global")
    assert response.status_code == 200, response.text
    assert response.json()["namespace"] == "global"


def test_wiki_cas_and_lost_receipt_preserve_versions_without_silent_rebase(
    research_store,
):
    """A stale editor loses no draft; retrying the original intent recovers its committed revision."""
    from backend.knowledge.wiki import WikiConflict, WikiStore

    store = WikiStore(research_store.database)
    args = {
        "project_id": 101,
        "namespace": "project",
        "path": "intro",
        "title": "Intro",
        "actor": "owner",
        "operation_key": "create",
        "expected_revision": 0,
        "content": "Version one.",
    }
    first = store.write(**args)
    assert first["revision"] == 1
    edit = {
        **args,
        "operation_key": "edit",
        "page_id": first["page_id"],
        "expected_revision": 1,
        "content": "Version two.",
    }
    second = store.write(**edit)
    assert second["revision"] == 2 and second["page_id"] == first["page_id"]
    with pytest.raises(WikiConflict):
        store.write(**{**edit, "operation_key": "stale", "content": "Stale draft."})
    third = store.write(
        **{
            **edit,
            "operation_key": "third",
            "expected_revision": 2,
            "content": "Version three.",
        }
    )
    assert third["revision"] == 3
    assert store.write(**edit) == second
    assert store.read(101, "intro", namespace="project")["content"] == "Version three."
    assert (
        store.read_revision(101, first["page_id"], 1, namespace="project")["content"]
        == "Version one."
    )
    with pytest.raises(WikiConflict):
        store.write(**{**edit, "content": "Changed intent under old key."})


def test_native_wiki_revision_becomes_an_exact_captured_source(
    research_client, research_store
):
    """Reading/editing wiki is not itself a citation; capture a named revision through the scoped API."""
    from backend.knowledge.wiki import WikiStore

    store = WikiStore(research_store.database)
    first = store.write(
        project_id=101,
        namespace="project",
        path="evidence",
        title="Evidence",
        actor="owner",
        operation_key="wiki",
        expected_revision=0,
        content="No improvement in the control group.",
    )
    headers = credentials(
        research_store,
        permissions={"wiki.read", "wiki.write", "sources.capture", "sources.read"},
    )
    response = research_client.get("/api/research-tools/wiki/evidence", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 1
    captured = research_client.post(
        "/api/research-tools/sources/wiki",
        headers=headers,
        json={
            "operation_key": "capture-wiki",
            "page_id": first["page_id"],
            "revision": 1,
            "namespace": "project",
        },
    )
    assert captured.status_code == 200, captured.text
    source = research_client.get(
        "/api/research-tools/sources/" + str(captured.json()["source_id"]),
        headers=headers,
    ).json()
    assert source["kind"] == "wiki"
    assert source["content"] == "No improvement in the control group."
    assert source["provenance"]["wiki_revision"] == 1
    foreign = research_client.get(
        "/api/research-tools/wiki/evidence",
        headers=credentials(research_store, 202, 2002, {"wiki.read"}),
    )
    assert foreign.status_code == 404


def test_recreated_wiki_path_cannot_receive_a_stale_edit_without_page_identity(
    research_store,
):
    """Deleting/recreating revision 1 must not turn an old editor into authority over a new page."""
    from backend.knowledge.wiki import WikiConflict, WikiStore
    from backend.research.models import ResearchInputError

    store = WikiStore(research_store.database)
    args = {
        "project_id": 101,
        "namespace": "project",
        "path": "reused",
        "title": "Original",
        "content": "Original document",
        "expected_revision": 0,
        "actor": "owner",
        "operation_key": "old-create",
    }
    original = store.write(**args)
    store.delete(
        101,
        "reused",
        namespace="project",
        expected_revision=1,
        actor="owner",
        operation_key="delete-old",
        page_id=original["page_id"],
    )
    store.write(
        **{
            **args,
            "title": "New document",
            "content": "New context",
            "operation_key": "new-create",
        }
    )
    with pytest.raises((WikiConflict, ResearchInputError)):
        store.write(
            **{
                **args,
                "operation_key": "stale-editor",
                "expected_revision": 1,
                "content": "Old editor draft",
            }
        )
    assert store.read(101, "reused", namespace="project")["content"] == "New context"
    assert (
        store.read_revision(101, original["page_id"], 1, namespace="project")["content"]
        == "Original document"
    )


def test_unversioned_legacy_wiki_edit_cannot_claim_an_unchanged_revision(
    research_store,
):
    """An old writer changing content outside the adapter must be detected before read/edit acceptance."""
    from backend.knowledge.wiki import WikiConflict, WikiStore

    store = WikiStore(research_store.database)
    store.write(
        project_id=101,
        namespace="project",
        path="tracked",
        title="Tracked",
        content="Saved evidence",
        expected_revision=0,
        actor="owner",
        operation_key="tracked-create",
    )
    with store.transaction(write=True) as conn:
        conn.execute(
            "UPDATE wiki_pages SET content='Unversioned change' WHERE path='tracked'"
        )
    with pytest.raises(WikiConflict):
        store.read(101, "tracked", namespace="project")


def test_wiki_edit_invalidates_legacy_vectors_instead_of_ranking_new_text_with_old_embeddings(
    research_store,
):
    """Removing hidden write-time embeddings must not retain a vector from the previous revision."""
    from backend.knowledge.wiki import WikiStore

    store = WikiStore(research_store.database)
    first = store.write(
        project_id=101,
        namespace="project",
        path="vectors",
        title="Vectors",
        content="Original",
        expected_revision=0,
        actor="owner",
        operation_key="vectors-create",
    )
    with store.transaction(write=True) as conn:
        conn.execute(
            "UPDATE wiki_pages SET embedding=? WHERE id=?",
            (b"stale-vector", first["page_id"]),
        )
    store.write(
        project_id=101,
        namespace="project",
        path="vectors",
        title="Vectors",
        content="Changed",
        expected_revision=1,
        page_id=first["page_id"],
        actor="owner",
        operation_key="vectors-edit",
    )
    with store.transaction() as conn:
        assert (
            conn.execute(
                "SELECT embedding FROM wiki_pages WHERE id=?", (first["page_id"],)
            ).fetchone()[0]
            is None
        )


def test_legacy_wiki_context_keeps_colliding_scope_identity_visible(research_store):
    """The remaining legacy context path must distinguish same-path local/global candidates."""
    from backend.knowledge import WikiKnowledgeSource
    from backend.knowledge.wiki import WikiStore

    store = WikiStore(research_store.database)
    for namespace, content in [("project", "Project note"), ("global", "Global note")]:
        store.write(
            project_id=101,
            namespace=namespace,
            path="same/path",
            title="Same title",
            content=content,
            expected_revision=0,
            actor="fixture",
            operation_key="same-" + namespace,
        )
    chunks = WikiKnowledgeSource(project_id=101).load_content()
    assert {chunk["metadata"]["namespace"] for chunk in chunks} == {"project", "global"}
    assert len({chunk["metadata"]["page_id"] for chunk in chunks}) == 2
    assert all(
        "Namespace:" in chunk["content"] and "Revision: 1" in chunk["content"]
        for chunk in chunks
    )


def test_owner_wiki_receipts_survive_delete_and_stale_ids_cannot_edit_a_recreated_path(
    research_client,
):
    """Recover actual committed versions before current-page lookup, including after deletion/recreation."""
    create = {
        "project_id": 101,
        "path": "retry/path",
        "title": "Original",
        "content": "Version one",
        "operation_key": "owner-create",
    }
    first = research_client.post("/api/wiki", json=create)
    assert first.status_code == 201, first.text
    page_id = first.json()["id"]
    path = "/api/wiki/retry%2Fpath?project_id=101"
    edit = {
        "page_id": page_id,
        "expected_revision": 1,
        "title": "Original",
        "content": "Version two",
        "operation_key": "owner-edit",
    }
    edited = research_client.put(path, json=edit)
    assert edited.status_code == 200, edited.text
    assert (
        research_client.delete(
            path + f"&page_id={page_id}&expected_revision=2&operation_key=owner-delete"
        ).status_code
        == 204
    )
    assert research_client.put(path, json=edit).json()["content"] == "Version two"
    assert (
        research_client.post("/api/wiki", json=create).json()["content"]
        == "Version one"
    )
    newer = research_client.post(
        "/api/wiki",
        json={
            **create,
            "operation_key": "owner-recreate",
            "title": "New document",
            "content": "Independent new context",
        },
    )
    assert newer.status_code == 201 and newer.json()["id"] != page_id
    stale = research_client.put(path, json={**edit, "operation_key": "stale-old-id"})
    assert stale.status_code == 409
    assert (
        research_client.delete(
            path + f"&page_id={page_id}&expected_revision=1&operation_key=stale-delete"
        ).status_code
        == 409
    )
    assert research_client.get(path).json()["content"] == "Independent new context"


def test_concurrent_wiki_editors_cannot_both_commit_the_same_observed_revision(
    research_store,
):
    """One SQLite write lock and id/revision compare yield one winner with no lost update."""
    from concurrent.futures import ThreadPoolExecutor

    from backend.knowledge.wiki import WikiConflict, WikiStore

    store = WikiStore(research_store.database)
    first = store.write(
        project_id=101,
        namespace="project",
        path="race",
        title="Race",
        content="Initial",
        expected_revision=0,
        actor="owner",
        operation_key="race-create",
    )

    def edit(number):
        """Submit an independent editor's intent against the identical observed identity/revision."""
        try:
            return store.write(
                project_id=101,
                namespace="project",
                path="race",
                title="Race",
                content=f"Editor {number}",
                expected_revision=1,
                page_id=first["page_id"],
                actor="owner",
                operation_key=f"race-{number}",
            )
        except WikiConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(edit, [1, 2]))
    assert sum(result is not None for result in outcomes) == 1
    assert store.read(101, "race", namespace="project")["revision"] == 2
    with store.transaction() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM wiki_revisions WHERE page_id=?",
                (first["page_id"],),
            ).fetchone()[0]
            == 2
        )
