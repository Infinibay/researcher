"""Neutral owner decision policy preserves check failures and explicit absence without I/O."""

import pytest


@pytest.mark.parametrize(
    "checks,blocked,limited",
    [
        ([], False, True),
        ([{"state": "finished", "result": {"status": "passed"}}], False, False),
        ([{"state": "finished", "result": {"status": "no_tests"}}], False, True),
        ([{"state": "finished", "result": {"status": "skipped"}}], False, True),
        ([{"state": "preparing", "result": None}], True, False),
        ([{"state": "finished", "result": {"status": "failed"}}], True, False),
        (
            [{"state": "finished", "result": {"status": "infrastructure_error"}}],
            True,
            False,
        ),
        ([{"state": "finished", "result": {"status": "invalidated"}}], True, False),
        ([{"state": "finished", "result": {"status": "future_status"}}], True, False),
    ],
)
def test_check_policy_never_converts_missing_or_failed_tests_to_success(
    checks, blocked, limited
):
    """An owner can acknowledge finite missing evidence, but cannot use that acknowledgement to waive failed or unfinished work."""
    from backend.runtime.code_acceptance_policy import assess_code_checks

    result = assess_code_checks(checks)
    assert bool(result["blockers"]) is blocked
    assert bool(result["limitations"]) is limited


@pytest.mark.parametrize(
    "field,value",
    [
        ("context_version", True),
        ("subject_sha256", "abc"),
        ("acknowledge_limits", 1),
        ("operation_key", "bad key"),
    ],
)
def test_code_owner_intent_requires_explicit_neutral_identity(field, value):
    """Request validation rejects coercions and incomplete observations before any database or model work."""
    from backend.runtime.code_acceptance_policy import CodeAcceptanceIntent

    args = {
        "operation_key": "accept-1",
        "attempt_id": "author-attempt",
        "context_version": 2,
        "subject_sha256": "a" * 64,
        "review_sha256": "b" * 64,
        "acknowledge_limits": True,
        "note": None,
    }
    args[field] = value
    with pytest.raises(ValueError):
        CodeAcceptanceIntent(**args)


@pytest.mark.parametrize(
    "state,verdict,blocking",
    [
        ("confirmed", "needs_revision", True),
        ("reconciling", "needs_revision", False),
        ("confirmed", "inconclusive", False),
    ],
)
def test_prior_review_policy_distinguishes_confirmed_objection_from_unconfirmed_judgment(
    state, verdict, blocking
):
    """All prior concerns remain attributed; only a confirmed rejection is treated as a blocking verdict."""
    from backend.runtime.code_acceptance_policy import prior_code_review_issues

    issues = prior_code_review_issues(
        [
            {
                "run_id": "old-review",
                "state": state,
                "verdict": verdict,
                "rationale": "Observed or unresolved concern.",
            }
        ]
    )
    assert len(issues) == 1 and issues[0]["blocking"] is blocking
    assert issues[0]["state"] == state and issues[0]["verdict"] == verdict
