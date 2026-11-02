"""Explicit wiki namespaces, revision guards and durable mutation receipts.

Shared by owner HTTP, legacy adapters and grant-checked native tools. A namespace
is always selected; a project miss never falls through to a global document.
These Markdown notes are context, not scientific validation or authorization.
"""

import hashlib
import json
from contextlib import closing, contextmanager
from datetime import UTC, datetime

from backend.db.connection import connect
from backend.research.models import (
    OperationConflict,
    ResearchInputError,
    ResearchNotFound,
    bounded_text,
    operation_key,
)


class WikiConflict(OperationConflict):
    """The observed revision or retry identity no longer matches this edit's intent."""


def content_hash(content):
    """Identify the exact saved Markdown bytes, independently of current title or layout."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def namespace_filter(project_id, namespace):
    """Build only a fixed SQL predicate; the caller cannot supply SQL or an implicit fallback."""
    if (
        type(project_id) is not int
        or project_id <= 0
        or namespace not in ("project", "global")
    ):
        raise ResearchInputError(
            "Wiki requires a positive project and explicit project/global namespace"
        )
    return (
        ("project_id=?", [project_id])
        if namespace == "project"
        else ("project_id IS NULL", [])
    )


def page_metadata(row):
    """Expose identity and revision without serializing large content/embedding fields."""
    result = {
        key: row[key]
        for key in (
            "id",
            "project_id",
            "path",
            "title",
            "parent_path",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "revision",
        )
    }
    result["namespace"] = "global" if row["project_id"] is None else "project"
    result["sha256"] = content_hash(row["content"])
    return result


def read_page(
    conn, project_id, path, *, namespace="project", offset=0, max_chars=200000
):
    """Read one active page with explicit namespace and an honest continuation offset."""
    where, params = namespace_filter(project_id, namespace)
    row = conn.execute(
        f"SELECT * FROM wiki_pages WHERE {where} AND path=?", (*params, path)
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Wiki page was not found in the selected namespace")
    verify_current_revision(conn, row, project_id, namespace)
    text = row["content"]
    chunk = text[offset : offset + max_chars]
    end = offset + len(chunk)
    return {
        **page_metadata(row),
        "content": chunk,
        "total_chars": len(text),
        "offset": offset,
        "next_offset": end if end < len(text) else None,
    }


def read_revision(conn, project_id, page_id, revision, *, namespace="project"):
    """Recover exact retained Markdown even after its active page was edited or deleted."""
    where, params = namespace_filter(project_id, namespace)
    row = conn.execute(
        f"SELECT * FROM wiki_revisions WHERE {where} AND page_id=? AND revision=?",
        (*params, page_id, revision),
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Wiki revision was not found in the selected namespace")
    if content_hash(row["content"]) != row["sha256"]:
        raise WikiConflict(
            "Retained wiki revision failed its content hash; reconcile stored evidence before use"
        )
    return {**dict(row), "namespace": namespace}


def verify_current_revision(conn, row, project_id, namespace):
    """Detect unversioned legacy writes instead of presenting changed text as a recorded revision."""
    try:
        saved = read_revision(
            conn, project_id, row["id"], row["revision"], namespace=namespace
        )
    except ResearchNotFound as exc:
        raise WikiConflict(
            "Wiki page has no recorded revision; reconcile the legacy writer before editing"
        ) from exc
    if any(
        row[name] != saved[name] for name in ("path", "title", "content", "parent_path")
    ):
        raise WikiConflict(
            "Wiki changed outside revision tracking; preserve the draft and reconcile before use"
        )


def list_pages(
    conn, project_id, *, namespace="project", after_id=0, limit=50, query=None
):
    """Page metadata by stable id; optional lexical FTS never invokes a model or embeddings."""
    where, params = namespace_filter(project_id, namespace)
    if (
        type(after_id) is not int
        or after_id < 0
        or type(limit) is not int
        or not 1 <= limit <= 100
    ):
        raise ResearchInputError("Wiki cursor/limit is invalid")
    extra = ""
    if query is not None:
        from backend.tools.base.db import sanitize_fts5_query

        bounded_text(query, "wiki search", 500)
        extra = " AND id IN (SELECT rowid FROM wiki_fts WHERE wiki_fts MATCH ?)"
        params.append(sanitize_fts5_query(query))
    try:
        rows = conn.execute(
            f"SELECT * FROM wiki_pages WHERE {where}{extra} AND id>? ORDER BY id LIMIT ?",
            (*params, after_id, limit + 1),
        ).fetchall()
    except Exception as exc:
        import sqlite3

        if not isinstance(exc, sqlite3.OperationalError) or query is None:
            raise
        raise ResearchInputError(
            "Wiki lexical search could not execute this query"
        ) from exc
    selected = rows[:limit]
    return {
        "pages": [page_metadata(row) for row in selected],
        "namespace": namespace,
        "next_after_id": selected[-1]["id"] if len(rows) > limit else None,
        "search_kind": "fts5_lexical" if query is not None else None,
    }


def validate_write(
    path, title, content, expected_revision, parent_path=None, page_id=None
):
    """Bound new edits and require an observed revision; zero means explicit creation."""
    bounded_text(path, "wiki path", 512)
    bounded_text(title, "wiki title", 1200)
    if not isinstance(content, str) or len(content.encode("utf-8")) > 200000:
        raise ResearchInputError("Wiki content must be at most 200000 UTF-8 bytes")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ResearchInputError(
            "Wiki edit requires expected_revision >= 0; read before editing"
        )
    if expected_revision > 0 and (type(page_id) is not int or page_id <= 0):
        raise ResearchInputError(
            "Wiki updates require the observed page_id as well as revision"
        )
    if expected_revision == 0 and page_id is not None:
        raise ResearchInputError("Wiki creation must not reuse a page identity")
    if parent_path is not None:
        bounded_text(parent_path, "wiki parent path", 512)


def write_page(
    conn,
    project_id,
    *,
    namespace,
    path,
    title,
    content,
    expected_revision,
    actor,
    parent_path=None,
    page_id=None,
):
    """Apply a revision-guarded edit inside the caller's existing write/receipt transaction."""
    validate_write(path, title, content, expected_revision, parent_path, page_id)
    where, params = namespace_filter(project_id, namespace)
    row = conn.execute(
        f"SELECT * FROM wiki_pages WHERE {where} AND path=?", (*params, path)
    ).fetchone()
    if row is None and expected_revision != 0:
        raise ResearchNotFound("Wiki page was not found in the selected namespace")
    if row is not None and (
        row["revision"] != expected_revision or row["id"] != page_id
    ):
        raise WikiConflict(
            "Wiki changed since the observed revision; preserve the draft and compare before saving again"
        )
    if row is not None:
        verify_current_revision(conn, row, project_id, namespace)
    if parent_path is not None:
        seen = {path}
        ancestor = parent_path
        while ancestor is not None:
            if ancestor in seen or len(seen) > 64:
                raise ResearchInputError(
                    "Wiki parent hierarchy would be cyclic or too deep"
                )
            seen.add(ancestor)
            parent = conn.execute(
                f"SELECT parent_path FROM wiki_pages WHERE {where} AND path=?",
                (*params, ancestor),
            ).fetchone()
            if parent is None:
                raise ResearchNotFound("Wiki parent is missing in the same namespace")
            ancestor = parent["parent_path"]
    timestamp = datetime.now(UTC).isoformat()
    revision = expected_revision + 1
    if row is None:
        cursor = conn.execute(
            "INSERT INTO wiki_pages(project_id,path,title,content,parent_path,created_by,updated_by,created_at,updated_at,revision) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                project_id if namespace == "project" else None,
                path,
                title,
                content,
                parent_path,
                actor,
                actor,
                timestamp,
                timestamp,
                revision,
            ),
        )
        page_id = cursor.lastrowid
    else:
        page_id = row["id"]
        conn.execute(
            "UPDATE wiki_pages SET title=?,content=?,parent_path=?,updated_by=?,updated_at=?,revision=?,embedding=NULL WHERE id=? AND revision=?",
            (
                title,
                content,
                parent_path,
                actor,
                timestamp,
                revision,
                page_id,
                expected_revision,
            ),
        )
    digest = content_hash(content)
    conn.execute(
        "INSERT INTO wiki_revisions(page_id,revision,project_id,path,title,content,parent_path,sha256,actor,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            page_id,
            revision,
            project_id if namespace == "project" else None,
            path,
            title,
            content,
            parent_path,
            digest,
            actor,
            timestamp,
        ),
    )
    return {
        "page_id": page_id,
        "project_id": project_id if namespace == "project" else None,
        "namespace": namespace,
        "path": path,
        "revision": revision,
        "sha256": digest,
        "action": "created" if row is None else "updated",
    }


