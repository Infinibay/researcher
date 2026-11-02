"""Freeze review subjects and preserve actual author and evidence provenance.

A historical status, reviewer-looking name or exact quote is not an independent
review. Subject fingerprints bind the stored claim and its dependencies; they do
not prove scientific correctness or that an agent understood the material.
"""

import hashlib
import json

from backend.research.models import (
    InvalidEvidence,
    OperationConflict,
    ResearchForbidden,
    ResearchInputError,
    ResearchNotFound,
    positive_id,
)


def canonical(value):
    """Serialize complete review data consistently, rejecting nonfinite numbers."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value):
    """Fingerprint a canonical subject or decision, without claiming its truth."""
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def finding_version(finding, evidence):
    """Seal the authored claim/quoted references, excluding later administrative state."""
    material = {
        key: finding[key]
        for key in (
            "project_id",
            "task_id",
            "agent_id",
            "topic",
            "content",
            "finding_type",
        )
    }
    material["source_declarations"] = json.loads(finding["sources_json"])
    material["evidence"] = sorted(
        evidence, key=lambda ref: (ref["source_id"], ref["quote"])
    )
    return digest({"schema_version": 1, **material})


def source_version(source):
    """Verify actual saved bytes and fingerprint source identity/provenance separately."""
    if (
        not isinstance(source["content"], str)
        or hashlib.sha256(source["content"].encode()).hexdigest() != source["sha256"]
    ):
        raise InvalidEvidence("Captured source hash differs from its saved text")
    metadata = {key: value for key, value in source.items() if key != "content"}
    if "provenance_json" in metadata:
        try:
            metadata["provenance"] = json.loads(metadata.pop("provenance_json"))
        except (TypeError, ValueError) as exc:
            raise InvalidEvidence("Captured source provenance is unreadable") from exc
    return metadata, digest(metadata)


def decision_evidence_current(conn, project_id, decision_id, *, cache=None):
    """Keep every cited source, including counterevidence, bound to its saved version."""
    if decision_id is None:
        return True
    cache = {} if cache is None else cache
    refs = conn.execute(
        "SELECT source_id,metadata_sha256 FROM finding_review_evidence WHERE project_id=? AND decision_id=?",
        (project_id, decision_id),
    ).fetchall()
    expected = conn.execute(
        "SELECT COUNT(DISTINCT json_extract(value,'$.source_id')) FROM finding_review_decisions,json_each(decision_json,'$.verified_evidence') WHERE finding_review_decisions.project_id=? AND finding_review_decisions.id=?",
        (project_id, decision_id),
    ).fetchone()[0]
    if len(refs) != expected:
        return False
    for ref in refs:
        sid = ref["source_id"]
        if sid not in cache:
            row = conn.execute(
                "SELECT * FROM research_sources WHERE project_id=? AND id=?",
                (project_id, sid),
            ).fetchone()
            try:
                cache[sid] = source_version(dict(row))[1] if row is not None else None
            except InvalidEvidence:
                cache[sid] = None
        if cache[sid] != ref["metadata_sha256"]:
            return False
    return True


def review_presence(conn, project_id, finding_ids):
    """Read cheap review presence; a stored decision does not establish currentness."""
    if not finding_ids:
        return {}
    result = {}
    marks = ",".join("?" for _ in finding_ids)
    rows = conn.execute(
        f"""SELECT q.id AS request_id,q.finding_id,r.status,d.id AS decision_id,d.verdict
        FROM finding_review_requests q JOIN runtime_runs r ON r.id=q.run_id
        LEFT JOIN finding_review_decisions d ON d.run_id=q.run_id
        WHERE q.project_id=? AND q.finding_id IN ({marks}) ORDER BY q.id DESC""",
        (project_id, *finding_ids),
    )
    for row in rows:
        item = result.setdefault(
            row["finding_id"],
            {
                "latest_request_id": row["request_id"],
                "latest_request_status": row["status"],
                "latest_decision_request_id": None,
                "reported_verdict": None,
                "currentness": "not_checked",
            },
        )
        if (
            row["decision_id"] is not None
            and item["latest_decision_request_id"] is None
        ):
            item["latest_decision_request_id"] = row["request_id"]
            item["reported_verdict"] = row["verdict"]
    for item in result.values():
        item["status"] = (
            "independent_decision_recorded"
            if item["latest_decision_request_id"] is not None
            else "independent_review_pending"
            if item["latest_request_status"]
            in {"queued", "running", "cancelling", "reconciling", "waiting_input"}
            else "review_attempt_without_decision"
        )
    return result


def author_origin(conn, project_id, finding):
    """Resolve the original committed writer operation to its actual bound attempt."""
    rows = conn.execute(
        """SELECT a.id AS attempt_id,a.run_id,r.actor_id,r.context_version,a.fence,
        a.status AS attempt_status,a.thread_id,a.turn_id,r.status AS run_status,
        o.request_hash AS producer_request_hash,o.result_json AS producer_result_json
        FROM tool_operations o JOIN tool_grants g ON g.id=o.grant_id
        JOIN runtime_attempts a ON a.id=g.runtime_attempt_id
        JOIN runtime_runs r ON r.id=a.run_id
        WHERE o.project_id=? AND o.task_id=? AND o.kind='finding.record'
        AND json_extract(o.result_json,'$.finding_id')=? AND g.runtime_bound=1
        AND g.project_id=o.project_id AND g.task_id=o.task_id
        AND r.project_id=o.project_id AND r.task_id=o.task_id
        AND r.actor_id=g.agent_id AND g.agent_id=?
        AND r.context_version=g.context_version""",
        (project_id, finding["task_id"], finding["id"], finding["agent_id"]),
    ).fetchall()
    if len(rows) != 1 or rows[0]["thread_id"] is None or rows[0]["turn_id"] is None:
        return None
    author = dict(rows[0])
    result = json.loads(author.pop("producer_result_json"))
    request_hash = author.pop("producer_request_hash")
    evidence = [
        dict(row)
        for row in conn.execute(
            "SELECT source_id,quote FROM finding_sources WHERE project_id=? AND finding_id=? ORDER BY rowid",
            (project_id, finding["id"]),
        )
    ]
    if "finding_version_sha256" in result or "finding_version_schema" in result:
        try:
            verified = result.get("finding_version_schema") == 1 and result.get(
                "finding_version_sha256"
            ) == finding_version(finding, evidence)
        except (ValueError, TypeError, KeyError):
            verified = False
        proof = "committed_finding_version"
    else:
        # A historical packet must match exactly; citation order is never guessed.
        packet = {
            "project_id": project_id,
            "task_id": finding["task_id"],
            "agent_id": finding["agent_id"],
            "context_version": author["context_version"],
            "kind": "finding.record",
            "intent": {
                "topic": finding["topic"],
                "content": finding["content"],
                "finding_type": finding["finding_type"],
                "evidence": evidence,
            },
        }
        verified = digest(packet) == request_hash
        proof = "historical_writer_intent"
    if not verified:
        return None
    return {**author, "version_proof": proof}


def finding_subject(conn, project_id, finding_id):
    """Snapshot the full claim, exact citations, verified sources and linked reports.

    The caller owns the SQL read/write transaction. Capture is complete within a one
    MiB serialized snapshot budget: oversized subjects fail rather than omit evidence.
    Source text is hashed and quoted against, but is not duplicated into the snapshot.
    """
    positive_id(project_id)
    positive_id(finding_id)
    row = conn.execute(
        "SELECT * FROM findings WHERE project_id=? AND id=?", (project_id, finding_id)
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Finding not found in this project")
    finding = dict(row)
    # An encoder cache is derived retrieval state, not part of a scientific claim.
    finding.pop("embedding", None)
    evidence = []
    rows = conn.execute(
        """SELECT fs.quote,s.* FROM finding_sources fs JOIN research_sources s
        ON s.id=fs.source_id AND s.project_id=fs.project_id
        WHERE fs.project_id=? AND fs.finding_id=? ORDER BY s.id,fs.quote LIMIT 201""",
        (project_id, finding_id),
    ).fetchall()
    if len(rows) > 200:
        raise ResearchInputError("Review subject exceeds 200 saved quotations")
    expected = conn.execute(
        "SELECT COUNT(*) FROM finding_sources WHERE project_id=? AND finding_id=?",
        (project_id, finding_id),
    ).fetchone()[0]
    if len(rows) != expected:
        raise InvalidEvidence(
            "Review citation has a missing or foreign captured source"
        )
    for row in rows:
        source = dict(row)
        quote = source.pop("quote")
        content = source["content"]
        source, _ = source_version(source)
        if not isinstance(quote, str) or not quote or quote not in content:
            raise InvalidEvidence("Review citation does not match the captured source")
        evidence.append({"quote": quote, "source": source})
    reports = []
    rows = conn.execute(
        """SELECT a.id,a.project_id,a.task_id,a.content,r.title,r.report_type,r.status,r.content_sha256
        FROM report_findings rf JOIN artifacts a ON a.id=rf.artifact_id AND a.project_id=rf.project_id
        JOIN research_reports r ON r.artifact_id=a.id WHERE rf.project_id=? AND rf.finding_id=? ORDER BY a.id LIMIT 21""",
        (project_id, finding_id),
    ).fetchall()
    if len(rows) > 20:
        raise ResearchInputError("Review subject exceeds 20 linked reports")
    expected = conn.execute(
        "SELECT COUNT(*) FROM report_findings WHERE project_id=? AND finding_id=?",
        (project_id, finding_id),
    ).fetchone()[0]
    if len(rows) != expected:
        raise InvalidEvidence("Review report link has a missing or foreign report")
    for row in rows:
        report = dict(row)
        report.pop(
            "status"
        )  # Administrative acceptance does not change reviewed content.
        if (
            hashlib.sha256(report["content"].encode()).hexdigest()
            != report["content_sha256"]
        ):
            raise InvalidEvidence("Linked report hash differs from its saved text")
        report["finding_ids"] = [
            r[0]
            for r in conn.execute(
                "SELECT finding_id FROM report_findings WHERE project_id=? AND artifact_id=? ORDER BY finding_id",
                (project_id, report["id"]),
            )
        ]
        reports.append(report)
    origin = author_origin(conn, project_id, finding)
    author = (
        {
            key: value
            for key, value in origin.items()
            if key not in {"attempt_status", "run_status"}
        }
        if origin is not None
        else None
    )
    snapshot = {
        "schema_version": 1,
        "finding": finding,
        "evidence": evidence,
        "reports": reports,
        "author": author,
    }
    if len(canonical(snapshot).encode()) > 1048576:
        raise ResearchInputError(
            "Complete review subject exceeds the one MiB snapshot budget"
        )
    reason = (
        "author_origin_unknown"
        if author is None
        else "author_attempt_unclosed"
        if origin["attempt_status"] != "finished"
        else None
    )
    return {
        "subject_sha256": digest(snapshot),
        "snapshot": snapshot,
        "reviewable": reason is None,
        "reason": reason,
    }


def scope_request(conn, scope):
    """Resolve a grant to its original admitted reviewer, never from its role name."""
    row = conn.execute(
        """SELECT q.*,a.id AS reviewer_attempt_id,a.fence AS reviewer_fence,r.actor_id AS reviewer_actor_id,
        r.execution_kind FROM tool_grants g JOIN runtime_attempts a ON a.id=g.runtime_attempt_id
        JOIN runtime_runs r ON r.id=a.run_id JOIN finding_review_requests q ON q.run_id=r.id
        WHERE g.id=? AND g.runtime_bound=1""",
        (scope.grant_id,),
    ).fetchone()
    if row is None:
        return None
    request = dict(row)
    if (
        (
            request["project_id"],
            request["task_id"],
            request["context_version"],
            request["reviewer_actor_id"],
        )
        != (scope.project_id, scope.task_id, scope.context_version, scope.agent_id)
        or request["execution_kind"] != "finding_review"
        or request["reviewer_attempt_id"] == request["author_attempt_id"]
        or request["reviewer_actor_id"] == request["author_actor_id"]
        or request["run_id"] == request["author_run_id"]
    ):
        raise ResearchForbidden(
            "Review grant does not identify an independent admitted attempt"
        )
    return request


def verify_current(conn, request):
    """Reject a changed review subject before using current material or deciding."""
    current = finding_subject(conn, request["project_id"], request["finding_id"])
    if (
        not current["reviewable"]
        or current["subject_sha256"] != request["subject_sha256"]
    ):
        raise OperationConflict(
            "Review subject changed; inspect and admit its current version"
        )
    return current


def _review_context(conn, task_id):
    """Read the actual task context without inferring a new version."""
    row = conn.execute(
        "SELECT version FROM task_contexts WHERE task_id=?", (task_id,)
    ).fetchone()
    return row[0] if row is not None else 1


def _existing_review_task(conn, project_id, task_id):
    """Keep review projections bound to their finding's actual project/task."""
    if (
        conn.execute(
            "SELECT 1 FROM tasks WHERE project_id=? AND id=?", (project_id, task_id)
        ).fetchone()
        is None
    ):
        raise ResearchNotFound("Task not found in this project")


