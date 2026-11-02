"""Atomic SQLite adapter for evidence, report effects and revocable tool scopes.

The native runtime cannot mint scopes or choose project/actor identities. HTTP
adapters authorize a bearer token; mutations recheck it in their transaction,
including after slow acquisition. Receipts and effects commit together.
"""

import hashlib
import json
import secrets
import time
from collections.abc import Callable
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.db.connection import connect
from backend.research.models import (
    PERMISSIONS,
    FindingDraft,
    OperationConflict,
    ReferenceRecord,
    ReportDraft,
    ResearchForbidden,
    ResearchNotFound,
    ResearchScope,
    SourceDraft,
    bounded_text,
    operation_key,
    positive_id,
    validate_report_finding,
)


def _json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SQLiteResearchStore:
    """Own scoped source/finding/report/wiki transactions, revocable grants and atomic effect receipts."""

    def __init__(
        self,
        database: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        runtime_authority: Callable[[str], bool] | None = None,
    ):
        self.database = str(database)
        self.clock = clock
        self.runtime_authority = runtime_authority

    @contextmanager
    def _transaction(self, *, write=False):
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn

    def issue_grant(
        self,
        *,
        project_id: int,
        task_id: int,
        agent_id: str,
        permissions: set[str],
        ttl_seconds: float = 900,
    ) -> str:
        """Trusted host-only issuance; never expose this method as an agent tool."""
        positive_id(project_id)
        positive_id(task_id)
        bounded_text(agent_id, "agent_id", 128)
        if not permissions or not set(permissions) <= PERMISSIONS:
            raise ValueError("Unknown or empty tool permissions")
        if not 0 < ttl_seconds <= 3600:
            raise ValueError("Grant TTL must be positive and at most one hour")
        token = secrets.token_urlsafe(32)
        now = self.clock()
        with self._transaction(write=True) as conn:
            self._task(conn, project_id, task_id)
            conn.execute(
                "INSERT OR IGNORE INTO task_contexts(task_id,version) VALUES(?,1)",
                (task_id,),
            )
            version = conn.execute(
                "SELECT version FROM task_contexts WHERE task_id=?", (task_id,)
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO tool_grants(id,token_hash,project_id,task_id,agent_id,context_version,permissions_json,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    _hash(token),
                    project_id,
                    task_id,
                    agent_id,
                    version,
                    _json(sorted(permissions)),
                    now,
                    now + ttl_seconds,
                ),
            )
        return token

    def revoke_grant(self, grant_id: str) -> None:
        with self._transaction(write=True) as conn:
            conn.execute(
                "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE id=?",
                (self.clock(), grant_id),
            )

    def authorize(self, token: str) -> ResearchScope:
        if not isinstance(token, str) or not 20 <= len(token) <= 512:
            raise ResearchForbidden("Invalid tool credentials")
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM tool_grants WHERE token_hash=?", (_hash(token),)
            ).fetchone()
            if row is None:
                raise ResearchForbidden("Invalid tool credentials")
            scope = ResearchScope(
                row["id"],
                row["project_id"],
                row["task_id"],
                row["agent_id"],
                row["context_version"],
                frozenset(json.loads(row["permissions_json"])),
            )
            self._check_scope(conn, scope)
            return scope

    def _task(self, conn, project_id, task_id):
        row = conn.execute(
            "SELECT status FROM tasks WHERE id=? AND project_id=?",
            (task_id, project_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Task not found in this project")
        if row["status"] in ("done", "cancelled", "failed"):
            raise ResearchForbidden("Task no longer accepts tool operations")

    def _check_scope(self, conn, scope: ResearchScope, permission: str | None = None):
        row = conn.execute(
            "SELECT g.*,c.version AS current_version FROM tool_grants g JOIN task_contexts c ON c.task_id=g.task_id WHERE g.id=?",
            (scope.grant_id,),
        ).fetchone()
        if (
            row is None
            or row["revoked_at"] is not None
            or row["expires_at"] <= self.clock()
            or (
                row["project_id"],
                row["task_id"],
                row["agent_id"],
                row["context_version"],
            )
            != (scope.project_id, scope.task_id, scope.agent_id, scope.context_version)
            or row["context_version"] != row["current_version"]
        ):
            raise ResearchForbidden(
                "Tool scope expired, revoked or superseded by a context correction"
            )
        if permission and permission not in json.loads(row["permissions_json"]):
            raise ResearchForbidden("Tool scope lacks the required permission")
        if row["runtime_bound"]:
            if self.runtime_authority is not None and not self.runtime_authority(
                scope.grant_id
            ):
                raise ResearchForbidden(
                    "Execution authority was withdrawn by this host"
                )
            attempt = conn.execute(
                """SELECT a.id,a.status AS attempt_status,a.lease_expires_at,a.fence,
                    r.project_id,r.task_id,r.actor_id,r.context_version,r.status AS run_status,
                    r.fence AS current_fence,r.current_attempt_id
                    FROM runtime_attempts a JOIN runtime_runs r ON r.id=a.run_id
                    WHERE a.id=?""",
                (row["runtime_attempt_id"],),
            ).fetchone()
            if (
                attempt is None
                or attempt["attempt_status"] != "running"
                or attempt["run_status"] != "running"
                or attempt["lease_expires_at"] <= self.clock()
                or attempt["fence"] != attempt["current_fence"]
                or attempt["id"] != attempt["current_attempt_id"]
                or (
                    attempt["project_id"],
                    attempt["task_id"],
                    attempt["actor_id"],
                    attempt["context_version"],
                )
                != (
                    scope.project_id,
                    scope.task_id,
                    scope.agent_id,
                    scope.context_version,
                )
            ):
                raise ResearchForbidden(
                    "Execution attempt no longer owns this tool scope"
                )
        self._task(conn, scope.project_id, scope.task_id)

    @staticmethod
    def _permission(kind):
        """Bind each supported mutation to its explicit stored grant capability."""
        return {
            "source.capture": "sources.capture",
            "finding.record": "findings.write",
            "report.write": "reports.write",
            "question.ask": "questions.ask",
            "wiki.write": "wiki.write",
        }[kind]

    @staticmethod
    def _fingerprint(scope, kind, intent):
        return _hash(
            _json(
                {
                    "project_id": scope.project_id,
                    "task_id": scope.task_id,
                    "agent_id": scope.agent_id,
                    "context_version": scope.context_version,
                    "kind": kind,
                    "intent": intent,
                }
            )
        )

    def _receipt(self, conn, scope, key, kind, intent):
        row = conn.execute(
            "SELECT request_hash,result_json FROM tool_operations WHERE project_id=? AND task_id=? AND operation_key=?",
            (scope.project_id, scope.task_id, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != self._fingerprint(scope, kind, intent):
            raise OperationConflict(
                "Operation key already identifies a different intent"
            )
        return json.loads(row["result_json"])

    def lookup_operation(self, scope, key, kind, intent) -> dict | None:
        operation_key(key)
        with self._transaction() as conn:
            self._check_scope(conn, scope, self._permission(kind))
            return self._receipt(conn, scope, key, kind, intent)

    def _write(self, scope, key, kind, intent, apply):
        operation_key(key)
        fingerprint = self._fingerprint(scope, kind, intent)
        with self._transaction(write=True) as conn:
            self._check_scope(conn, scope, self._permission(kind))
            receipt = self._receipt(conn, scope, key, kind, intent)
            if receipt is not None:
                return receipt
            result = apply(conn)
            result["operation_key"] = key
            conn.execute(
                "INSERT INTO tool_operations(project_id,task_id,operation_key,kind,request_hash,result_json,grant_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    scope.project_id,
                    scope.task_id,
                    key,
                    kind,
                    fingerprint,
                    _json(result),
                    scope.grant_id,
                    self.clock(),
                ),
            )
            return result

    def capture_source(self, scope, key, draft: SourceDraft, *, intent: dict):
        digest = _hash(draft.content)

        def apply(conn):
            cursor = conn.execute(
                "INSERT INTO research_sources(project_id,task_id,kind,locator,title,content,sha256,provenance_json,captured_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    scope.project_id,
                    scope.task_id,
                    draft.kind,
                    draft.locator,
                    draft.title,
                    draft.content,
                    digest,
                    _json(draft.provenance),
                    self.clock(),
                ),
            )
            return {
                "source_id": cursor.lastrowid,
                "sha256": digest,
                "kind": draft.kind,
                "locator": draft.locator,
            }

        return self._write(scope, key, "source.capture", intent, apply)

    @staticmethod
    def _source(conn, project_id, source_id):
        row = conn.execute(
            "SELECT * FROM research_sources WHERE id=? AND project_id=?",
            (source_id, project_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Source not found in this project")
        result = dict(row)
        result["provenance"] = json.loads(result.pop("provenance_json"))
        return result

    def read_source(self, scope, source_id):
        positive_id(source_id)
        with self._transaction() as conn:
            self._check_scope(conn, scope, "sources.read")
            return self._source(conn, scope.project_id, source_id)

    def list_sources(self, scope, *, after_id=0, limit=50):
        if (
            type(after_id) is not int
            or after_id < 0
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ValueError("Invalid source page")
        with self._transaction() as conn:
            self._check_scope(conn, scope, "sources.read")
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT id,kind,locator,title,sha256,captured_at FROM research_sources WHERE project_id=? AND id>? ORDER BY id LIMIT ?",
                    (scope.project_id, after_id, limit),
                )
            ]

    def get_reference(self, scope, reference_id):
        positive_id(reference_id)
        with self._transaction() as conn:
            self._check_scope(conn, scope, "sources.capture")
            row = conn.execute(
                "SELECT id,project_id,file_name,file_path,file_type FROM reference_files WHERE id=? AND project_id=?",
                (reference_id, scope.project_id),
            ).fetchone()
            if row is None:
                raise ResearchNotFound("Reference file not found in this project")
            return ReferenceRecord(
                row["id"],
                row["project_id"],
                row["file_name"],
                row["file_path"],
                row["file_type"] or "application/octet-stream",
            )

    def list_references(self, scope):
        with self._transaction() as conn:
            self._check_scope(conn, scope, "sources.read")
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT id,file_name AS filename,file_size,file_type AS mime_type,description,uploaded_at FROM reference_files WHERE project_id=? ORDER BY id",
                    (scope.project_id,),
                )
            ]

    def record_finding(self, scope, key, draft: FindingDraft):
        def apply(conn):
            sources = [
                self._source(conn, scope.project_id, ref.source_id)
                for ref in draft.evidence
            ]
            for reference, source in zip(draft.evidence, sources, strict=True):
                reference.validate_against(source)
            cursor = conn.execute(
                "INSERT INTO findings(project_id,task_id,topic,content,sources_json,confidence,agent_id,status,finding_type) VALUES(?,?,?,?,?,NULL,?,'provisional',?)",
                (
                    scope.project_id,
                    scope.task_id,
                    draft.topic,
                    draft.content,
                    _json([source["locator"] for source in sources]),
                    scope.agent_id,
                    draft.finding_type,
                ),
            )
            finding_id = cursor.lastrowid
            for ref in draft.evidence:
                conn.execute(
                    "INSERT INTO finding_sources(project_id,finding_id,source_id,quote) VALUES(?,?,?,?)",
                    (scope.project_id, finding_id, ref.source_id, ref.quote),
                )
            return {
                "finding_id": finding_id,
                "status": "provisional",
                "confidence": None,
            }

        return self._write(scope, key, "finding.record", asdict(draft), apply)

    @staticmethod
    def _finding(conn, project_id, finding_id):
        row = conn.execute(
            "SELECT * FROM findings WHERE project_id=? AND id=?",
            (project_id, finding_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Finding not found in this project")
        return dict(row)

    def read_finding(self, scope, finding_id):
        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            result = self._finding(conn, scope.project_id, finding_id)
            result["evidence"] = self._evidence(conn, scope.project_id, [finding_id])
            return result

    @staticmethod
    def _evidence(conn, project_id, finding_ids):
        references = []
        for finding_id in finding_ids:
            rows = conn.execute(
                "SELECT fs.finding_id,fs.source_id,fs.quote,s.kind,s.locator,s.title,s.sha256,s.captured_at,f.status AS finding_status FROM finding_sources fs JOIN research_sources s ON s.project_id=fs.project_id AND s.id=fs.source_id JOIN findings f ON f.id=fs.finding_id WHERE fs.project_id=? AND fs.finding_id=? ORDER BY fs.source_id,fs.quote",
                (project_id, finding_id),
            ).fetchall()
            references.extend(dict(row) for row in rows)
        return references

    def write_report(self, scope, key, draft: ReportDraft):
        def apply(conn):
            for finding_id in draft.finding_ids:
                finding = self._finding(conn, scope.project_id, finding_id)
                validate_report_finding(
                    finding, self._evidence(conn, scope.project_id, [finding_id])
                )
            cursor = conn.execute(
                "INSERT INTO artifacts(project_id,task_id,type,file_path,description,content) VALUES(?,?,'report','pending',?,?)",
                (
                    scope.project_id,
                    scope.task_id,
                    draft.report_type + ": " + draft.title,
                    draft.markdown,
                ),
            )
            artifact_id = cursor.lastrowid
            conn.execute(
                "UPDATE artifacts SET file_path=? WHERE id=?",
                (f"reports/{artifact_id}.md", artifact_id),
            )
            conn.execute(
                "INSERT INTO research_reports(artifact_id,title,report_type,status,content_sha256) VALUES(?,?,?,'draft',?)",
                (artifact_id, draft.title, draft.report_type, _hash(draft.markdown)),
            )
            for finding_id in draft.finding_ids:
                conn.execute(
                    "INSERT INTO report_findings(project_id,artifact_id,finding_id) VALUES(?,?,?)",
                    (scope.project_id, artifact_id, finding_id),
                )
            return {"artifact_id": artifact_id, "status": "draft", "title": draft.title}

        return self._write(scope, key, "report.write", asdict(draft), apply)

    def read_report(self, scope, artifact_id):
        with self._transaction() as conn:
            self._check_scope(conn, scope, "reports.read")
            row = conn.execute(
                "SELECT a.*,r.title,r.report_type,r.status,r.content_sha256 FROM artifacts a JOIN research_reports r ON r.artifact_id=a.id WHERE a.project_id=? AND a.id=?",
                (scope.project_id, artifact_id),
            ).fetchone()
            if row is None:
                raise ResearchNotFound("Report not found in this project")
            result = dict(row)
            result["finding_ids"] = [
                r[0]
                for r in conn.execute(
                    "SELECT finding_id FROM report_findings WHERE project_id=? AND artifact_id=? ORDER BY finding_id",
                    (scope.project_id, artifact_id),
                )
            ]
            result["evidence"] = self._evidence(
                conn, scope.project_id, result["finding_ids"]
            )
            return result

    def wiki_read(self, scope, path, *, namespace="project", offset=0, max_chars=12000):
        """Read one explicit namespace under a current wiki-read grant; never fall through globally."""
        from backend.knowledge.wiki import read_page

        with self._transaction() as conn:
            self._check_scope(conn, scope, "wiki.read")
            return read_page(
                conn,
                scope.project_id,
                path,
                namespace=namespace,
                offset=offset,
                max_chars=max_chars,
            )

    def wiki_list(self, scope, **options):
        """Page scoped wiki metadata/lexical search without embeddings or an auxiliary LLM."""
        from backend.knowledge.wiki import list_pages

        with self._transaction() as conn:
            self._check_scope(conn, scope, "wiki.read")
            return list_pages(conn, scope.project_id, **options)

    def wiki_write(
        self,
        scope,
        key,
        *,
        path,
        title,
        content,
        expected_revision,
        parent_path=None,
        page_id=None,
    ):
        """Commit a project-only revision and receipt after checking current grant/context authority."""
        from backend.knowledge.wiki import validate_write, write_page

        validate_write(path, title, content, expected_revision, parent_path, page_id)
        intent = {
            "page_id": page_id,
            "path": path,
            "title": title,
            "content": content,
            "expected_revision": expected_revision,
            "parent_path": parent_path,
        }
        return self._write(
            scope,
            key,
            "wiki.write",
            intent,
            lambda conn: write_page(
                conn,
                scope.project_id,
                namespace="project",
                actor=scope.agent_id,
                **intent,
            ),
        )

    def capture_wiki(self, scope, key, *, page_id, revision, namespace="project"):
        """Capture exact retained wiki Markdown as source evidence; reading a page alone is not capture."""
        from backend.knowledge.wiki import read_revision

        positive_id(page_id)
        positive_id(revision)
        intent = {
            "wiki_page_id": page_id,
            "wiki_revision": revision,
            "namespace": namespace,
        }
        prior = self.lookup_operation(scope, key, "source.capture", intent)
        if prior is not None:
            return prior
        with self._transaction() as conn:
            self._check_scope(conn, scope, "wiki.read")
            row = read_revision(
                conn, scope.project_id, page_id, revision, namespace=namespace
            )
        draft = SourceDraft(
            kind="wiki",
            locator=f"wiki:{namespace}:{page_id}@{revision}",
            title=row["title"],
            content=row["content"],
            provenance={
                **intent,
                "wiki_path": row["path"],
                "wiki_content_sha256": row["sha256"],
                "wiki_actor": row["actor"],
                "wiki_revision_origin": row["origin"],
                "wiki_recorded_at": row["recorded_at"],
                "extraction": "wiki-revision-v1",
                "extraction_note": "Exact retained wiki Markdown, not scientific validation or current-page status.",
            },
        )
        return self.capture_source(scope, key, draft, intent=intent)

    def capture_wiki_collection(self, scope, key, *, members):
        """Capture all explicitly selected wiki revisions for existing scoped semantic retrieval."""
        from backend.knowledge.wiki import read_revision
        from backend.research.models import ResearchInputError
        from backend.research.structured_text import Units

        if not isinstance(members, list) or not 1 <= len(members) <= 50:
            raise ResearchInputError("Wiki collection requires 1–50 explicit revisions")
        identities = set()
        for member in members:
            if not isinstance(member, dict) or set(member) != {
                "page_id",
                "revision",
                "namespace",
            }:
                raise ResearchInputError(
                    "Wiki collection member requires page_id/revision/namespace"
                )
            positive_id(member["page_id"])
            positive_id(member["revision"])
            identity = (member["namespace"], member["page_id"], member["revision"])
            if (
                member["namespace"] not in ("project", "global")
                or identity in identities
            ):
                raise ResearchInputError(
                    "Wiki collection scopes must be explicit and members distinct"
                )
            identities.add(identity)
        intent = {"wiki_collection": members}
        prior = self.lookup_operation(scope, key, "source.capture", intent)
        if prior is not None:
            return prior
        units = Units()
        with self._transaction() as conn:
            self._check_scope(conn, scope, "wiki.read")
            for member in members:
                row = read_revision(conn, scope.project_id, **member)
                if not row["content"].strip():
                    raise ResearchInputError(
                        "An empty wiki page cannot be captured as textual evidence"
                    )
                units.add(
                    "wiki_page",
                    f"wiki:{member['namespace']}:{member['page_id']}@{member['revision']}",
                    row["content"],
                )
                units.units[-1].update(
                    {
                        "wiki_page_id": member["page_id"],
                        "wiki_revision": member["revision"],
                        "namespace": member["namespace"],
                        "wiki_content_sha256": row["sha256"],
                    }
                )
        content, provenance = units.finish(
            "wiki",
            collection_member_count=len(members),
            extraction_note="Every requested retained wiki revision is included in request order. Markers identify members; quotations address this normalized collection, not current-page state or scientific validation.",
        )
        draft = SourceDraft(
            kind="wiki",
            locator="wiki-collection:" + _hash(_json(members)),
            title=f"Wiki collection: {len(members)} revisions",
            content=content,
            provenance=provenance,
        )
        return self.capture_source(scope, key, draft, intent=intent)