class WikiStore:
    """Own authenticated owner wiki transactions; native adapters check grants in their own transaction."""

    def __init__(self, database):
        """Bind existing product storage; this adapter never initializes missing databases."""
        self.database = str(database)

    @contextmanager
    def transaction(self, *, write=False):
        """Serialize edits and receipts while returning plain scoped reads from one snapshot."""
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn

    def read(self, project_id, path, **options):
        """Read one namespace, preserving old content windows when requested explicitly."""
        with self.transaction() as conn:
            return read_page(conn, project_id, path, **options)

    def read_revision(self, project_id, page_id, revision, **options):
        """Recover a retained revision for comparison or subsequent exact source capture."""
        with self.transaction() as conn:
            return read_revision(conn, project_id, page_id, revision, **options)

    def list(self, project_id, **options):
        """Return a bounded index/search page without implicit global-project merging."""
        with self.transaction() as conn:
            return list_pages(conn, project_id, **options)

    def write(
        self,
        *,
        project_id,
        namespace,
        path,
        title,
        content,
        expected_revision,
        actor,
        operation_key,
        parent_path=None,
        page_id=None,
    ):
        """Recover same-intent receipts before checking current revision, avoiding retry edits."""
        from backend.research.models import operation_key as validate_key

        validate_key(operation_key)
        validate_write(path, title, content, expected_revision, parent_path, page_id)
        namespace_filter(project_id, namespace)
        intent = {
            "page_id": page_id,
            "path": path,
            "title": title,
            "content": content,
            "expected_revision": expected_revision,
            "actor": actor,
            "parent_path": parent_path,
        }
        return self._mutation(
            project_id,
            namespace,
            operation_key,
            {"kind": "write", **intent},
            lambda conn: write_page(conn, project_id, namespace=namespace, **intent),
        )

    def _mutation(self, project_id, namespace, key, intent, apply):
        """Commit one owner effect and receipt atomically under an explicit namespace identity."""
        operation_key(key)
        scope = "global" if namespace == "global" else f"project:{project_id}"
        digest = content_hash(
            json.dumps(
                intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
        )
        with self.transaction(write=True) as conn:
            if not conn.execute(
                "SELECT 1 FROM projects WHERE id=?", (project_id,)
            ).fetchone():
                raise ResearchNotFound("Wiki project was not found")
            old = conn.execute(
                "SELECT request_hash,result_json FROM wiki_operations WHERE scope_identity=? AND operation_key=?",
                (scope, key),
            ).fetchone()
            if old:
                if old["request_hash"] != digest:
                    raise WikiConflict(
                        "Wiki operation key already identifies another intent"
                    )
                return json.loads(old["result_json"])
            result = apply(conn) | {"operation_key": key}
            conn.execute(
                "INSERT INTO wiki_operations VALUES(?,?,?,?)",
                (scope, key, digest, json.dumps(result)),
            )
            return result

    def delete(
        self,
        project_id,
        path,
        *,
        namespace,
        expected_revision,
        actor,
        operation_key,
        page_id=None,
    ):
        """Remove an active page only at its observed revision, retaining immutable revision history."""
        namespace_filter(project_id, namespace)
        if type(page_id) is not int or page_id <= 0:
            raise ResearchInputError("Wiki deletion requires the observed page_id")
        intent = {
            "page_id": page_id,
            "kind": "delete",
            "path": path,
            "expected_revision": expected_revision,
            "actor": actor,
        }

        def apply(conn):
            """Delete the selected identity, never a global fallback, under the receipt lock."""
            page = read_page(conn, project_id, path, namespace=namespace)
            if page["revision"] != expected_revision or page["id"] != page_id:
                raise WikiConflict("Wiki changed since the observed delete revision")
            where, params = namespace_filter(project_id, namespace)
            if conn.execute(
                f"SELECT 1 FROM wiki_pages WHERE {where} AND parent_path=?",
                (*params, path),
            ).fetchone():
                raise WikiConflict(
                    "Wiki has child pages; move them explicitly before deleting"
                )
            conn.execute("DELETE FROM wiki_pages WHERE id=?", (page["id"],))
            return {
                "page_id": page["id"],
                "revision": expected_revision,
                "namespace": namespace,
                "deleted": True,
            }

        return self._mutation(project_id, namespace, operation_key, intent, apply)
