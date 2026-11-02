"""Scoped finding inspection without inferring scientific validation from legacy flags.

Owner readers and grant-checked native tools share bounded SQL projections. Saved
quotes retain their source identity; arbitrary URLs/files are never opened here.
Historical confidence/method values are attributed records, not calibrated certainty.
"""

import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing, contextmanager

from backend.db.connection import connect
from backend.research.models import (
    OperationConflict,
    ResearchInputError,
    ResearchNotFound,
    SourceTooLarge,
    bounded_text,
    positive_id,
)
from backend.research.provenance import provenance_summary

TYPES = {"observation", "hypothesis", "experiment", "proof", "conclusion"}
STATUSES = {"provisional", "active", "superseded"}
META = """f.id,f.project_id,f.task_id,substr(f.topic,1,1200) AS topic,
substr(f.agent_id,1,128) AS agent_id,f.created_at,f.status,f.finding_type,
f.confidence,substr(f.validation_method,1,4000) AS validation_method,
f.reproducibility_score,length(f.content) AS content_chars,
substr(f.content,1,240) AS content_excerpt,
(SELECT count(*) FROM finding_sources fs WHERE fs.project_id=f.project_id AND fs.finding_id=f.id) AS evidence_count"""


def window(text, offset, max_chars):
    """Bound character disclosure with an explicit continuation rather than a silent excerpt."""
    if (
        type(offset) is not int
        or offset < 0
        or type(max_chars) is not int
        or not 1 <= max_chars <= 20000
    ):
        raise ResearchInputError(
            "Text window requires offset >= 0 and max_chars 1–20000"
        )
    part = text[offset : offset + max_chars]
    end = offset + len(part)
    return {
        "content": part,
        "offset": offset,
        "total_chars": len(text),
        "next_offset": end if end < len(text) else None,
    }


def filters(
    project_id,
    *,
    query=None,
    finding_type=None,
    status=None,
    min_confidence=None,
    task_id=None,
):
    """Combine every selected predicate; a missing project never becomes a global search."""
    positive_id(project_id)
    clauses, params = ["f.project_id=?"], [project_id]
    for column, value, allowed in [
        ("finding_type", finding_type, TYPES),
        ("status", status, STATUSES),
    ]:
        if value is not None:
            if value not in allowed | {"unknown"}:
                raise ResearchInputError("Unsupported finding type or status filter")
            if value == "unknown":
                clauses.append(f"f.{column} IS NULL")
            else:
                clauses.append(f"f.{column}=?")
                params.append(value)
    if task_id is not None:
        positive_id(task_id)
        clauses.append("f.task_id=?")
        params.append(task_id)
    if min_confidence is not None:
        if (
            type(min_confidence) not in (int, float)
            or not math.isfinite(min_confidence)
            or not 0 <= min_confidence <= 1
        ):
            raise ResearchInputError(
                "Declared confidence filter must be finite and between 0 and 1"
            )
        clauses.append("f.confidence>=? AND f.confidence<=1")
        params.append(min_confidence)
    if query is not None:
        bounded_text(query, "finding search", 1000)
        from backend.tools.base.db import sanitize_fts5_query

        clauses.append(
            "f.id IN (SELECT rowid FROM findings_fts WHERE findings_fts MATCH ?)"
        )
        expression = sanitize_fts5_query(query)
        if expression == '""':
            raise ResearchInputError(
                "Finding lexical query contains no searchable words"
            )
        params.append(expression)
    return " AND ".join(clauses), params