def finding_review_state(conn, project_id, finding_id, *, after_id=0, limit=20):
    """Inspect an observed subject and page actual review attempts without auto-validation."""
    if (
        type(after_id) is not int
        or after_id < 0
        or type(limit) is not int
        or not 1 <= limit <= 50
    ):
        raise ResearchInputError(
            "Review history requires a nonnegative cursor and limit 1–50"
        )
    subject = finding_subject(conn, project_id, finding_id)
    task_id = subject["snapshot"]["finding"]["task_id"]
    _existing_review_task(conn, project_id, task_id)
    task = conn.execute(
        "SELECT status,type FROM tasks WHERE project_id=? AND id=?",
        (project_id, task_id),
    ).fetchone()
    context = _review_context(conn, task_id)
    rows = conn.execute(
        """SELECT q.id AS request_id,q.run_id,q.subject_sha256,q.context_version,q.created_at,
        r.status,r.operation_key,r.actor_id AS reviewer_actor_id,d.id AS decision_id,d.verdict,d.reviewer_attempt_id
        FROM finding_review_requests q JOIN runtime_runs r ON r.id=q.run_id
        LEFT JOIN finding_review_decisions d ON d.run_id=q.run_id
        WHERE q.project_id=? AND q.finding_id=? AND q.id>? ORDER BY q.id LIMIT ?""",
        (project_id, finding_id, after_id, limit + 1),
    ).fetchall()
    items = []
    cache = {}
    for row in rows[:limit]:
        subject_current = (
            row["subject_sha256"] == subject["subject_sha256"]
            and row["context_version"] == context
        )
        evidence_current = decision_evidence_current(
            conn, project_id, row["decision_id"], cache=cache
        )
        items.append(
            {
                **dict(row),
                "subject_current": subject_current and evidence_current,
                "currentness_reason": "review_subject_changed"
                if not subject_current
                else "review_evidence_changed"
                if not evidence_current
                else None,
            }
        )
    active = conn.execute(
        """SELECT q.id AS request_id,q.run_id,q.finding_id,r.status,r.operation_key,d.id AS decision_id FROM finding_review_requests q
    JOIN runtime_runs r ON r.id=q.run_id LEFT JOIN finding_review_decisions d ON d.run_id=q.run_id
            WHERE q.project_id=? AND q.task_id=? AND r.status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')
    ORDER BY q.id DESC LIMIT 1""",
        (project_id, task_id),
    ).fetchone()
    latest = conn.execute(
        """SELECT q.id AS request_id,q.run_id,q.finding_id,r.status,r.operation_key,d.id AS decision_id
        FROM finding_review_requests q JOIN runtime_runs r ON r.id=q.run_id LEFT JOIN finding_review_decisions d ON d.run_id=q.run_id
        WHERE q.project_id=? AND q.finding_id=? ORDER BY q.id DESC LIMIT 1""",
        (project_id, finding_id),
    ).fetchone()
    task_active = (
        task["status"] not in ("done", "cancelled", "failed")
        and task["type"] == "research"
    )
    return {
        "project_id": project_id,
        "task_id": task_id,
        "finding_id": finding_id,
        "context_version": context,
        "subject_sha256": subject["subject_sha256"],
        "reviewable": subject["reviewable"] and task_active,
        "reason": subject["reason"]
        if not subject["reviewable"]
        else None
        if task_active
        else "task_not_active_research",
        "author": subject["snapshot"]["author"],
        "source_count": len(
            {e["source"]["id"] for e in subject["snapshot"]["evidence"]}
        ),
        "report_count": len(subject["snapshot"]["reports"]),
        "scientific_confidence": None,
        "active_review": dict(active) if active is not None else None,
        "latest_review": dict(latest) if latest is not None else None,
        "reviews": {
            "items": items,
            "next_after_id": items[-1]["request_id"] if len(rows) > limit else None,
        },
    }


