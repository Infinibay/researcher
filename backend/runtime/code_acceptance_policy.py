"""Neutral owner acceptance intent and check policy, independent of persistence and HTTP.

Acceptance records a human decision about one captured code version. Missing
tests remain missing evidence; none of these values authorize publication.
"""

import re
from dataclasses import dataclass

from backend.runtime.contracts import command_key, identity, text


@dataclass(frozen=True)
class CodeAcceptanceIntent:
    """One explicit owner observation, retained unchanged after an uncertain response."""

    operation_key: str
    attempt_id: str
    context_version: int
    subject_sha256: str
    review_sha256: str
    acknowledge_limits: bool
    note: str | None = None
    check_policy_revision: int | None = None

    def __post_init__(self):
        """Reject coercion, incomplete fingerprints and implicit acknowledgement before effects."""
        command_key(self.operation_key)
        text(self.attempt_id, "Author attempt", 128)
        identity(self.context_version)
        for value in (self.subject_sha256, self.review_sha256):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(
                    "Code acceptance requires complete observed fingerprints"
                )
        if type(self.acknowledge_limits) is not bool:
            raise ValueError("Code acceptance requires explicit owner acknowledgement")
        if self.note is not None:
            text(self.note, "Owner note", 4000)
        if self.check_policy_revision is not None:
            if type(self.check_policy_revision) is not int or not 1 <= self.check_policy_revision <= 9007199254740991:
                raise ValueError("Code acceptance requires an observed check policy revision")


def assess_code_checks(checks, *, policy_mode=None):
    """Apply explicit project test requirements; absent mode retains historical receipt semantics without inventing test execution."""
    blockers, limitations = [], []
    if not checks:
        limitations.append(
            {
                "code": "checks_absent",
                "message": "No hay comprobaciones registradas del candidato.",
            }
        )
    for check in checks:
        status = (check.get("result") or {}).get("status")
        if check.get("state") != "finished" or status not in {
            "passed",
            "no_tests",
            "skipped",
        }:
            blockers.append(
                {
                    "code": "check_not_passed",
                    "check_id": check.get("id"),
                    "state": check.get("state"),
                    "outcome": status,
                    "message": "Hay una comprobación fallida, pendiente o sin resultado verificable.",
                }
            )
        elif status in {"no_tests", "skipped"}:
            limitations.append(
                {
                    "code": "check_" + status,
                    "check_id": check.get("id"),
                    "message": "No se ejecutaron pruebas."
                    if status == "no_tests"
                    else "Se omitieron pruebas o comprobaciones.",
                }
            )
        elif policy_mode and (check.get("result") or {}).get("skipped", 0):
            limitations.append({"code": "check_partially_skipped", "check_id": check.get("id"),
                                "message": "Se ejecutaron pruebas, pero algunas se omitieron."})
    if policy_mode and checks and not blockers and not limitations and not any(
        type((c.get("result") or {}).get("tests")) is int
        and c["result"]["tests"] > (c["result"].get("skipped") or 0)
        for c in checks
    ):
        limitations.append({"code": "test_execution_unproven", "message": "Los comandos terminaron, pero no acreditan pruebas ejecutadas."})
    if policy_mode == "require_tests" and limitations:
        blockers.append({"code": "tests_required", "message": "Este proyecto exige pruebas ejecutadas y satisfactorias, sin omisiones."})
    return {"blockers": blockers, "limitations": limitations}


def prior_code_review_issues(history):
    """Preserve earlier concerns about the same exact subject; a newer positive verdict cannot erase a confirmed objection."""
    issues = []
    for item in history:
        if item["verdict"] not in ("needs_revision", "inconclusive"):
            continue
        blocking = item["state"] == "confirmed" and item["verdict"] == "needs_revision"
        issues.append(
            {
                **item,
                "blocking": blocking,
                "message": "Una revisión confirmada del mismo candidato pide cambios. Resuelve esa objeción antes de aceptar."
                if blocking
                else "Hay una revisión anterior con límites u objeciones; su estado de confirmación y su explicación se conservan.",
            }
        )
    return issues
