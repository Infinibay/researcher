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
    """Serialize deterministic UTF-8 JSON text with sorted keys and reject nonfinite numeric values."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash(value: str) -> str:
    """Return the SHA-256 identity of UTF-8 text used for credentials and effect intents."""
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
        """Bind the existing database, clock and optional live-runtime authority check without opening a connection."""
        self.database = str(database)
        self.clock = clock
        self.runtime_authority = runtime_authority

    @contextmanager
    def _transaction(self, *, write=False):
        """Own an existing-only SQLite read or immediate-write transaction and commit or roll back on exit."""
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
        """Record the first revocation time without deleting the original grant or overwriting its history."""
        with self._transaction(write=True) as conn:
            conn.execute(
                "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE id=?",
                (self.clock(), grant_id),
            )

    def authorize(self, token: str) -> ResearchScope:
        """Resolve a token to its stored scope and recheck current grant, context and task authority."""
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
        """Require the task to belong to this project and still accept research-tool operations."""
        row = conn.execute(
            "SELECT status FROM tasks WHERE id=? AND project_id=?",
            (task_id, project_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Task not found in this project")
        if row["status"] in ("done", "cancelled", "failed"):
            raise ResearchForbidden("Task no longer accepts tool operations")

    def _check_scope(self, conn, scope: ResearchScope, permission: str | None = None):
        """Recheck stored grant, live attempt, context and review-subject authority in this transaction."""
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
                    r.fence AS current_fence,r.current_attempt_id,r.id AS run_id,r.execution_kind
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
            if attempt["execution_kind"] == "code_review":
                from backend.research.models import CODE_REVIEW_PERMISSIONS
                from backend.runtime.code_reviews import CodeReviews
                from backend.runtime.sqlite_runs import SQLiteRunStore

                if (
                    not set(json.loads(row["permissions_json"]))
                    <= CODE_REVIEW_PERMISSIONS
                ):
                    raise ResearchForbidden(
                        "Code reviewer grants cannot acquire author mutation permissions"
                    )
                CodeReviews(SQLiteRunStore(self.database, clock=self.clock))._request(
                    conn, scope.project_id, attempt["run_id"], require_current=True
                )
        self._task(conn, scope.project_id, scope.task_id)
        from backend.knowledge.reviews import scope_request, verify_current
        from backend.research.models import REVIEW_PERMISSIONS

        review = scope_request(conn, scope)
        if review is not None:
            if not set(json.loads(row["permissions_json"])) <= REVIEW_PERMISSIONS:
                raise ResearchForbidden(
                    "Reviewer grants cannot acquire author mutation permissions"
                )
            if permission in {
                "sources.read",
                "findings.read",
                "reports.read",
                "wiki.read",
                "tasks.read",
                "messages.read",
                "messages.send",
                "messages.ack",
            }:
                verify_current(conn, review)

    @staticmethod
    def _permission(kind):
        """Bind each supported mutation to its explicit stored grant capability."""
        return {
            "source.capture": "sources.capture",
            "finding.record": "findings.write",
            "report.write": "reports.write",
            "investigation.summary": "reports.write",
            "question.ask": "questions.ask",
            "wiki.write": "wiki.write",
            "review.record": "findings.review",
            "result.propose": "results.propose",
            "task.comment": "tasks.comment",
            "task.note": "continuity.write",
            "message.send": "messages.send",
            "message.ack": "messages.ack",
        }[kind]

    @staticmethod
    def _fingerprint(scope, kind, intent):
        """Bind project, task, author, context, operation kind and exact intent into one deterministic hash."""
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
        """Return the original scoped effect receipt or reject reuse of its key for a different intent."""
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
        """Recheck current permission before reconciling an exact previously committed operation."""
        operation_key(key)
        with self._transaction() as conn:
            self._check_scope(conn, scope, self._permission(kind))
            return self._receipt(conn, scope, key, kind, intent)

    def _write(self, scope, key, kind, intent, apply):
        """Recheck authority and commit an effect with its receipt atomically, returning an exact replay unchanged."""
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

    def propose_result(self, scope, key, draft):
        """Record selected final reports under the actual live author grant, never accept a task."""
        from backend.knowledge.results import record_proposal

        intent = {"producer_grant_id": scope.grant_id, "draft": asdict(draft)}
        return self._write(
            scope,
            key,
            "result.propose",
            intent,
            lambda conn: record_proposal(conn, scope, draft, now=self.clock()),
        )

    def read_reviews(
        self,
        scope,
        finding_id,
        *,
        request_id=None,
        part="decision",
        after_id=0,
        limit=20,
        offset=0,
        max_chars=12000,
    ):
        """Read attributed feedback or frozen old subjects in the same authenticated snapshot."""
        from backend.knowledge.reviews import read_feedback

        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            return read_feedback(
                conn,
                scope.project_id,
                finding_id,
                request_id=request_id,
                part=part,
                after_id=after_id,
                limit=limit,
                offset=offset,
                max_chars=max_chars,
            )

    def read_review_subject(self, scope, *, offset=0, max_chars=12000):
        """Page this reviewer's exact immutable subject, never an inferred latest version."""
        from backend.knowledge.findings import window
        from backend.knowledge.reviews import scope_request

        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            review = scope_request(conn, scope)
            if review is None:
                raise ResearchForbidden("This grant has no admitted review subject")
            return {
                "finding_id": review["finding_id"],
                "subject_sha256": review["subject_sha256"],
                "review_run_id": review["run_id"],
                "reviewer_attempt_id": review["reviewer_attempt_id"],
                "author_attempt_id": review["author_attempt_id"],
                "review_scope": "reported_checks_only",
                **window(review["snapshot_json"], offset, max_chars),
            }

    def record_review(self, scope, key, draft):
        """Commit one attributed decision for the live original review request and subject."""
        from backend.knowledge.reviews import (
            scope_request,
            source_version,
            verify_current,
        )
        from backend.research.models import (
            InvalidEvidence,
            ResearchInputError,
            ReviewDecision,
        )

        if not isinstance(draft, ReviewDecision):
            raise ResearchInputError("A typed explained review decision is required")
        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.review")
            review = scope_request(conn, scope)
            if review is None:
                raise ResearchForbidden(
                    "Review decisions require an owner-admitted reviewer attempt"
                )
        intent = {
            "review_run_id": review["run_id"],
            "subject_sha256": review["subject_sha256"],
            "decision": asdict(draft),
        }
        if len(_json(intent).encode()) > 200000:
            raise ResearchInputError(
                "Serialized review decision exceeds its 200000-byte budget"
            )

        def apply(conn):
            """Recheck the complete subject and exact evidence inside the receipt transaction."""
            current_request = scope_request(conn, scope)
            if current_request is None or current_request["run_id"] != review["run_id"]:
                raise ResearchForbidden("Original review admission ended")
            verify_current(conn, current_request)
            if conn.execute(
                "SELECT 1 FROM finding_review_decisions WHERE run_id=?",
                (review["run_id"],),
            ).fetchone():
                raise OperationConflict(
                    "This review already has a decision; recover its original receipt"
                )
            verified_evidence = []
            source_versions = {}
            for ref in draft.evidence:
                source = self._source(conn, scope.project_id, ref.source_id)
                if _hash(source["content"]) != source["sha256"]:
                    raise InvalidEvidence(
                        "Review source hash differs from its saved text"
                    )
                ref.validate_against(source)
                metadata, version = source_version(source)
                source_versions[ref.source_id] = (metadata, version)
                verified_evidence.append(
                    {
                        "source_id": source["id"],
                        "source_sha256": source["sha256"],
                        "quote": ref.quote,
                        "quote_offset": source["content"].index(ref.quote),
                    }
                )
            self._check_scope(conn, scope, "findings.review")
            if (
                sum(len(_json(meta).encode()) for meta, _ in source_versions.values())
                > 1048576
            ):
                raise ResearchInputError(
                    "Complete review evidence metadata exceeds its one MiB snapshot budget"
                )
            payload = {
                **asdict(draft),
                "verified_evidence": verified_evidence,
                "review_scope": "reported_checks_only",
                "scientific_confidence": None,
            }
            cursor = conn.execute(
                """INSERT INTO finding_review_decisions(run_id,project_id,finding_id,subject_sha256,
                reviewer_attempt_id,reviewer_actor_id,reviewer_fence,verdict,decision_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    review["run_id"],
                    scope.project_id,
                    review["finding_id"],
                    review["subject_sha256"],
                    review["reviewer_attempt_id"],
                    scope.agent_id,
                    review["reviewer_fence"],
                    draft.verdict,
                    _json(payload),
                    self.clock(),
                ),
            )
            result = {
                "decision_id": cursor.lastrowid,
                "review_run_id": review["run_id"],
                "finding_id": review["finding_id"],
                "subject_sha256": review["subject_sha256"],
                "verdict": draft.verdict,
                "independent_attempt": True,
                "scientific_confidence": None,
                "task_accepted": False,
                "report_published": False,
            }
            for sid, (metadata, version) in source_versions.items():
                conn.execute(
                    "INSERT INTO finding_review_evidence(project_id,decision_id,source_id,source_sha256,metadata_sha256,metadata_json) VALUES(?,?,?,?,?,?)",
                    (
                        scope.project_id,
                        cursor.lastrowid,
                        sid,
                        metadata["sha256"],
                        version,
                        _json(metadata),
                    ),
                )
            conn.execute(
                "INSERT INTO events_log(project_id,event_type,event_source,entity_type,entity_id,event_data_json) VALUES(?,'finding.review_recorded','runtime','finding',?,?)",
                (scope.project_id, review["finding_id"], _json(result)),
            )
            return result

        return self._write(scope, key, "review.record", intent, apply)

    def _insert_source(self, conn, scope, draft: SourceDraft):
        """Insert one exact captured document inside the caller's already-authorized source/receipt transaction."""
        digest = _hash(draft.content)
        cursor = conn.execute(
            "INSERT INTO research_sources(project_id,task_id,kind,locator,title,content,sha256,provenance_json,captured_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (scope.project_id, scope.task_id, draft.kind, draft.locator, draft.title, draft.content, digest, _json(draft.provenance), self.clock()),
        )
        return {"source_id": cursor.lastrowid, "sha256": digest, "kind": draft.kind, "locator": draft.locator}

    def capture_source(self, scope, key, draft: SourceDraft, *, intent: dict):
        """Persist captured document and original receipt together; ordinary capture intent remains compatible."""
        return self._write(scope, key, "source.capture", intent, lambda conn: self._insert_source(conn, scope, draft))

    def capture_command(self, scope, key, job_id):
        """Capture this native author's actual closed terminal command output as exact citable evidence without replaying work."""
        from backend.research.command_sources import capture_command

        return capture_command(self, scope, key, job_id)

    @staticmethod
    def _source(conn, project_id, source_id):
        """Load one source only from the specified project and decode its stored provenance."""
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
        """Require sources.read authority and return the full captured source in the caller project."""
        positive_id(source_id)
        with self._transaction() as conn:
            self._check_scope(conn, scope, "sources.read")
            return self._source(conn, scope.project_id, source_id)

    def list_sources(self, scope, *, after_id=0, limit=50):
        """Return ascending source metadata after an ID within the validated page bound and current scope."""
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
        """Resolve a project-scoped upload with any original imported identity and its expected byte hash."""
        positive_id(reference_id)
        with self._transaction() as conn:
            self._check_scope(conn, scope, "sources.capture")
            row = conn.execute(
                "SELECT f.id,f.project_id,f.file_name,f.file_path,f.file_type,p.content_sha256,p.provenance_json FROM reference_files f LEFT JOIN reference_import_provenance p ON p.reference_file_id=f.id WHERE f.id=? AND f.project_id=?",
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
                None if row['provenance_json'] is None else {'sha256':row['content_sha256'],'details':json.loads(row['provenance_json'])},
            )

    def list_references(self, scope):
        """Return this authorized project's uploaded-reference metadata in ascending identity order."""
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
        """Persist a provisional claim with an effect receipt sealing its authored version."""

        def apply(conn):
            """Validate exact quotations and save the producer seal in the same transaction."""
            from backend.knowledge.reviews import finding_version

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
                "finding_version_schema": 1,
                "finding_version_sha256": finding_version(
                    self._finding(conn, scope.project_id, finding_id),
                    [asdict(ref) for ref in draft.evidence],
                ),
            }

        return self._write(scope, key, "finding.record", asdict(draft), apply)

    @staticmethod
    def _finding(conn, project_id, finding_id):
        """Load one finding from the specified project or reject the missing scoped identity."""
        row = conn.execute(
            "SELECT * FROM findings WHERE project_id=? AND id=?",
            (project_id, finding_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Finding not found in this project")
        return dict(row)

    def list_findings(self, scope, **selection):
        """Return scoped metadata pages; stored confidence is a declaration, not scientific validation."""
        from backend.knowledge.findings import list_findings

        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            return list_findings(conn, scope.project_id, **selection)

    def summarize_findings(self, scope, **selection):
        """Aggregate every matching finding without sampling or another inference loop."""
        from backend.knowledge.findings import summarize_findings

        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            return summarize_findings(conn, scope.project_id, **selection)

    def finding_corpus(self, scope, **selection):
        """Freeze a complete current scoped finding corpus, rechecking grant/context authority."""
        from backend.knowledge.findings import finding_corpus

        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            return finding_corpus(conn, scope.project_id, **selection)

    def read_finding(self, scope, finding_id, **selection):
        """Read bounded current claim/citation windows with actual historical review provenance."""
        from backend.knowledge.findings import read_finding

        with self._transaction() as conn:
            self._check_scope(conn, scope, "findings.read")
            return read_finding(conn, scope.project_id, finding_id, **selection)

    @staticmethod
    def _evidence(conn, project_id, finding_ids):
        """Read stored quotations, source identities and finding status for the selected project findings."""
        references = []
        for finding_id in finding_ids:
            rows = conn.execute(
                "SELECT fs.finding_id,fs.source_id,fs.quote,s.kind,s.locator,s.title,s.sha256,s.captured_at,f.status AS finding_status FROM finding_sources fs JOIN research_sources s ON s.project_id=fs.project_id AND s.id=fs.source_id JOIN findings f ON f.id=fs.finding_id WHERE fs.project_id=? AND fs.finding_id=? ORDER BY fs.source_id,fs.quote",
                (project_id, finding_id),
            ).fetchall()
            references.extend(dict(row) for row in rows)
        return references

    def _insert_report(self, conn, scope, draft):
        """Insert canonical draft/evidence rows inside the caller's already-authorized receipt transaction; shared by ordinary and exploratory reports."""
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

    def write_report(self, scope, key, draft: ReportDraft):
        """Persist an ordinary canonical report and its exact original writer receipt under the current scoped grant."""
        return self._write(scope, key, "report.write", asdict(draft), lambda conn: self._insert_report(conn, scope, draft))

    def write_investigation_summary(self, scope, key, draft):
        """Persist a typed exploratory scope/area summary through the same report and receipt transaction, never a task acceptance."""
        from backend.research.investigation import write_summary

        return write_summary(self, scope, key, draft)

    def query_knowledge(self, scope, query, **selection):
        """Search requested source kinds only after checking each live read permission in the same SQL snapshot."""
        from backend.knowledge.search import KnowledgeSearchStore, select_sources

        permissions = {"findings": "findings.read", "wiki": "wiki.read", "reference_files": "sources.read", "reports": "reports.read"}
        selected = select_sources(selection.get("sources"))
        with self._transaction() as conn:
            for source in selected:
                self._check_scope(conn, scope, permissions[source])
            return KnowledgeSearchStore.query_snapshot(conn, scope.project_id, query, **selection)

    def read_report(self, scope, artifact_id):
        """Read retained report bytes in this project, explicitly distinguishing native records from unverified history; never open paths."""
        positive_id(artifact_id)
        with self._transaction() as conn:
            self._check_scope(conn, scope, "reports.read")
            row = conn.execute(
                "SELECT a.*,r.artifact_id AS native_record,r.title,r.report_type,r.status,r.content_sha256 FROM artifacts a LEFT JOIN research_reports r ON r.artifact_id=a.id WHERE a.project_id=? AND a.id=? AND a.type='report'",
                (scope.project_id, artifact_id),
            ).fetchone()
            if row is None:
                raise ResearchNotFound("Report not found in this project")
            result = dict(row)
            if not isinstance(result["content"], str):
                raise ResearchNotFound("Report bytes are not retained in this database; restore the registered historical artifact before reading")
            native = result.pop("native_record") is not None
            result["record_origin"] = "native" if native else "legacy_unverified"
            result["hash_origin"] = "stored_native_content" if native else "observed_legacy_content"
            if not native:
                result.update(title=result["description"] or f"Historical report {artifact_id}",
                              report_type="legacy", status="legacy_unverified", content_sha256=_hash(result["content"]))
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