def finding_review_detail(conn, project_id, request_id):
    """Read an attributed bounded decision, preserving stale and partial assessments."""
    positive_id(project_id)
    positive_id(request_id)
    row = conn.execute(
        """SELECT q.*,r.status,r.operation_key,r.actor_id AS reviewer_actor_id,d.id AS decision_id,d.decision_json,d.reviewer_attempt_id,d.reviewer_fence
        FROM finding_review_requests q JOIN runtime_runs r ON r.id=q.run_id LEFT JOIN finding_review_decisions d ON d.run_id=q.run_id
        WHERE q.project_id=? AND q.id=?""",
        (project_id, request_id),
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Review request not found in this project")
    try:
        current = finding_subject(conn, project_id, row["finding_id"])
        subject_current = row["subject_sha256"] == current["subject_sha256"] and row[
            "context_version"
        ] == _review_context(conn, row["task_id"])
    except (ResearchInputError, ResearchNotFound):
        subject_current = None
    evidence_current = decision_evidence_current(conn, project_id, row["decision_id"])
    decision = json.loads(row["decision_json"]) if row["decision_json"] else None
    if decision is not None:
        sources = {
            r["source_id"]: json.loads(r["metadata_json"])
            for r in conn.execute(
                "SELECT source_id,metadata_json FROM finding_review_evidence WHERE project_id=? AND decision_id=?",
                (project_id, row["decision_id"]),
            )
        }
        decision["verified_evidence"] = [
            {**ref, "source": sources.get(ref["source_id"])}
            for ref in decision["verified_evidence"]
        ]
    return {
        "project_id": project_id,
        "task_id": row["task_id"],
        "request_id": request_id,
        "run_id": row["run_id"],
        "operation_key": row["operation_key"],
        "finding_id": row["finding_id"],
        "subject_sha256": row["subject_sha256"],
        "subject_current": None
        if subject_current is None
        else subject_current and evidence_current,
        "currentness_reason": "review_subject_unavailable"
        if subject_current is None
        else "review_subject_changed"
        if not subject_current
        else "review_evidence_changed"
        if not evidence_current
        else None,
        "context_version": row["context_version"],
        "status": row["status"],
        "reviewer_actor_id": row["reviewer_actor_id"],
        "reviewer_attempt_id": row["reviewer_attempt_id"],
        "reviewer_fence": row["reviewer_fence"],
        "author_attempt_id": row["author_attempt_id"],
        "decision_id": row["decision_id"],
        "decision": decision,
        "scientific_confidence": None,
        "review_scope": "reported_checks_only",
    }


def read_feedback(
    conn,
    project_id,
    finding_id,
    *,
    request_id=None,
    part="decision",
    after_id=0,
    limit=20,
    offset=0,
    max_chars=12000,
):
    """Project bounded attributed feedback on the caller's already-authorized SQL snapshot.

    The native caller must check its live findings.read grant in this same transaction;
    owner/retained host readers establish their own project boundary before calling.
    This projection never admits a review or upgrades a reader's authority.
    """
    from backend.knowledge.findings import window

    positive_id(project_id)
    positive_id(finding_id)
    if part not in ("decision", "subject"):
        raise ResearchInputError("Unknown review read part")
    if (
        conn.execute(
            "SELECT 1 FROM findings WHERE project_id=? AND id=?",
            (project_id, finding_id),
        ).fetchone()
        is None
    ):
        raise ResearchNotFound("Finding not found in this project")
    if request_id is None:
        if offset != 0 or part != "decision":
            raise ResearchInputError("Choose a review request before paging its text")
        return {
            "read_kind": "history",
            **finding_review_state(
                conn, project_id, finding_id, after_id=after_id, limit=limit
            ),
        }
    detail = finding_review_detail(conn, project_id, request_id)
    if detail["finding_id"] != finding_id:
        raise ResearchNotFound("Review request does not belong to this finding")
    value = detail.pop("decision")
    if part == "subject":
        text = conn.execute(
            "SELECT snapshot_json FROM finding_review_requests WHERE project_id=? AND id=?",
            (project_id, request_id),
        ).fetchone()[0]
        available = True
    else:
        text = canonical(value) if value is not None else ""
        available = value is not None
    return {
        **detail,
        "read_kind": part,
        "available": available,
        **window(text, offset, max_chars),
    }
