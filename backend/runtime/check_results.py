"""Classify version-bound check evidence without treating no tests, skipped work or lost receipts as success.

This policy does not start a process, collect a report, persist a check or approve
publication. The execution adapter must supply actual owned observations and
revalidate the candidate workspace; passing booleans from model text is not proof.
"""

from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from backend.runtime.check_contracts import (
    CandidateSubject,
    CheckObservation,
    CheckOutcome,
    CheckSpec,
)

MAX_REPORT_BYTES = 1024**2


def evaluate_check(
    subject: CandidateSubject, spec: CheckSpec, observed: CheckObservation
) -> CheckOutcome:
    """Require exact scope/recipe, closed effects and complete bounded report evidence before classifying a check."""

    def outcome(
        status, reason, exit_code, tests=None, failures=None, errors=None, skipped=None
    ):
        """Retain the observed scope even when rejecting evidence for another requested candidate."""
        return CheckOutcome(
            observed.subject,
            observed.spec_sha256,
            status,
            reason,
            exit_code,
            tests,
            failures,
            errors,
            skipped,
        )

    if observed.subject != subject or observed.spec_sha256 != spec.sha256:
        return outcome(
            "invalidated", "candidate_or_recipe_mismatch", observed.exit_code
        )
    if not observed.execution_closed or observed.exit_code is None:
        return outcome(
            "infrastructure_error", "termination_unconfirmed", observed.exit_code
        )
    if not observed.workspace_matches:
        return outcome("invalidated", "candidate_workspace_changed", observed.exit_code)
    if not observed.output_complete:
        return outcome("infrastructure_error", "output_incomplete", observed.exit_code)
    if spec.framework == "command":
        return outcome(
            "passed" if observed.exit_code == 0 else "failed",
            "command_completed",
            observed.exit_code,
        )
    if observed.exit_code not in (0, 1, 5, 6):
        return outcome(
            "infrastructure_error",
            "pytest_interrupted_or_unavailable",
            observed.exit_code,
        )
    report = observed.junit_xml
    if report is None or not report or len(report) > MAX_REPORT_BYTES:
        return outcome(
            "infrastructure_error", "report_absent_or_oversized", observed.exit_code
        )
    try:
        root = fromstring(report)
        if root.tag not in ("testsuites", "testsuite"):
            raise ValueError("Unknown test report root")
        tests = failures = errors = skipped = 0
        for case in root.iter("testcase"):
            failed = case.find("failure") is not None
            error = case.find("error") is not None
            skip = case.find("skipped") is not None
            if sum((failed, error, skip)) > 1:
                raise ValueError("Conflicting test case outcomes")
            tests += 1
            failures += failed
            errors += error
            skipped += skip
    except (ParseError, DefusedXmlException, ValueError, RecursionError):
        return outcome("infrastructure_error", "report_invalid", observed.exit_code)
    if observed.exit_code == 6:
        return outcome(
            "failed",
            "pytest_warnings_limit",
            observed.exit_code,
            tests,
            failures,
            errors,
            skipped,
        )
    if observed.exit_code == 5:
        status = "no_tests" if tests == 0 else "infrastructure_error"
    elif observed.exit_code == 1:
        status = "failed" if failures + errors > 0 else "infrastructure_error"
    elif failures + errors:
        status = "infrastructure_error"
    elif tests == 0:
        status = "no_tests"
    elif skipped == tests:
        status = "skipped"
    else:
        status = "passed"
    return outcome(
        status,
        "pytest_report_observed",
        observed.exit_code,
        tests,
        failures,
        errors,
        skipped,
    )
