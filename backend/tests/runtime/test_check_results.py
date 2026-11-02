"""Versioned CI evidence must distinguish actual tests, skipped work, infrastructure errors and another candidate."""

from dataclasses import replace

import pytest


def subject():
    """Return one exact synthetic candidate identity without claiming an execution took place."""
    from backend.runtime.check_contracts import CandidateSubject

    return CandidateSubject(
        101,
        1001,
        11,
        "run-a",
        "attempt-a",
        1,
        1,
        "a" * 40,
        "b" * 40,
        "c" * 40,
        "d" * 64,
    )


def observation(
    spec,
    *,
    candidate=None,
    exit_code=0,
    closed=True,
    complete=True,
    workspace_matches=True,
    xml=None,
):
    """Build typed evidence at the host-result boundary for pure outcome classification tests."""
    from backend.runtime.check_contracts import CheckObservation

    return CheckObservation(
        candidate or subject(),
        spec.sha256,
        exit_code,
        closed,
        complete,
        workspace_matches,
        xml,
    )


def test_pytest_success_requires_collected_non_skipped_tests():
    """A real case element and clean terminal receipt support a passed pytest result."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_results import evaluate_check

    spec = CheckSpec(("/usr/bin/python3", "-m", "pytest"), "pytest")
    result = evaluate_check(
        subject(),
        spec,
        observation(spec, xml=b'<testsuite><testcase name="works"/></testsuite>'),
    )
    assert (
        result.status == "passed"
        and result.tests == 1
        and result.failures == 0
        and result.skipped == 0
    )
    assert result.subject == subject() and result.spec_sha256 == spec.sha256


@pytest.mark.parametrize(
    "code,xml,status",
    [
        (5, b"<testsuite/>", "no_tests"),
        (0, b"<testsuite/>", "no_tests"),
        (0, b"<testsuite><testcase><skipped/></testcase></testsuite>", "skipped"),
        (1, b"<testsuite><testcase><failure/></testcase></testsuite>", "failed"),
        (1, b"<testsuite><testcase><error/></testcase></testsuite>", "failed"),
        (2, b"<testsuite/>", "infrastructure_error"),
        (3, b"<testsuite/>", "infrastructure_error"),
        (4, b"<testsuite/>", "infrastructure_error"),
        (6, b'<testsuite><testcase name="works"/></testsuite>', "failed"),
        (0, None, "infrastructure_error"),
        (0, b"<testsuite>", "infrastructure_error"),
        (
            0,
            b"<testsuite><testcase><failure/></testcase></testsuite>",
            "infrastructure_error",
        ),
    ],
)
def test_pytest_outcomes_do_not_promote_absence_or_invalid_evidence(code, xml, status):
    """Empty, skipped, failed, interrupted and malformed reports have distinct non-success outcomes."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_results import evaluate_check

    spec = CheckSpec(("/usr/bin/python3", "-m", "pytest"), "pytest")
    assert (
        evaluate_check(
            subject(), spec, observation(spec, exit_code=code, xml=xml)
        ).status
        == status
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("repository_id", 22),
        ("base_sha", "e" * 40),
        ("head_sha", "e" * 40),
        ("context_version", 2),
        ("attempt_id", "attempt-b"),
    ],
)
def test_another_candidate_or_context_invalidates_the_observation(field, value):
    """Check evidence for A cannot approve B, even when a command returns zero."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_results import evaluate_check

    spec = CheckSpec(("/usr/bin/true",), "command")
    other = replace(subject(), **{field: value})
    assert (
        evaluate_check(subject(), spec, observation(spec, candidate=other)).status
        == "invalidated"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"exit_code": None},
        {"execution_closed": False},
        {"output_complete": False},
        {"workspace_matches": False},
        {"spec_sha256": "e" * 64},
    ],
)
def test_incomplete_or_changed_execution_evidence_never_passes(change):
    """Unknown exit, live descendants, lost output, modified code and a different recipe cannot produce success."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_results import evaluate_check

    spec = CheckSpec(("/usr/bin/true",), "command")
    result = evaluate_check(subject(), spec, replace(observation(spec), **change))
    assert result.status in ("invalidated", "infrastructure_error")


def test_generic_success_is_a_command_check_without_invented_test_counts():
    """A formatter/build command can pass without being presented as tests that ran."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_results import evaluate_check

    spec = CheckSpec(("/usr/bin/true",), "command")
    result = evaluate_check(subject(), spec, observation(spec))
    assert result.status == "passed" and result.tests is None


def test_recipe_fingerprint_is_immutable_and_changes_with_environment():
    """The same command in a different host-selected toolchain needs its own evidence."""
    from backend.runtime.check_contracts import CheckSpec

    spec = CheckSpec(("/usr/bin/true",), "command", environment_id="system-v1")
    assert spec.sha256 == replace(spec).sha256
    assert spec.sha256 != replace(spec, environment_id="system-v2").sha256
    with pytest.raises(ValueError):
        CheckSpec(("relative-command",), "command")


def test_unsafe_or_oversized_xml_cannot_be_interpreted_as_passed():
    """The host parser rejects entity expansion and report truncation instead of trusting report attributes."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.check_results import evaluate_check

    spec = CheckSpec(("/usr/bin/python3", "-m", "pytest"), "pytest")
    for report in (
        b'<!DOCTYPE a [<!ENTITY x "expanded">]><testsuite><testcase name="&x;"/></testsuite>',
        b"x" * (1024**2 + 1),
    ):
        assert (
            evaluate_check(subject(), spec, observation(spec, xml=report)).status
            == "infrastructure_error"
        )
