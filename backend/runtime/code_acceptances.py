"""Owner-only observation and atomic acceptance of captured code and independent review.

This adapter reuses the original run transaction/event boundary. It never opens
inference, mutates candidate files or authorizes publication to a destination.
"""

import hashlib
import json
from dataclasses import asdict

from backend.knowledge.reviews import canonical, digest
from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.check_contracts import CandidateSubject
from backend.runtime.code_acceptance_policy import (
    CodeAcceptanceIntent,
    assess_code_checks,
    prior_code_review_issues,
)
from backend.runtime.code_reviews import CodeReviews
from backend.runtime.contracts import RunConflict
from backend.runtime.project_check_policy import ProjectCheckPolicies


class CodeAcceptances:
    """Keep exact owner observations and historical receipts separate from native turn completion."""

    def __init__(self, runs):
        """Use the existing scoped store, clock and durable events without adding another scheduler."""
        self.runs = runs
        self.reviews = CodeReviews(runs)

    @staticmethod
    def _receipt(conn, project_id, run_id):
        """Return original immutable owner history without asserting currentness."""
        row = conn.execute(
            "SELECT receipt_json FROM runtime_code_acceptances WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def _state(self, conn, project_id, run_id):
        """Derive current eligibility from original scoped evidence while retaining stale receipts as history."""
        run = self.runs._row(conn, project_id, run_id)
        receipt = self._receipt(conn, project_id, run_id)
        project_policy = ProjectCheckPolicies.current(conn, project_id)
        # Accepted history keeps its original rule; old receipts predate project policies.
        applied_policy = receipt.get("check_policy") if receipt else project_policy
        if run["execution_kind"] != "development":
            raise RunConflict("This run is not a code development result")
        candidate = CodeCandidates._row(conn, project_id, run["current_attempt_id"])
        if candidate["state"] != "ready":
            raise RunConflict(
                "El candidato todavía no está listo para revisión y aceptación"
            )
        subject = asdict(CandidateSubject.from_row(candidate))
        blockers = []
        packet = None
        try:
            packet, _ = self.reviews._subject(
                conn, project_id, candidate["attempt_id"], allow_accepted=True
            )
        except (RunConflict, ValueError) as error:
            blockers.append(
                {
                    "code": "candidate_not_current",
                    "message": "El candidato ya no coincide con los requisitos o su cierre no está comprobado.",
                    "detail": str(error),
                }
            )
        row = conn.execute(
            """SELECT q.*,v.current_attempt_id AS reviewer_attempt_id,
            v.status AS reviewer_status,v.actor_id AS reviewer_actor_id,
            a.thread_id,a.turn_id,a.status AS attempt_status,a.native_result_json,
            rr.state AS record_state,rr.proposal_json,rr.result_json
            FROM runtime_code_review_requests q JOIN runtime_runs v ON v.id=q.run_id
            LEFT JOIN runtime_attempts a ON a.id=v.current_attempt_id
            LEFT JOIN runtime_code_review_records rr ON rr.attempt_id=a.id
            WHERE q.project_id=? AND q.author_attempt_id=? ORDER BY q.created_at DESC,q.rowid DESC LIMIT 1""",
            (project_id, candidate["attempt_id"]),
        ).fetchone()
        review = None
        if row is not None:
            self.reviews._request(conn, project_id, row["run_id"])
            review = {
                "run_id": row["run_id"],
                "attempt_id": row["reviewer_attempt_id"],
                "actor_id": row["reviewer_actor_id"],
                "thread_id": row["thread_id"],
                "turn_id": row["turn_id"],
                "subject_sha256": row["subject_sha256"],
                "state": row["record_state"],
                "proposal": json.loads(row["proposal_json"])
                if row["proposal_json"]
                else None,
                "confirmation": json.loads(row["result_json"])
                if row["result_json"]
                else None,
                "native_result": json.loads(row["native_result_json"])
                if row["native_result_json"]
                else None,
            }
            current = (
                packet is not None
                and row["subject_sha256"] == packet["subject_sha256"]
                and (
                    row["candidate_workspace"],
                    row["candidate_device"],
                    row["candidate_inode"],
                )
                == (candidate["workspace"], candidate["device"], candidate["inode"])
            )
            if not current:
                blockers.append(
                    {
                        "code": "review_not_current",
                        "message": "La revisión no corresponde al candidato y las comprobaciones actuales.",
                    }
                )
            if (
                row["record_state"] != "confirmed"
                or row["attempt_status"] != "finished"
                or not review["native_result"]
                or review["native_result"].get("native_status") != "completed"
            ):
                blockers.append(
                    {
                        "code": "review_unconfirmed",
                        "message": "La revisión no terminó con confirmación y cierre comprobados.",
                    }
                )
            elif (
                not review["proposal"]
                or review["proposal"].get("verdict") != "supported"
            ):
                blockers.append(
                    {
                        "code": "review_not_supported",
                        "message": "El revisor pide cambios o no pudo respaldar el resultado.",
                    }
                )
            try:
                self.runs._closed_peer_proof(conn, row["reviewer_attempt_id"])
            except RunConflict:
                blockers.append(
                    {
                        "code": "review_closure_unknown",
                        "message": "Falta comprobar el cierre del revisor.",
                    }
                )
        else:
            blockers.append(
                {
                    "code": "review_absent",
                    "message": "Todavía no hay revisión independiente del candidato.",
                }
            )
        prior_issues = []
        if row is not None:
            history = conn.execute(
                """SELECT q.run_id,rr.state,
                json_extract(rr.proposal_json,'$.verdict') AS verdict,
                json_extract(rr.proposal_json,'$.rationale') AS rationale
                FROM runtime_code_review_requests q JOIN runtime_code_review_records rr ON rr.run_id=q.run_id
                WHERE q.project_id=? AND q.author_attempt_id=? AND q.subject_sha256=? AND q.run_id!=?
                ORDER BY q.created_at,q.rowid LIMIT 65""",
                (
                    project_id,
                    candidate["attempt_id"],
                    packet["subject_sha256"] if packet else row["subject_sha256"],
                    row["run_id"],
                ),
            ).fetchall()
            if len(history) > 64:
                blockers.append(
                    {
                        "code": "review_history_over_limit",
                        "message": "El historial de revisión supera el límite de esta vista; no se puede acreditar una inspección completa.",
                    }
                )
            prior_issues = prior_code_review_issues(
                [dict(item) for item in history[:64]]
            )
            blockers.extend(
                {
                    "code": "review_disagreement",
                    "run_id": issue["run_id"],
                    "message": issue["message"],
                }
                for issue in prior_issues
                if issue["blocking"]
            )
        check_policy = (
            assess_code_checks(packet["snapshot"]["checks"], policy_mode=(applied_policy or {}).get("mode"))
            if packet
            else {
                "blockers": [
                    {
                        "code": "checks_unverifiable",
                        "message": "No se pudo comprobar qué resultados pertenecen al contexto actual.",
                    }
                ],
                "limitations": [],
            }
        )
        blockers.extend(check_policy["blockers"])
        if not receipt and not project_policy["mode"]:
            blockers.append({"code": "check_policy_unset", "message": "Elige la política de comprobaciones del proyecto antes de aceptar código."})
        from backend.runtime.code_publications import CodePublications

        owned_publications = CodePublications.linked_runs(
            conn, project_id, run_id, self._receipt(conn, project_id, run_id)
        )
        from backend.runtime.remote_runtime import RemotePublications

        owned_publications |= RemotePublications.linked_runs(
            conn, project_id, owned_publications
        )
        other = conn.execute(
            """SELECT id,status FROM runtime_runs WHERE project_id=? AND task_id=?
            AND id NOT IN (?,?) AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')""",
            (project_id, run["task_id"], run_id, row["run_id"] if row else ""),
        ).fetchall()
        other = [item for item in other if item["id"] not in owned_publications]
        live = conn.execute(
            """SELECT r.id FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id
            JOIN runtime_runs r ON r.id=a.run_id WHERE r.project_id=? AND r.task_id=? AND p.state!='closed'""",
            (project_id, run["task_id"]),
        ).fetchall()
        live = [item for item in live if item["id"] not in owned_publications]
        if other or live:
            blockers.append(
                {
                    "code": "other_work_unreconciled",
                    "message": "Hay trabajo activo o pendiente de reconciliar en esta tarea.",
                }
            )
        task_status = conn.execute(
            "SELECT status FROM tasks WHERE project_id=? AND id=?",
            (project_id, run["task_id"]),
        ).fetchone()[0]
        receipt = self._receipt(conn, project_id, run_id)
        # Keep existing single-review receipts stable; bind every additional
        # material concern when history contributes evidence to the decision.
        review_sha = (
            digest(
                {
                    "review": review,
                    "prior_issues": [
                        {key: value for key, value in issue.items() if key != "message"}
                        for issue in prior_issues
                    ],
                }
            )
            if prior_issues
            else digest(review)
        )
        current_subject = packet["subject_sha256"] if packet else None
        acceptance_current = bool(
            receipt
            and packet
            and receipt["subject_sha256"] == current_subject
            and receipt["review_sha256"] == review_sha
            and run["status"] == "accepted"
            and task_status == "done"
            and not blockers
        )
        eligible = (
            not blockers
            and run["status"] == "needs_review"
            and task_status not in ("done", "failed", "cancelled")
            and row["reviewer_status"] == "needs_review"
        )
        publication = {
            "performed": False,
            "eligibility": "not_evaluated",
            "message": "Aceptar esta versión no la publica. Puedes publicar después el candidato aceptado en una rama nueva.",
        }
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_code_publication_requests'"
        ).fetchone():
            latest = conn.execute(
                """SELECT p.*,r.status,r.operation_key,r.current_attempt_id,r.fence FROM runtime_code_publication_requests p
            JOIN runtime_runs r ON r.id=p.run_id WHERE p.project_id=? AND p.author_run_id=? ORDER BY p.created_at DESC,p.rowid DESC LIMIT 1""",
                (project_id, run_id),
            ).fetchone()
            if latest:
                result = (
                    json.loads(latest["result_json"]) if latest["result_json"] else None
                )
                publication.update(
                    {
                        "run_id": latest["run_id"],
                        "status": latest["status"],
                        "attempt_id": latest["current_attempt_id"],
                        "fence": latest["fence"],
                        "operation_key": latest["operation_key"],
                        "intent": json.loads(latest["intent_json"]),
                        "result": result,
                        "target_ref": latest["target_ref"],
                        "performed": bool(result and result["publication_performed"]),
                        "message": (
                            "Versión publicada en "
                            + latest["target_ref"]
                            + ". El registro conserva la referencia observada al publicar."
                        )
                        if result and result["publication_performed"]
                        else "La publicación original no se aplicó; no se repitió su transacción."
                        if result and result["observed"]["state"] == "not_applied"
                        else "No se ha confirmado el resultado. Puedes comprobar qué ocurrió sin volver a publicar."
                        if latest["status"] == "reconciling"
                        else "Publicación registrada; consulta su estado y su resultado antes de solicitar otra.",
                    }
                )
        return {
            "project_id": project_id,
            "task_id": run["task_id"],
            "run_id": run_id,
            "candidate": subject,
            "packet": packet["snapshot"] if packet else None,
            "subject_sha256": current_subject,
            "candidate_current": packet is not None,
            "review": review,
            "review_issues": prior_issues,
            "review_sha256": review_sha,
            "checks": check_policy,
            "project_check_policy": project_policy,
            "blockers": blockers,
            "eligible": bool(eligible),
            "requires_acknowledgement": bool(
                check_policy["limitations"]
                or prior_issues
                or (
                    review
                    and review["proposal"]
                    and review["proposal"].get("limitations")
                )
            ),
            "acceptance": receipt,
            "acceptance_current": acceptance_current,
            "publication": publication,
        }

    def state(self, project_id, run_id):
        """Inspect the exact version, review, missing checks and original decision without inference or effects."""
        with self.runs._transaction() as conn:
            return self._state(conn, project_id, run_id)

    def diff(self, project_id, run_id, *, offset=0, max_chars=12000):
        """Read bounded captured diff text without substituting current filesystem bytes or hiding an unread tail."""
        if (
            type(offset) is not int
            or offset < 0
            or type(max_chars) is not int
            or not 1 <= max_chars <= 24000
        ):
            raise ValueError("Expected a bounded diff text window")
        with self.runs._transaction() as conn:
            run = self.runs._row(conn, project_id, run_id)
            if run["execution_kind"] != "development":
                raise RunConflict("This run has no captured code diff")
            candidate = CodeCandidates._row(conn, project_id, run["current_attempt_id"])
            data = candidate["diff"]
            if candidate["state"] != "ready" or not isinstance(data, bytes):
                raise RunConflict("El diff capturado todavía no está disponible")
            if hashlib.sha256(data).hexdigest() != candidate["diff_sha256"]:
                raise RunConflict(
                    "Captured diff no longer matches its exact fingerprint"
                )
            try:
                content = data.decode("utf-8")
            except UnicodeError as error:
                raise RunConflict(
                    "Captured diff is not UTF-8; this text viewer cannot represent its complete bytes"
                ) from error
            if offset > len(content):
                raise ValueError("Diff offset exceeds its complete text")
            end = min(offset + max_chars, len(content))
            return {
                "content": content[offset:end],
                "offset": offset,
                "next_offset": end if end < len(content) else None,
                "total_chars": len(content),
                "bytes": len(data),
                "sha256": candidate["diff_sha256"],
                "complete_file": offset == 0 and end == len(content),
            }

    def accept(self, project_id, run_id, intent):
        """Atomically record one paired-owner observation and close author/reviewer states; never publish code."""
        if not isinstance(intent, CodeAcceptanceIntent):
            raise TypeError("An explicit typed owner code acceptance is required")
        observed = asdict(intent)
        if intent.check_policy_revision is None:
            del observed["check_policy_revision"]  # Preserve pre-migration retry fingerprints.
        fingerprint = digest({"project_id": project_id, "run_id": run_id, **observed})
        with self.runs._transaction(write=True) as conn:
            run = self.runs._row(conn, project_id, run_id)
            previous = conn.execute(
                "SELECT * FROM runtime_code_acceptances WHERE project_id=? AND task_id=? AND operation_key=?",
                (project_id, run["task_id"], intent.operation_key),
            ).fetchone()
            if previous:
                if previous["request_sha256"] != fingerprint:
                    raise RunConflict(
                        "Owner operation already identifies another code acceptance"
                    )
                return json.loads(previous["receipt_json"])
            state = self._state(conn, project_id, run_id)
            if not state["eligible"] or state["acceptance"]:
                raise RunConflict(
                    "Code acceptance blocked: "
                    + ",".join(item["code"] for item in state["blockers"])
                )
            candidate = state["candidate"]
            if intent.check_policy_revision != state["project_check_policy"]["revision"]:
                raise RunConflict("Check policy changed or was not observed before acceptance")
            if (
                candidate["attempt_id"],
                candidate["context_version"],
                state["subject_sha256"],
                state["review_sha256"],
            ) != (
                intent.attempt_id,
                intent.context_version,
                intent.subject_sha256,
                intent.review_sha256,
            ):
                raise RunConflict(
                    "Candidate, context or review changed after the owner observation"
                )
            if state["requires_acknowledgement"] and not intent.acknowledge_limits:
                raise RunConflict(
                    "Explicit acknowledgement of displayed check/review limits is required"
                )
            now = self.runs.clock()
            receipt = {
                "project_id": project_id,
                "task_id": run["task_id"],
                "run_id": run_id,
                **observed,
                "check_policy": state["project_check_policy"],
                "review_run_id": state["review"]["run_id"],
                "actor_source": "paired_owner_action",
                "accepted_at": now,
                "task_accepted": True,
                "publication_performed": False,
                "acceptance_scope": "captured_code_version",
                "candidate": candidate,
                "check_limitations": state["checks"]["limitations"],
                "review_limitations": state["review"]["proposal"]["limitations"],
                "review_issues": state["review_issues"],
            }
            conn.execute(
                """INSERT INTO runtime_code_acceptances(project_id,task_id,run_id,attempt_id,review_run_id,context_version,operation_key,request_sha256,subject_sha256,review_sha256,receipt_json,accepted_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    project_id,
                    run["task_id"],
                    run_id,
                    intent.attempt_id,
                    receipt["review_run_id"],
                    intent.context_version,
                    intent.operation_key,
                    fingerprint,
                    intent.subject_sha256,
                    intent.review_sha256,
                    canonical(receipt),
                    now,
                ),
            )
            for identifier, attempt in (
                (run_id, intent.attempt_id),
                (receipt["review_run_id"], state["review"]["attempt_id"]),
            ):
                updated = conn.execute(
                    "UPDATE runtime_runs SET status='accepted',updated_at=? WHERE project_id=? AND id=? AND current_attempt_id=? AND status='needs_review'",
                    (now, project_id, identifier, attempt),
                )
                if updated.rowcount != 1:
                    raise RunConflict(
                        "Original author or reviewer no longer owns this decision"
                    )
            updated = conn.execute(
                "UPDATE tasks SET status='done',completed_at=datetime(?,'unixepoch') WHERE project_id=? AND id=? AND status NOT IN ('done','failed','cancelled')",
                (now, project_id, run["task_id"]),
            )
            if updated.rowcount != 1:
                raise RunConflict("Task no longer accepts this code result")
            conn.execute(
                "UPDATE tool_grants SET revoked_at=COALESCE(revoked_at,?) WHERE project_id=? AND task_id=?",
                (now, project_id, run["task_id"]),
            )
            self.runs._event(conn, project_id, run["task_id"], "code.accepted", receipt)
            return receipt