def metadata(row):
    """Keep historical assertions visible while leaving scientific confidence unknown."""
    result = dict(row)
    result["review_status"] = (
        "unverified_legacy"
        if result.get("validation_method")
        or result.get("status") in {"active", "superseded"}
        else "not_recorded"
    )
    result["scientific_confidence"] = None
    result["confidence_origin"] = (
        "stored_declaration" if result.get("confidence") is not None else "unknown"
    )
    for field in ("confidence", "reproducibility_score"):
        value = result.get(field)
        if value is not None and (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            result[field + "_original"] = str(value)
            result[field] = None
            result[field + "_invalid"] = True
    return result


def _search_execute(conn, statement, parameters):
    """Translate FTS parser failures only; preserve database faults and never change search method."""
    try:
        return conn.execute(statement, parameters)
    except sqlite3.OperationalError as exc:
        message = str(exc).casefold()
        if "findings_fts MATCH" in statement and (
            "fts5:" in message or "unterminated string" in message
        ):
            raise ResearchInputError(
                "Finding lexical query could not be parsed; revise its quotes/prefixes"
            ) from exc
        raise


def list_findings(conn, project_id, *, after_id=0, limit=50, **selection):
    """Page stable finding ids and metadata while counting all matching records in one snapshot."""
    if (
        type(after_id) is not int
        or after_id < 0
        or type(limit) is not int
        or not 1 <= limit <= 200
    ):
        raise ResearchInputError(
            "Finding index requires a nonnegative cursor and limit 1–200"
        )
    where, params = filters(project_id, **selection)
    total = _search_execute(
        conn, f"SELECT count(*) FROM findings f WHERE {where}", params
    ).fetchone()[0]
    rows = _search_execute(
        conn,
        f"SELECT {META} FROM findings f WHERE {where} AND f.id>? ORDER BY f.id LIMIT ?",
        (*params, after_id, limit + 1),
    ).fetchall()
    selected = rows[:limit]
    return {
        "project_id": project_id,
        "items": [metadata(row) for row in selected],
        "next_after_id": selected[-1]["id"] if len(rows) > limit else None,
        "total_matching": total,
        "search_kind": "fts5_lexical" if selection.get("query") is not None else None,
        "confidence_filter_scope": "historical stored declarations; unknown values excluded only when a threshold is selected",
    }


def summarize_findings(conn, project_id, **selection):
    """Aggregate the complete filtered set without an LLM summary or invented confidence."""
    where, params = filters(project_id, **selection)
    groups = _search_execute(
        conn,
        f"SELECT finding_type,status,count(*) AS count FROM findings f WHERE {where} GROUP BY finding_type,status ORDER BY finding_type,status",
        params,
    ).fetchall()
    declared = _search_execute(
        conn,
        f"SELECT sum(CASE WHEN confidence>=0 AND confidence<=1 THEN 1 ELSE 0 END) AS known_count,avg(CASE WHEN confidence>=0 AND confidence<=1 THEN confidence END) AS mean FROM findings f WHERE {where}",
        params,
    ).fetchone()
    total = sum(row["count"] for row in groups)
    known = declared["known_count"] or 0
    return {
        "project_id": project_id,
        "total_count": total,
        "groups": [dict(row) for row in groups],
        "declared_confidence": {
            "known_count": known,
            "unknown_count": total - known,
            "mean": declared["mean"],
            "meaning": "historical stored declarations, not scientific confidence or independent review",
        },
        "scientific_confidence": None,
        "summary_kind": "structured_counts",
    }


def _finding(conn, project_id, finding_id):
    """Resolve both identities before exposing any finding metadata."""
    positive_id(project_id)
    positive_id(finding_id)
    row = conn.execute(
        f"SELECT {META} FROM findings f WHERE f.project_id=? AND f.id=?",
        (project_id, finding_id),
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Finding not found in this project")
    return metadata(row)


def evidence(conn, project_id, finding_id, *, offset=0, limit=20):
    """Read bounded exact-quote records; inconsistent historical relations remain visible as unavailable."""
    _finding(conn, project_id, finding_id)
    if (
        type(offset) is not int
        or offset < 0
        or type(limit) is not int
        or not 1 <= limit <= 20
    ):
        raise ResearchInputError("Evidence page requires offset >= 0 and limit 1–20")
    total = conn.execute(
        "SELECT count(*) FROM finding_sources WHERE project_id=? AND finding_id=?",
        (project_id, finding_id),
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT fs.finding_id,fs.source_id,substr(fs.quote,1,8000) AS quote,length(fs.quote) AS quote_chars,
        s.kind,s.locator,s.title,s.sha256,s.captured_at,f.status AS finding_status,
        CASE WHEN s.id IS NOT NULL AND instr(s.content,fs.quote)>0 THEN 1 ELSE 0 END AS quote_is_exact,
        CASE WHEN s.id IS NOT NULL AND instr(s.content,fs.quote)>0 THEN instr(s.content,fs.quote)-1 ELSE NULL END AS quote_offset,
        CASE WHEN s.id IS NULL THEN 1 ELSE 0 END AS source_unavailable
        FROM finding_sources fs JOIN findings f ON f.id=fs.finding_id AND f.project_id=fs.project_id
        LEFT JOIN research_sources s ON s.id=fs.source_id AND s.project_id=fs.project_id
        WHERE fs.project_id=? AND fs.finding_id=? ORDER BY fs.source_id,fs.quote LIMIT ? OFFSET ?""",
        (project_id, finding_id, limit, offset),
    ).fetchall()
    values = [
        {
            **dict(row),
            "quote_is_exact": bool(row["quote_is_exact"]),
            "source_unavailable": bool(row["source_unavailable"]),
            "quote_truncated": row["quote_chars"] > 8000,
        }
        for row in rows
    ]
    end = offset + len(values)
    return {
        "project_id": project_id,
        "finding_id": finding_id,
        "evidence": values,
        "total_evidence": total,
        "evidence_offset": offset,
        "next_evidence_offset": end if end < total else None,
    }


def legacy_sources(conn, project_id, finding_id, *, offset=0, max_chars=8000):
    """Recover unverified historical source declarations literally, without inventing captured evidence."""
    _finding(conn, project_id, finding_id)
    window("", offset, max_chars)
    text, total = conn.execute(
        "SELECT substr(sources_json,?,?),length(sources_json) FROM findings WHERE project_id=? AND id=?",
        (offset + 1, max_chars, project_id, finding_id),
    ).fetchone()
    end = offset + len(text or "")
    return {
        "project_id": project_id,
        "finding_id": finding_id,
        "content": text or "",
        "declaration_present": text is not None,
        "total_chars": total or 0,
        "offset": offset,
        "next_offset": end if end < (total or 0) else None,
        "verification": "unverified_legacy_declaration",
    }


def legacy_declaration(conn, project_id, finding_id):
    """Attach only the first bounded raw declaration preview to a normal finding read."""
    page = legacy_sources(conn, project_id, finding_id)
    return {
        "legacy_sources_json": page["content"] if page["declaration_present"] else None,
        "legacy_sources_total_chars": page["total_chars"],
        "legacy_sources_next_offset": page["next_offset"],
    }


def read_finding(
    conn, project_id, finding_id, *, offset=0, max_chars=12000, evidence_offset=0
):
    """Read bounded current text and citations without treating a legacy active flag as validation."""
    result = _finding(conn, project_id, finding_id)
    # Validate before using SQLite's one-based substring, including bool rejection.
    window("", offset, max_chars)
    body = conn.execute(
        "SELECT substr(content,?,?) FROM findings WHERE project_id=? AND id=?",
        (offset + 1, max_chars, project_id, finding_id),
    ).fetchone()[0]
    end = offset + len(body)
    return {
        **result,
        "content": body,
        "offset": offset,
        "total_chars": result["content_chars"],
        "next_offset": end if end < result["content_chars"] else None,
        **evidence(conn, project_id, finding_id, offset=evidence_offset),
        **legacy_declaration(conn, project_id, finding_id),
    }


def read_source(conn, project_id, finding_id, source_id, *, offset=0, max_chars=12000):
    """Read only a cited saved snapshot, verifying hash before disclosing text or provenance."""
    _finding(conn, project_id, finding_id)
    positive_id(source_id)
    row = conn.execute(
        """SELECT s.id,length(CAST(s.content AS BLOB)) AS bytes FROM research_sources s
        WHERE s.project_id=? AND s.id=? AND EXISTS(SELECT 1 FROM finding_sources fs WHERE fs.project_id=s.project_id AND fs.finding_id=? AND fs.source_id=s.id)""",
        (project_id, source_id, finding_id),
    ).fetchone()
    if row is None:
        raise ResearchNotFound("Source is not cited by this project's finding")
    if row["bytes"] > 200000:
        raise SourceTooLarge(
            "Saved source exceeds its canonical text budget; reconcile before use"
        )
    source = dict(
        conn.execute(
            "SELECT * FROM research_sources WHERE project_id=? AND id=?",
            (project_id, source_id),
        ).fetchone()
    )
    if hashlib.sha256(source["content"].encode()).hexdigest() != source["sha256"]:
        raise OperationConflict(
            "Captured source hash differs from its text; reconcile before use"
        )
    provenance = json.loads(source["provenance_json"])
    return {
        "finding_id": finding_id,
        "source_id": source_id,
        "project_id": project_id,
        "captured_for_task_id": source["task_id"],
        "kind": source["kind"],
        "title": source["title"],
        "locator": source["locator"],
        "sha256": source["sha256"],
        "captured_at": source["captured_at"],
        "provenance": provenance_summary(provenance),
        **window(source["content"], offset, max_chars),
    }


def selected_ids(value):
    """Decode the HTTP adapter's finite comma-separated selection, never a project identity."""
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 1000:
        raise ResearchInputError("Finding selection requires at most 50 positive ids")
    parts = value.split(",")
    if not 1 <= len(parts) <= 50 or any(
        not part.isascii() or not part.isdigit() or part.startswith("0")
        for part in parts
    ):
        raise ResearchInputError("Finding selection requires at most 50 positive ids")
    return [int(part) for part in parts]


def finding_corpus(conn, project_id, *, finding_ids=None, **selection):
    """Freeze every matching title/body within explicit row/byte budgets, without creating a source."""
    from backend.research.structured_text import Units

    where, params = filters(project_id, **selection)
    if finding_ids is not None:
        if (
            not isinstance(finding_ids, (list, tuple))
            or not 1 <= len(finding_ids) <= 50
        ):
            raise ResearchInputError("Select 1–50 distinct finding ids")
        for identity in finding_ids:
            positive_id(identity)
        if len(set(finding_ids)) != len(finding_ids):
            raise ResearchInputError("Finding selection contains duplicates")
        where += " AND f.id IN (" + ",".join("?" for _ in finding_ids) + ")"
        params += list(finding_ids)
    count, size = _search_execute(
        conn,
        f"SELECT count(*),coalesce(sum(length(CAST(topic AS BLOB))+length(CAST(content AS BLOB))+15+length(CAST(f.id AS TEXT))),0)-CASE WHEN count(*)>0 THEN 2 ELSE 0 END FROM findings f WHERE {where}",
        params,
    ).fetchone()
    if finding_ids is not None and count != len(finding_ids):
        raise ResearchNotFound(
            "One or more selected findings are unavailable in this project/filter"
        )
    if count > 500 or size > 200000:
        raise SourceTooLarge(
            "Complete finding corpus exceeds 500 rows or 200000 bytes; narrow filters or select explicit findings, no partial search was run"
        )
    if count == 0:
        return {
            "id": "ephemeral_finding_corpus",
            "content": "",
            "sha256": hashlib.sha256(b"").hexdigest(),
            "provenance": {"units": []},
            "finding_ids": [],
            "corpus_count": 0,
        }
    rows = _search_execute(
        conn,
        f"SELECT {META},f.content,f.topic AS full_topic FROM findings f WHERE {where} ORDER BY f.id",
        params,
    ).fetchall()
    units = Units()
    snapshots = []
    for row in rows:
        item = metadata(row)
        snapshot = hashlib.sha256(
            json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        units.add(
            "finding", str(row["id"]), row["full_topic"] + "\n\n" + row["content"]
        )
        units.units[-1].update(
            finding_id=row["id"], topic=row["topic"], record_sha256=snapshot
        )
        snapshots.append(snapshot)
    text, provenance = units.finish("finding_registry", record_snapshots=snapshots)
    # Bind metadata as well as text: a changed status/author/filter set invalidates a query.
    record_set = hashlib.sha256(
        json.dumps(snapshots, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "id": "ephemeral_finding_corpus",
        "content": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "record_set_sha256": record_set,
        "provenance": provenance,
        "finding_ids": [row["id"] for row in rows],
        "corpus_count": count,
    }


def corpus_unchanged(before, after):
    """Compare all text/metadata identities before releasing results of a slow local worker."""
    return all(
        before.get(key) == after.get(key)
        for key in ("sha256", "record_set_sha256", "finding_ids")
    )


def finding_matches(corpus, result):
    """Map ranked corpus chunks to exact title/body slices; cosine is not scientific confidence."""
    matches = []
    for chunk in result["matches"]:
        for unit in corpus["provenance"]["units"]:
            start = max(chunk["start_offset"], unit["start_offset"])
            end = min(chunk["end_offset"], unit["end_offset"])
            if start >= end:
                continue
            matches.append(
                {
                    "finding_id": unit["finding_id"],
                    "topic": unit["topic"],
                    "record_sha256": unit["record_sha256"],
                    "rank": chunk["rank"],
                    "score": chunk["score"],
                    "score_scope": "retrieval chunk; not scientific confidence",
                    "text_scope": "title_and_body",
                    "finding_start_offset": start - unit["start_offset"],
                    "finding_end_offset": end - unit["start_offset"],
                    "excerpt": corpus["content"][start:end],
                }
            )
    return {
        **{
            key: value
            for key, value in result.items()
            if key not in {"source_id", "sha256", "matches"}
        },
        "corpus_sha256": corpus["sha256"],
        "record_set_sha256": corpus.get("record_set_sha256"),
        "corpus_count": corpus["corpus_count"],
        "finding_ids": corpus["finding_ids"],
        "matches": matches,
        "scientific_confidence": None,
        "coverage_scope": "all complete titles/bodies selected by the explicit project and filters; not captured scientific-source verification",
    }


def validate_continuation(corpus, after_rank, expected_text, expected_records):
    """Bind rank offsets to observed text and metadata before admitting any semantic worker."""
    if after_rank > 0 and (expected_text is None or expected_records is None):
        raise ResearchInputError(
            "A semantic continuation requires both observed corpus fingerprints"
        )
    if expected_text is None and expected_records is None:
        return
    if any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in (expected_text, expected_records)
    ):
        raise ResearchInputError(
            "Both corpus fingerprints must be complete SHA-256 values"
        )
    if expected_text != corpus["sha256"] or expected_records != corpus.get(
        "record_set_sha256"
    ):
        raise OperationConflict(
            "Finding corpus changed between result pages; restart the search instead of combining revisions"
        )


def query_corpus(
    corpus,
    retriever,
    query,
    *,
    limit=5,
    after_rank=0,
    cancelled=None,
    expected_corpus_sha256=None,
    expected_record_set_sha256=None,
):
    """Use the existing owned semantic worker, or explicitly report a genuinely empty scoped set."""
    bounded_text(query, "semantic finding query", 1000)
    validate_continuation(
        corpus, after_rank, expected_corpus_sha256, expected_record_set_sha256
    )
    if not corpus["corpus_count"]:
        return {
            "search_kind": "empty_scoped_set",
            "matches": [],
            "full_coverage": True,
            "corpus_count": 0,
            "finding_ids": [],
            "scientific_confidence": None,
            "next_rank": None,
            "execution": {"worker_started": False},
        }
    return finding_matches(
        corpus,
        retriever.query(
            corpus, query, limit=limit, after_rank=after_rank, cancelled=cancelled
        ),
    )


class FindingStore:
    """Owner/legacy read adapter over an existing serving database; never bootstraps or loads models."""

    def __init__(self, database):
        """Bind the exact database path chosen by the composition edge."""
        self.database = str(database)

    @contextmanager
    def _transaction(self):
        """Keep metadata/count/body on one read-only SQLite snapshot."""
        with closing(connect(self.database, existing_only=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            yield conn

    def list(self, project_id, **selection):
        """Expose one scoped metadata page with all chosen filters applied."""
        with self._transaction() as conn:
            return list_findings(conn, project_id, **selection)

    def summary(self, project_id, **selection):
        """Count the entire scoped filtered set without invoking a model."""
        with self._transaction() as conn:
            return summarize_findings(conn, project_id, **selection)

    def read(self, project_id, finding_id, **selection):
        """Recover bounded text/evidence for the selected project and finding."""
        with self._transaction() as conn:
            return read_finding(conn, project_id, finding_id, **selection)

    def evidence(self, project_id, finding_id, **selection):
        """Page exact citation records independently of the finding body."""
        with self._transaction() as conn:
            return evidence(conn, project_id, finding_id, **selection)

    def source(self, project_id, finding_id, source_id, **selection):
        """Inspect a cited snapshot without permitting arbitrary source/file reads."""
        with self._transaction() as conn:
            return read_source(conn, project_id, finding_id, source_id, **selection)

    def legacy_sources(self, project_id, finding_id, **selection):
        """Page literal historical source declarations, explicitly distinct from captured quotations."""
        with self._transaction() as conn:
            return legacy_sources(conn, project_id, finding_id, **selection)

    def corpus(self, project_id, **selection):
        """Freeze a complete bounded current finding corpus in one read-only snapshot."""
        with self._transaction() as conn:
            return finding_corpus(conn, project_id, **selection)
