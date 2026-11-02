"""Explicit host check recipes disclosed before development; no inferred test commands or model-selected execution policy."""

import json
from dataclasses import asdict

from backend.runtime.check_contracts import CheckSpec
from backend.runtime.development_instructions import DEVELOPMENT_INSTRUCTIONS


def parse_development_checks(value):
    """Copy a bounded JSON check list into immutable validated recipes; reject unknown fields and environments without fallback."""
    if not isinstance(value, list) or len(value) > 8:
        raise ValueError(
            "development_checks must be an explicit list of at most eight recipes"
        )
    checks = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("argv"), list):
            raise TypeError("Each development check requires an explicit argv list")
        spec = CheckSpec(**{**item, "argv": tuple(item["argv"])})
        if spec.environment_id not in ("system", "runtime-python"):
            raise ValueError(
                "Development check environment is unavailable; no fallback"
            )
        checks.append(spec)
    return tuple(checks)


def development_instructions(checks):
    """Bind the exact host plan into the original frozen developer instructions without representing commands as successful tests."""
    plan = json.dumps(
        [{"sha256": check.sha256, **asdict(check)} for check in checks],
        ensure_ascii=False,
        sort_keys=True,
    )
    return DEVELOPMENT_INSTRUCTIONS + (
        "\nAfter your completed turn, the host captures the exact candidate and runs these recipes in independent copies. "
        "Do not claim their results in advance. Commands are not test suites.\n" + plan
        if checks
        else "\nNo host checks are configured. State that limitation; never imply that tests passed."
    )
