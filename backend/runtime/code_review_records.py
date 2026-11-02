"""Bind native reviewer assertions to actual source and original owned validation/closure observations.

Proposals are attributed assertions. Confirmation records protocol completion
against one exact candidate; it does not accept the task or certify correctness.
All mutations recheck the original lease, current packet and distinct native IDs.
"""

import hashlib
import json
from dataclasses import asdict

from backend.knowledge.reviews import canonical, digest
from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.check_contracts import CandidateSubject
from backend.runtime.code_candidate import CapturedCodeCandidate
from backend.runtime.code_review_files import CodeReviewFiles, verify_source_quote
from backend.runtime.code_review_git import ReviewGitWitness
from backend.runtime.code_review_models import CodeReviewDecision
from backend.runtime.code_reviews import CodeReviews
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, text


class CodeReviewRecords:
    """Reserve before native effects, retain one proposal and confirm only under original current authority and physical receipts."""

    def __init__(self, runs):
        """Use the existing run-store transaction, original authority, clock and event boundary."""
        self.runs = runs
        self.reviews = CodeReviews(runs)

    @staticmethod
    def _row(conn, project_id, attempt_id):
        """Read only the original scoped review record, including historical interrupted observations."""
        row = conn.execute(
            "SELECT * FROM runtime_code_review_records WHERE project_id=? AND attempt_id=?",
            (project_id, attempt_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Native code review record not found")
        return dict(row)

    @staticmethod
    def _origin(row, lease):
        """Reject adoption by another attempt, context, owner or fence even after original authority ends."""
        if any(
            row[name] != getattr(lease, name)
            for name in (
                "run_id",
                "attempt_id",
                "project_id",
                "task_id",
                "context_version",
                "fence",
                "owner_id",
            )
        ):
            raise RunConflict("Native review belongs to another original owner")

    def _current(self, conn, lease):
        """Require a current reviewer and the unchanged originally admitted subject, separate from the actual author."""
        run = self.runs._authority(conn, lease)
        if run["execution_kind"] != "code_review":
            raise RunConflict("Native review requires its admitted review execution")
        request = self.reviews._request(
            conn, lease.project_id, lease.run_id, require_current=True
        )
        view = self.reviews.execution_view(conn, run)
        candidate = CodeCandidates._row(
            conn, lease.project_id, request["author_attempt_id"]
        )
        return run, request, view, candidate

    def candidate(self, lease):
        """Return exact immutable capture data for trusted owned Git validation, without starting or approving a review."""
        with self.runs._transaction() as conn:
            _run, _request, _view, row = self._current(conn, lease)
            return CapturedCodeCandidate(
                **{
                    name: row[name]
                    for name in CapturedCodeCandidate.__dataclass_fields__
                }
            )

    def reserve(self, lease):
        """Persist original review origin before Git/native effects; an existing reservation is data and never replay permission."""
        with self.runs._transaction(write=True) as conn:
            _run, request, _view, _candidate = self._current(conn, lease)
            self._author_input(conn, request)
            old = conn.execute(
                "SELECT attempt_id FROM runtime_code_review_records WHERE run_id=?",
                (lease.run_id,),
            ).fetchone()
            if old is not None:
                row = self._row(conn, lease.project_id, old["attempt_id"])
                self._origin(row, lease)
                return row, False
            now = self.runs.clock()
            conn.execute(
                """INSERT INTO runtime_code_review_records(attempt_id,run_id,project_id,task_id,context_version,fence,owner_id,subject_sha256,state,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,'preparing',?,?)""",
                (
                    lease.attempt_id,
                    lease.run_id,
                    lease.project_id,
                    lease.task_id,
                    lease.context_version,
                    lease.fence,
                    lease.owner_id,
                    request["subject_sha256"],
                    now,
                    now,
                ),
            )
            return self._row(conn, lease.project_id, lease.attempt_id), True

    @staticmethod
    def _author_input(conn, request):
        """Verify exact original host input bytes, retaining a reference rather than pretending task metadata was the complete request."""
        expected = json.loads(request["snapshot_json"])["author_input"]
        row = conn.execute(
            "SELECT input_text,input_sha256 FROM runtime_input_snapshots WHERE attempt_id=?",
            (request["author_attempt_id"],),
        ).fetchone()
        if (
            expected is None
            or row is None
            or expected["input_sha256"] != row["input_sha256"]
            or hashlib.sha256(row["input_text"].encode()).hexdigest()
            != row["input_sha256"]
        ):
            raise RunConflict("Native review requires the author's exact saved input")
        return row["input_text"], row["input_sha256"]

    @staticmethod
    def _witness(candidate, observed, proof):
        """Match complete actual Git observations and nonempty original closed-operation evidence; booleans from model prose are not a witness."""
        if not isinstance(observed, ReviewGitWitness) or asdict(observed) != {
            name: candidate[name]
            for name in ("base_sha", "head_sha", "tree_sha", "diff_sha256")
        }:
            raise RunConflict("Review Git observation belongs to another candidate")
        CodeCandidates._proof(proof)
        return {"git": asdict(observed), "closure": proof}

    def preflight(self, lease, observed, proof):
        """Record complete current source validation before any native code-review dispatch is allowed."""
        with self.runs._transaction(write=True) as conn:
            _run, request, _view, candidate = self._current(conn, lease)
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            evidence = canonical(self._witness(candidate, observed, proof))
            if row["state"] == "ready" and row["preflight_json"] == evidence:
                return row
            if (
                row["state"] != "preparing"
                or row["subject_sha256"] != request["subject_sha256"]
            ):
                raise RunConflict("Review validation requires its original preparation")
            conn.execute(
                "UPDATE runtime_code_review_records SET state='ready',preflight_json=?,updated_at=? WHERE attempt_id=?",
                (evidence, self.runs.clock(), lease.attempt_id),
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def require_preflight(self, conn, run):
        """Keep native dispatch closed without original current complete Git validation; readonly inspection remains separate."""
        try:
            row = self._row(conn, run["project_id"], run["current_attempt_id"])
        except RunNotFound as exc:
            raise RunConflict(
                "Native review requires its validated original candidate"
            ) from exc
        request = self.reviews._request(
            conn, run["project_id"], run["id"], require_current=True
        )
        if (
            row["state"] not in ("ready", "proposed")
            or row["run_id"] != run["id"]
            or row["context_version"] != run["context_version"]
            or row["fence"] != run["fence"]
            or row["owner_id"] != run["owner_id"]
            or row["subject_sha256"] != request["subject_sha256"]
        ):
            raise RunConflict("Native review requires its validated original candidate")
        return row

    def material(self, lease, section):
        """Read exact packet/original input/diff for bounded host windows, distinguishing history from current authority."""
        with self.runs._transaction() as conn:
            _run, request, _view, candidate = self._current(conn, lease)
            if section == "packet":
                content, sha = request["snapshot_json"], request["subject_sha256"]
            elif section == "author_input":
                content, sha = self._author_input(conn, request)
            elif section == "diff":
                content, sha = (
                    candidate["diff"].decode("utf-8", errors="replace"),
                    candidate["diff_sha256"],
                )
            else:
                raise ValueError("Unknown code review material")
            return {
                "review_run_id": lease.run_id,
                "subject_sha256": request["subject_sha256"],
                "section": section,
                "sha256": sha,
                "text": content,
            }

    def file(self, lease, path, *, offset=0, max_chars=12000):
        """Acquire bounded exact source outside the SQL writer lock and revalidate the original scope before returning it."""
        with self.runs._transaction() as conn:
            _run, _request, view, _candidate = self._current(conn, lease)
        result = CodeReviewFiles(view).read(path, offset=offset, max_chars=max_chars)
        with self.runs._transaction() as conn:
            self._current(conn, lease)
        return result

    @staticmethod
    def _references(view, candidate, decision):
        """Check exact candidate file/diff quotations separately from reviewers' claims about their logical support."""
        reader = CodeReviewFiles(view)
        return [
            reader.verify(ref)
            if ref.kind == "file"
            else verify_source_quote(ref, candidate["diff"])
            for ref in decision.references
        ]

    def propose(self, lease, operation_key, subject_sha256, decision):
        """Commit one immutable attributed proposal with actual source quotes; a positive model assertion is still not confirmation or acceptance."""
        command_key(operation_key)
        if not isinstance(decision, CodeReviewDecision):
            raise TypeError("Typed immutable code-review decision required")
        payload = canonical(asdict(decision))
        if len(payload.encode()) > 262144:
            raise RunConflict("Complete code review proposal exceeds its byte budget")
        intent = {
            "kind": "code_review.propose",
            "run_id": lease.run_id,
            "subject_sha256": subject_sha256,
            "decision": asdict(decision),
        }
        with self.runs._transaction() as conn:
            run, request, view, candidate = self._current(conn, lease)
            row = self.require_preflight(conn, run)
            self._origin(row, lease)
            if (
                request["subject_sha256"] != subject_sha256
                or run["thread_id"] is None
                or run["turn_id"] is None
                or run["thread_id"] == request["author_thread_id"]
            ):
                raise RunConflict(
                    "Review proposal requires its exact subject and independent native turn"
                )
            previous = self.runs._receipt(
                conn, lease.project_id, lease.task_id, operation_key, intent
            )
            if previous is not None:
                return row
        references = self._references(view, candidate, decision)
        with self.runs._transaction(write=True) as conn:
            run, request, _view, _candidate = self._current(conn, lease)
            row = self.require_preflight(conn, run)
            self._origin(row, lease)
            previous = self.runs._receipt(
                conn, lease.project_id, lease.task_id, operation_key, intent
            )
            if previous is not None:
                return row
            if row["state"] != "ready" or row["proposal_json"] is not None:
                raise RunConflict("This review already has an immutable proposal")
            proof = {
                "references": references,
                "reviewer": {
                    "attempt_id": lease.attempt_id,
                    "actor_id": lease.actor_id,
                    "thread_id": run["thread_id"],
                    "turn_id": run["turn_id"],
                },
            }
            conn.execute(
                "UPDATE runtime_code_review_records SET state='proposed',proposal_key=?,proposal_json=?,reference_proof_json=?,updated_at=? WHERE attempt_id=?",
                (
                    operation_key,
                    payload,
                    canonical(proof),
                    self.runs.clock(),
                    lease.attempt_id,
                ),
            )
            self.runs._save_receipt(
                conn,
                lease.project_id,
                lease.task_id,
                operation_key,
                intent,
                {"run_id": lease.run_id, "proposal_sha256": digest(asdict(decision))},
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_review.proposed",
                {
                    "run_id": lease.run_id,
                    "subject_sha256": subject_sha256,
                    "verdict": decision.verdict,
                    "confirmed": False,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def confirm(self, lease, observed, proof):
        """Confirm only matching after-review Git and original closure observations; never change a task's acceptance or source repository."""
        with self.runs._transaction() as conn:
            _run, _request, view, candidate = self._current(conn, lease)
            proposed = self._row(conn, lease.project_id, lease.attempt_id)
            if proposed["state"] != "proposed":
                raise RunConflict(
                    "A review needs its original proposal before confirmation"
                )
        # Git compares normalized repository content; quoted byte identities
        # are independently revalidated so an equivalent text conversion does
        # not silently relabel the source version used by the reviewer.
        self._references(
            view,
            candidate,
            CodeReviewDecision.from_data(json.loads(proposed["proposal_json"])),
        )
        with self.runs._transaction(write=True) as conn:
            run, request, _view, candidate = self._current(conn, lease)
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            if row["state"] != "proposed":
                raise RunConflict(
                    "A review needs its original proposal before confirmation"
                )
            after = self._witness(candidate, observed, proof)
            before = json.loads(row["preflight_json"])
            if before["closure"]["grant_id"] != proof["grant_id"] or not {
                op["operation_id"] for op in before["closure"]["operations"]
            } <= {op["operation_id"] for op in proof["operations"]}:
                raise RunConflict("Review closure belongs to another physical owner")
            native = conn.execute(
                "SELECT 1 FROM runtime_peers WHERE attempt_id=? AND kind='native' AND state='closed' AND bound_at IS NOT NULL",
                (lease.attempt_id,),
            ).fetchone()
            unclosed = conn.execute(
                "SELECT 1 FROM runtime_peers WHERE attempt_id=? AND state!='closed' AND NOT(kind='business' AND state='prepared' AND bound_at IS NULL)",
                (lease.attempt_id,),
            ).fetchone()
            if native is None or unclosed is not None:
                raise RunConflict("Review physical closure is unconfirmed")
            result = {
                "candidate": asdict(CandidateSubject.from_row(candidate)),
                "subject_sha256": request["subject_sha256"],
                "proposal_sha256": digest(json.loads(row["proposal_json"])),
                "after_review": after,
                "reviewer": json.loads(row["reference_proof_json"])["reviewer"],
                "native_turn": {
                    "thread_id": run["thread_id"],
                    "turn_id": run["turn_id"],
                },
            }
            conn.execute(
                "UPDATE runtime_code_review_records SET state='confirmed',result_json=?,updated_at=? WHERE attempt_id=?",
                (canonical(result), self.runs.clock(), lease.attempt_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code_review.confirmed",
                {
                    "run_id": lease.run_id,
                    "subject_sha256": request["subject_sha256"],
                    "verdict": json.loads(row["proposal_json"])["verdict"],
                    "accepted": False,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def observe_failure(self, lease, issue):
        """Retain the former original owner's interrupted work without restoring its ability to confirm after authority changes."""
        text(issue, "Code review issue", 4096)
        with self.runs._transaction(write=True) as conn:
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            if row["state"] == "confirmed":
                return row
            conn.execute(
                "UPDATE runtime_code_review_records SET state='reconciling',issue=?,updated_at=? WHERE attempt_id=?",
                (issue, self.runs.clock(), lease.attempt_id),
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def get(self, project_id, attempt_id):
        """Read historical data only; a confirmed record is not proof of current context or permission to publish."""
        with self.runs._transaction() as conn:
            return self._row(conn, project_id, attempt_id)
