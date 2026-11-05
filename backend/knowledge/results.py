"""Immutable explicitly delivered research reports and distinct version-bound owner decisions.

A writer selects its final deliverables. Native turn completion only closes that
proposal; an owner action accepts an exact version without promoting scientific
certainty or authorizing code publication. Callers own authorization/transactions.
"""

import hashlib
import json

from backend.knowledge.reviews import author_origin, canonical, digest, source_version
from backend.research.models import (
    InvalidEvidence,
    OperationConflict,
    ResearchForbidden,
    ResearchInputError,
    ResearchNotFound,
    ResultDraft,
    SourceTooLarge,
    positive_id,
)
from backend.runtime.task_profiles import DOCUMENTARY_TASK_TYPES

MAX_BYTES = 2 * 1024**2
MAX_REFERENCES = 1000
MAX_SOURCES = 200


def _check_size(conn, table, columns, where, args, limit):
    """Preflight SQLite byte lengths before loading bounded evidence into Python.

    Table, columns and predicate are internal SQL constants; only values come
    from callers. Canonical JSON expansion is checked again before persistence.
    """
    expression = "+".join(
        f"coalesce(length(cast({name} AS BLOB)),0)" for name in columns
    )
    row = conn.execute(
        f"SELECT {expression} FROM {table} WHERE {where}", args
    ).fetchone()
    if row is not None and row[0] > limit:
        raise SourceTooLarge(
            "Complete delivered evidence exceeds its byte budget; no content was omitted"
        )


def author_scope(conn, scope):
    """Require a real current research author attempt, never a reviewer-looking role name."""
    row = conn.execute(
        """SELECT r.*,a.id AS attempt_id,a.fence AS attempt_fence,
        a.thread_id,a.turn_id,a.status AS attempt_status FROM tool_grants g
        JOIN runtime_attempts a ON a.id=g.runtime_attempt_id JOIN runtime_runs r ON r.id=a.run_id
        WHERE g.id=? AND g.runtime_bound=1 AND g.project_id=? AND g.task_id=?
        AND g.agent_id=? AND g.context_version=?""",
        (
            scope.grant_id,
            scope.project_id,
            scope.task_id,
            scope.agent_id,
            scope.context_version,
        ),
    ).fetchone()
    if (
        row is None
        or row["execution_kind"] != "research"
        or row["current_attempt_id"] != row["attempt_id"]
        or row["status"] != "running"
        or row["attempt_status"] != "running"
        or row["fence"] != row["attempt_fence"]
        or not row["thread_id"]
        or not row["turn_id"]
    ):
        raise ResearchForbidden(
            "A current admitted research author is required to deliver a result"
        )
    return row


