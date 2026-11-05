"""Capture retained host command receipts as exact citable documents; no output or authority is supplied by a model."""

import hashlib
import json

from backend.knowledge.results import author_scope
from backend.research.models import (
    ResearchForbidden,
    ResearchInputError,
    ResearchNotFound,
    SourceDraft,
    bounded_text,
)
from backend.runtime.contracts import RunNotFound


def capture_command(store, scope, key, job_id):
    """Atomically capture only this current native author's closed terminal job, retaining failures/truncation and refusing binary or incomplete output."""
    bounded_text(job_id, "job_id", 128)

    def apply(conn):
        """Resolve actual stored origin/closure and create the document with the same source/receipt transaction."""
        from backend.runtime.sqlite_runs import SQLiteRunStore

        author = author_scope(conn, scope)
        size = conn.execute(
            "SELECT length(stdout)+length(stderr)+length(cast(argv_json AS BLOB)) FROM runtime_jobs j JOIN runtime_runs r ON r.id=j.run_id WHERE j.id=? AND r.project_id=?",
            (job_id, scope.project_id),
        ).fetchone()
        if size is not None and size[0] > 180000:
            raise ResearchInputError(
                "Retained command exceeds the complete source capture budget; no output was omitted"
            )
        try:
            job = SQLiteRunStore._job_row(conn, scope.project_id, job_id)
        except RunNotFound as error:
            raise ResearchNotFound("Command not found in this project") from error
        if job["run_id"] != author["id"] or job["attempt_id"] != author["attempt_id"]:
            raise ResearchForbidden(
                "Capture requires this native author's original command attempt"
            )
        if (
            job["status"] != "exited"
            or not job["local_execution_closed"]
            or job["exit_code"] is None
            or job["ended_at"] is None
        ):
            raise ResearchInputError(
                "Capture requires a terminal receipt and closed command peer; an unknown exit is not success"
            )
        stdout, stderr = bytes(job["stdout"]), bytes(job["stderr"])
        try:
            out, err = (
                stdout.decode("utf-8", errors="strict"),
                stderr.decode("utf-8", errors="strict"),
            )
        except UnicodeDecodeError as error:
            raise ResearchInputError(
                "Binary command output cannot become a lossless UTF-8 source; inspect its original byte windows"
            ) from error
        metadata = {
            "job_id": job_id,
            "run_id": job["run_id"],
            "attempt_id": job["attempt_id"],
            "peer_id": job["peer_id"],
            "local_execution_closed": True,
            "argv": json.loads(job["argv_json"]),
            "cwd": job["cwd"],
            "status": job["status"],
            "exit_code": job["exit_code"],
            "error": job["error"],
            "cancel_requested": bool(job["cancel_requested"]),
            "output_limited": bool(job["output_limited"]),
            "created_at": job["created_at"],
            "ended_at": job["ended_at"],
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        }
        content = (
            "# Retained command output\n\n## Receipt\n"
            + json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n\n## Standard output (UTF-8)\n"
            + out
            + "\n## Standard error (UTF-8)\n"
            + err
        )
        draft = SourceDraft(
            "attachment",
            f"command-receipt:{job_id}",
            f"Command output {job_id}",
            content,
            {
                "origin": "retained_command_receipt",
                "capture_adapter": "command-utf8-v1",
                "text_interpretation": "Exact retained UTF-8 stdout/stderr with host receipt; not uploaded input, empirical replication or scientific validation.",
                "job": metadata,
            },
        )
        return store._insert_source(conn, scope, draft)

    return store._write(
        scope,
        key,
        "source.capture",
        {"command_job_id": job_id, "capture": "terminal_utf8_v1"},
        apply,
    )