def _run(conn, project_id, run_id):
    """Read one actual run/attempt scope without inferring a project from its id."""
    positive_id(project_id)
    row = conn.execute(
        """SELECT r.*,a.id AS attempt_id,a.status AS attempt_status,
        a.thread_id,a.turn_id,a.native_result_json FROM runtime_runs r
        LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id
        WHERE r.project_id=? AND r.id=?""",
        (project_id, run_id),
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Run not found in this project")
    return row


def _report(conn, run, report_id):
    """Verify selected report bytes and original writer intent before attributing its delivery."""
    _check_size(
        conn,
        "artifacts",
        ("content",),
        "project_id=? AND task_id=? AND id=?",
        (run["project_id"], run["task_id"], report_id),
        501300,
    )
    row = conn.execute(
        """SELECT a.id,a.project_id,a.task_id,a.type,a.content,r.title,
        r.report_type,r.content_sha256 FROM artifacts a JOIN research_reports r ON r.artifact_id=a.id
        WHERE a.project_id=? AND a.task_id=? AND a.id=?""",
        (run["project_id"], run["task_id"], report_id),
    ).fetchone()
    if row is None or row["type"] != "report":
        raise ResearchNotFound("Delivered report is not in this project/task")
    if len(row["content"].encode()) > 500000 + 1300:
        raise SourceTooLarge("Delivered report exceeds the native report budget")
    if hashlib.sha256(row["content"].encode()).hexdigest() != row["content_sha256"]:
        raise InvalidEvidence("Delivered report body does not match its saved hash")
    prefix = f"# {row['title']}\n\n"
    if not row["content"].startswith(prefix):
        raise OperationConflict(
            "Delivered report no longer matches its original writer version"
        )
    count = conn.execute(
        "SELECT count(*) FROM report_findings WHERE project_id=? AND artifact_id=?",
        (run["project_id"], report_id),
    ).fetchone()[0]
    if not 1 <= count <= 50:
        raise InvalidEvidence("A delivered report needs 1–50 linked findings")
    finding_ids = [
        r[0]
        for r in conn.execute(
            "SELECT finding_id FROM report_findings WHERE project_id=? AND artifact_id=? ORDER BY rowid",
            (run["project_id"], report_id),
        )
    ]
    rows = conn.execute(
        """SELECT o.operation_key,o.request_hash,o.result_json,o.kind,o.grant_id,g.agent_id,g.context_version,
        a.id AS attempt_id,a.run_id FROM tool_operations o JOIN tool_grants g ON g.id=o.grant_id
        JOIN runtime_attempts a ON a.id=g.runtime_attempt_id
        WHERE o.project_id=? AND o.task_id=? AND o.kind IN ('report.write','investigation.summary') AND g.runtime_bound=1
        AND json_extract(o.result_json,'$.artifact_id')=? AND a.id=? AND a.run_id=? LIMIT 2""",
        (
            run["project_id"],
            run["task_id"],
            report_id,
            run["current_attempt_id"],
            run["id"],
        ),
    ).fetchall()
    if len(rows) != 1:
        raise ResearchForbidden(
            "Select reports actually written by this admitted author attempt"
        )
    producer = rows[0]
    investigation = None
    task_type = conn.execute("SELECT type FROM tasks WHERE project_id=? AND id=?", (run["project_id"], run["task_id"])).fetchone()[0]
    if producer["kind"] == "investigation.summary" or task_type == "investigation":
        from backend.research.investigation import verified_summary

        investigation = verified_summary(conn, run, report_id, producer, row["content"])
    packet = {
        "project_id": run["project_id"],
        "task_id": run["task_id"],
        "agent_id": producer["agent_id"],
        "context_version": producer["context_version"],
        "kind": producer["kind"],
        "intent": investigation if investigation is not None else {
            "title": row["title"],
            "content": row["content"][len(prefix) :],
            "finding_ids": finding_ids,
            "report_type": row["report_type"],
        },
    }
    if (
        producer["agent_id"] != run["actor_id"]
        or producer["context_version"] != run["context_version"]
        or digest(packet) != producer["request_hash"]
    ):
        raise OperationConflict(
            "Delivered report no longer matches its committed writer intent"
        )
    return {
        "artifact_id": report_id,
        "title": row["title"],
        "report_type": row["report_type"],
        "content": row["content"],
        "content_sha256": row["content_sha256"],
        "finding_ids": finding_ids,
        **({"investigation": investigation} if investigation is not None else {}),
        "producer": {
            "run_id": producer["run_id"],
            "attempt_id": producer["attempt_id"],
            "actor_id": producer["agent_id"],
            "operation_key": producer["operation_key"],
            "writer_intent_sha256": producer["request_hash"],
        },
    }


def snapshot(conn, run, draft):
    """Capture only selected complete reports and their exact finding/source dependencies within a byte bound."""
    if run["execution_kind"] != "research":
        raise ResearchForbidden(
            "A finding-review attempt cannot deliver an author result"
        )
    _check_size(
        conn,
        "tasks",
        (
            "title",
            "description",
            "acceptance_criteria",
            "context_json",
            "assigned_to",
            "reviewer",
            "branch_name",
        ),
        "project_id=? AND id=?",
        (run["project_id"], run["task_id"]),
        MAX_BYTES,
    )
    task = conn.execute(
        """SELECT title,description,type,acceptance_criteria,context_json,priority,
        estimated_complexity,branch_name,assigned_to,reviewer,epic_id,milestone_id,parent_task_id
        FROM tasks WHERE project_id=? AND id=?""",
        (run["project_id"], run["task_id"]),
    ).fetchone()
    if task is None or task["type"] not in DOCUMENTARY_TASK_TYPES:
        raise ResearchForbidden(
            "Only native documentary report delivery is implemented for this runtime"
        )
    size = 0

    def bounded(value):
        """Accumulate complete canonical pieces and fail before retaining an oversized graph."""
        nonlocal size
        size += len(canonical(value).encode())
        if size > MAX_BYTES:
            raise SourceTooLarge(
                "Complete delivered result exceeds 2 MiB; reduce the selected reports, no content was omitted"
            )
        return value

    task = bounded(dict(task))
    reports = [bounded(_report(conn, run, rid)) for rid in draft.report_ids]
    finding_ids = sorted({fid for report in reports for fid in report["finding_ids"]})
    if len(finding_ids) > 200:
        raise SourceTooLarge(
            "Delivered reports reference more than 200 findings; no references were omitted"
        )
    findings = []
    sources = {}
    reference_count = 0
    for fid in finding_ids:
        _check_size(
            conn,
            "findings",
            ("topic", "content", "sources_json", "validation_method", "agent_id"),
            "project_id=? AND id=?",
            (run["project_id"], fid),
            MAX_BYTES - size,
        )
        ref_size = conn.execute(
            "SELECT count(*),coalesce(sum(length(cast(quote AS BLOB))),0) FROM finding_sources WHERE project_id=? AND finding_id=?",
            (run["project_id"], fid),
        ).fetchone()
        reference_count += ref_size[0]
        if (
            reference_count > MAX_REFERENCES
            or ref_size[0] > 200
            or ref_size[1] > MAX_BYTES - size
        ):
            raise SourceTooLarge(
                "Delivered quotations exceed the complete evidence budget; reduce the selected reports"
            )
        row = conn.execute(
            "SELECT id,project_id,task_id,agent_run_id,topic,content,sources_json,confidence,agent_id,status,validation_method,reproducibility_score,finding_type,artifact_id,wiki_page_id,created_at FROM findings WHERE project_id=? AND id=?",
            (run["project_id"], fid),
        ).fetchone()
        if row is None:
            raise InvalidEvidence("Delivered report references a missing finding")
        finding = dict(row)
        refs = conn.execute(
            "SELECT source_id,quote FROM finding_sources WHERE project_id=? AND finding_id=? ORDER BY rowid",
            (run["project_id"], fid),
        ).fetchall()
        if not refs or len(refs) > 200:
            raise InvalidEvidence(
                "Delivered finding needs complete bounded captured quotations"
            )
        for ref in refs:
            if ref["source_id"] in sources:
                source = sources[ref["source_id"]]["source"]
            else:
                if len(sources) >= MAX_SOURCES:
                    raise SourceTooLarge(
                        "Delivered sources exceed the complete evidence budget"
                    )
                _check_size(
                    conn,
                    "research_sources",
                    ("content", "provenance_json", "title", "locator"),
                    "project_id=? AND id=?",
                    (run["project_id"], ref["source_id"]),
                    MAX_BYTES - size,
                )
                source = conn.execute(
                    "SELECT * FROM research_sources WHERE project_id=? AND id=?",
                    (run["project_id"], ref["source_id"]),
                ).fetchone()
            if source is None:
                raise InvalidEvidence("Delivered quotation lost its captured source")
            if ref["quote"] not in source["content"]:
                raise InvalidEvidence(
                    "Delivered quotation no longer matches its captured source"
                )
            if ref["source_id"] not in sources:
                metadata, metadata_sha256 = source_version(dict(source))
                sources[ref["source_id"]] = bounded(
                    {
                        "source": {**metadata, "content": source["content"]},
                        "metadata_sha256": metadata_sha256,
                    }
                )
        origin = author_origin(conn, run["project_id"], finding)
        if origin is not None:
            origin = {
                key: value
                for key, value in origin.items()
                if key not in ("attempt_status", "run_status")
            }
        findings.append(
            bounded(
                {
                    "finding": finding,
                    "evidence": [dict(ref) for ref in refs],
                    "author": origin,
                }
            )
        )
    value = {
        "schema_version": 1,
        "kind": "research_reports",
        "scope": {
            "project_id": run["project_id"],
            "task_id": run["task_id"],
            "run_id": run["id"],
            "attempt_id": run["current_attempt_id"],
            "actor_id": run["actor_id"],
            "context_version": run["context_version"],
            "fence": run["fence"],
        },
        "task": task,
        "report_ids": list(draft.report_ids),
        "reports": reports,
        "findings": findings,
        "sources": [sources[key] for key in sorted(sources)],
        "summary": draft.summary,
        "limitations": list(draft.limitations),
        "scientific_confidence": None,
        "acceptance_scope": "owner acceptance of research reports; not code or publication authorization",
    }
    if len(canonical(value).encode()) > MAX_BYTES:
        raise SourceTooLarge(
            "Complete delivered result exceeds 2 MiB; no partial candidate was saved"
        )
    return value


def record_proposal(conn, scope, draft, *, now):
    """Commit an immutable explicit delivery in the caller's live-author write transaction."""
    run = author_scope(conn, scope)
    value = snapshot(conn, run, draft)
    fingerprint = digest(value)
    cursor = conn.execute(
        """INSERT INTO runtime_result_proposals(project_id,task_id,run_id,attempt_id,
        fence,context_version,kind,subject_sha256,snapshot_json,created_at) VALUES(?,?,?,?,?,?,'research_reports',?,?,?)""",
        (
            scope.project_id,
            scope.task_id,
            run["id"],
            run["current_attempt_id"],
            run["fence"],
            scope.context_version,
            fingerprint,
            canonical(value),
            now,
        ),
    )
    return {
        "candidate_id": cursor.lastrowid,
        "run_id": run["id"],
        "candidate_sha256": fingerprint,
        "kind": "research_reports",
        "status": "proposed",
        "task_accepted": False,
        "report_ids": list(draft.report_ids),
    }


def result_state(conn, project_id, run_id):
    """Inspect explicit delivery and eligibility without deriving acceptance from native completion prose."""
    run = _run(conn, project_id, run_id)
    row = conn.execute(
        "SELECT * FROM runtime_result_proposals WHERE project_id=? AND run_id=? ORDER BY id DESC LIMIT 1",
        (project_id, run_id),
    ).fetchone()
    base = {
        "project_id": project_id,
        "task_id": run["task_id"],
        "run_id": run_id,
        "candidate": None,
        "candidate_current": None,
        "eligible": False,
        "reason": "no_explicit_delivery",
        "acceptance": None,
        "acceptance_current": False,
        "reviews": None,
        "review_sha256": None,
        "review_issues": [],
        "requires_acknowledgement": False,
        "active_work": [],
    }
    if row is None:
        return base
    value = json.loads(row["snapshot_json"])
    candidate = {
        "candidate_id": row["id"],
        "candidate_sha256": row["subject_sha256"],
        "kind": row["kind"],
        "scope": value["scope"],
        "summary": value["summary"],
        "limitations": value["limitations"],
        "reports": [
            {
                key: report[key]
                for key in (
                    "artifact_id",
                    "title",
                    "report_type",
                    "content_sha256",
                    "finding_ids",
                )
            }
            for report in value["reports"]
        ],
        "finding_ids": [item["finding"]["id"] for item in value["findings"]],
        "scientific_confidence": None,
    }
    current = None
    reason = None
    context = conn.execute(
        "SELECT version FROM task_contexts WHERE task_id=?", (run["task_id"],)
    ).fetchone()
    if row["attempt_id"] != run["current_attempt_id"] or row["fence"] != run["fence"]:
        current = False
        reason = "candidate_attempt_changed"
    elif row["context_version"] != (context[0] if context else 1):
        current = False
        reason = "candidate_context_changed"
    else:
        try:
            rebuilt = snapshot(
                conn,
                run,
                ResultDraft(
                    tuple(value["report_ids"]),
                    value["summary"],
                    tuple(value["limitations"]),
                ),
            )
            current = digest(rebuilt) == row["subject_sha256"]
            if not current:
                reason = "candidate_dependencies_changed"
        except OperationConflict:
            current = False
            reason = "candidate_dependencies_changed"
        except (ResearchInputError, ResearchNotFound, ResearchForbidden):
            current = None
            reason = "candidate_dependencies_unverifiable"
    native = (
        json.loads(run["native_result_json"]) if run["native_result_json"] else None
    )
    closed = (
        run["attempt_status"] == "finished"
        and native is not None
        and native.get("native_status") == "completed"
    )
    task = conn.execute(
        "SELECT status FROM tasks WHERE project_id=? AND id=?",
        (project_id, run["task_id"]),
    ).fetchone()
    other = conn.execute(
        """SELECT r.id,r.status,a.status AS attempt_status FROM runtime_runs r
        LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id WHERE r.project_id=? AND r.task_id=? AND r.id!=?
        AND (r.status IN ('queued','running','cancelling','reconciling','waiting_input')
        OR (r.status='needs_review' AND coalesce(a.status,'missing')!='finished'))""",
        (project_id, run["task_id"], run_id),
    ).fetchall()
    live = conn.execute(
        """SELECT p.id FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id JOIN runtime_runs r ON r.id=a.run_id
        WHERE r.project_id=? AND r.task_id=? AND p.state!='closed' LIMIT 1""",
        (project_id, run["task_id"]),
    ).fetchone()
    gate = review_gate(conn, project_id, run["task_id"], candidate["finding_ids"])
    acceptance = acceptance_record(conn, project_id, run_id)
    eligible = (
        current is True
        and run["status"] == "needs_review"
        and closed
        and task["status"] not in ("done", "failed", "cancelled")
        and not other
        and live is None
    )
    latest = conn.execute(
        "SELECT id FROM runtime_result_acceptances WHERE project_id=? AND task_id=? ORDER BY id DESC LIMIT 1",
        (project_id, run["task_id"]),
    ).fetchone()
    acceptance_current = bool(
        acceptance
        and latest
        and latest[0] == acceptance["acceptance_id"]
        and current is True
        and run["status"] == "accepted"
        and task["status"] == "done"
        and acceptance["review_sha256"] == gate["sha256"]
    )
    if reason is None and not eligible:
        reason = (
            "already_accepted"
            if acceptance
            else "other_work_unreconciled"
            if other or live
            else "task_closed"
            if task["status"] in ("done", "failed", "cancelled")
            else "author_not_closed"
            if not closed
            else "run_not_eligible"
        )
    return {
        **base,
        "candidate": candidate,
        "candidate_current": current,
        "eligible": eligible,
        "reason": reason,
        "acceptance": acceptance,
        "acceptance_current": acceptance_current,
        "reviews": gate,
        "review_sha256": gate["sha256"],
        "review_issues": gate["issues"],
        "requires_acknowledgement": bool(gate["issues"]),
        "active_work": [dict(item) for item in other],
    }


def review_gate(conn, project_id, task_id, finding_ids):
    """Describe actual finding reviews and unresolved limits without certifying the whole report."""
    from backend.knowledge.reviews import finding_review_detail

    items = []
    issues = []
    for finding_id in finding_ids:
        row = conn.execute(
            "SELECT id FROM finding_review_requests WHERE project_id=? AND finding_id=? ORDER BY id DESC LIMIT 1",
            (project_id, finding_id),
        ).fetchone()
        if row is None:
            items.append(
                {"finding_id": finding_id, "request_id": None, "decision_id": None}
            )
            issues.append({"finding_id": finding_id, "reason": "no_independent_review"})
            continue
        detail = finding_review_detail(conn, project_id, row["id"])
        decision = detail["decision"]
        item = {
            "finding_id": finding_id,
            "request_id": row["id"],
            "decision_id": detail["decision_id"],
            "subject_sha256": detail["subject_sha256"],
            "subject_current": detail["subject_current"],
            "currentness_reason": detail["currentness_reason"],
            "reviewer_actor_id": detail["reviewer_actor_id"],
            "reviewer_attempt_id": detail["reviewer_attempt_id"],
            "decision_sha256": digest(decision),
            "verdict": decision["verdict"] if decision else None,
            "rationale_preview": decision["rationale"][:800] if decision else None,
        }
        items.append(item)
        if decision is None:
            reason = "review_without_decision"
        elif detail["subject_current"] is not True:
            reason = "review_outdated_or_unverifiable"
        elif decision["verdict"] != "supported":
            reason = "review_reports_limits_or_changes"
        else:
            reason = None
        if reason:
            issues.append(
                {"finding_id": finding_id, "request_id": row["id"], "reason": reason}
            )
    return {
        "scope": "referenced_findings_only_not_whole_report_validation",
        "items": items,
        "issues": issues,
        "sha256": digest(items),
    }


def report_window(
    conn, project_id, run_id, candidate_id, report_id, *, offset=0, max_chars=12000
):
    """Read the frozen delivered report, even when current artifacts have since changed."""
    _run(conn, project_id, run_id)
    positive_id(candidate_id)
    positive_id(report_id)
    if (
        type(offset) is not int
        or offset < 0
        or type(max_chars) is not int
        or not 1 <= max_chars <= 20000
    ):
        raise ResearchInputError(
            "Use a nonnegative offset and max_chars between 1 and 20000"
        )
    row = conn.execute(
        "SELECT snapshot_json,subject_sha256 FROM runtime_result_proposals WHERE project_id=? AND run_id=? AND id=?",
        (project_id, run_id, candidate_id),
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Delivered candidate not found in this project/run")
    value = json.loads(row["snapshot_json"])
    if digest(value) != row["subject_sha256"]:
        raise InvalidEvidence("Delivered snapshot no longer matches its immutable hash")
    report = next(
        (item for item in value["reports"] if item["artifact_id"] == report_id), None
    )
    if report is None:
        raise ResearchNotFound("Report was not selected in this delivered candidate")
    content = report["content"]
    if hashlib.sha256(content.encode()).hexdigest() != report["content_sha256"]:
        raise InvalidEvidence("Frozen report does not match its saved hash")
    end = min(len(content), offset + max_chars)
    return {
        "project_id": project_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "candidate_sha256": row["subject_sha256"],
        "artifact_id": report_id,
        "title": report["title"],
        "content_sha256": report["content_sha256"],
        "content": content[offset:end],
        "offset": offset,
        "total_chars": len(content),
        "next_offset": end if end < len(content) else None,
        "source": "immutable_delivered_snapshot",
        "finding_ids": report["finding_ids"],
    }


def acceptance_record(conn, project_id, run_id):
    """Return the immutable original owner receipt, not an assertion of present-day currentness."""
    row = conn.execute(
        "SELECT id,receipt_json FROM runtime_result_acceptances WHERE project_id=? AND run_id=?",
        (project_id, run_id),
    ).fetchone()
    return (
        {**json.loads(row["receipt_json"]), "acceptance_id": row["id"]} if row else None
    )


def accept_result(
    conn,
    project_id,
    run_id,
    *,
    operation_key,
    candidate_id,
    candidate_sha256,
    context_version,
    review_sha256,
    acknowledge_limits,
    note,
    now,
):
    """Atomically accept one observed research version by owner action, without publishing or science promotion."""
    from backend.research.models import bounded_text
    from backend.research.models import operation_key as validate_key

    positive_id(project_id)
    positive_id(candidate_id)
    positive_id(context_version)
    validate_key(operation_key)
    if type(acknowledge_limits) is not bool:
        raise ResearchInputError("Owner acknowledgement must be an explicit boolean")
    for value in (candidate_sha256, review_sha256):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ResearchInputError("An observed SHA-256 is required for acceptance")
    if note is not None:
        bounded_text(note, "owner acceptance note", 4000)
    intent = {
        "project_id": project_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "context_version": context_version,
        "review_sha256": review_sha256,
        "acknowledge_limits": acknowledge_limits,
        "note": note,
    }
    fingerprint = digest(intent)
    run = _run(conn, project_id, run_id)
    previous = conn.execute(
        "SELECT * FROM runtime_result_acceptances WHERE project_id=? AND task_id=? AND operation_key=?",
        (project_id, run["task_id"], operation_key),
    ).fetchone()
    if previous is not None:
        if previous["request_sha256"] != fingerprint:
            raise OperationConflict(
                "Owner operation key already names a different acceptance intent"
            )
        return {
            **json.loads(previous["receipt_json"]),
            "acceptance_id": previous["id"],
        }, False
    state = result_state(conn, project_id, run_id)
    if state["acceptance"] is not None:
        raise OperationConflict(
            "This run already has an owner acceptance; inspect its original receipt"
        )
    if not state["eligible"]:
        raise OperationConflict(
            "Result is not eligible for acceptance: " + str(state["reason"])
        )
    candidate = state["candidate"]
    if (
        candidate["candidate_id"],
        candidate["candidate_sha256"],
        candidate["scope"]["context_version"],
        state["review_sha256"],
    ) != (candidate_id, candidate_sha256, context_version, review_sha256):
        raise OperationConflict(
            "Delivered version, task context or review changed since the owner observation"
        )
    if state["requires_acknowledgement"] and not acknowledge_limits:
        raise OperationConflict(
            "Acknowledge the displayed absence or limitations of independent review before accepting"
        )
    receipt = {
        "project_id": project_id,
        "task_id": state["task_id"],
        "run_id": run_id,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "context_version": context_version,
        "review_sha256": review_sha256,
        "operation_key": operation_key,
        "actor_source": "paired_owner_action",
        "owner_note": note,
        "acknowledged_limits": acknowledge_limits,
        "accepted_at": now,
        "task_accepted": True,
        "acceptance_scope": "research_reports",
        "publication_performed": False,
        "scientific_confidence": None,
    }
    cursor = conn.execute(
        """INSERT INTO runtime_result_acceptances(project_id,task_id,run_id,proposal_id,
        operation_key,request_sha256,subject_sha256,review_sha256,review_json,owner_note,
        acknowledged_limits,actor_source,receipt_json,accepted_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,'paired_owner_action',?,?)""",
        (
            project_id,
            state["task_id"],
            run_id,
            candidate_id,
            operation_key,
            fingerprint,
            candidate_sha256,
            review_sha256,
            canonical(state["reviews"]),
            note,
            int(acknowledge_limits),
            canonical(receipt),
            now,
        ),
    )
    updated = conn.execute(
        "UPDATE runtime_runs SET status='accepted',updated_at=? WHERE project_id=? AND id=? AND status='needs_review' AND current_attempt_id=? AND fence=?",
        (
            now,
            project_id,
            run_id,
            candidate["scope"]["attempt_id"],
            candidate["scope"]["fence"],
        ),
    )
    if updated.rowcount != 1:
        raise OperationConflict(
            "The original completed attempt no longer owns this result"
        )
    updated = conn.execute(
        "UPDATE tasks SET status='done',completed_at=datetime(?,'unixepoch') WHERE project_id=? AND id=? AND status NOT IN ('done','cancelled','failed')",
        (now, project_id, state["task_id"]),
    )
    if updated.rowcount != 1:
        raise OperationConflict("Task no longer accepts this result")
    conn.execute(
        "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE project_id=? AND task_id=?",
        (now, project_id, state["task_id"]),
    )
    return {**receipt, "acceptance_id": cursor.lastrowid}, True
