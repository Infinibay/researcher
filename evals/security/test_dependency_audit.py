"""Check repository-only audit tooling without adding script imports to installed backend tests."""

import json
import sys

import pytest

from scripts.audit_dependencies import run_auditor


@pytest.mark.parametrize(
    ("report", "exit_code", "name", "expected"),
    [
        ({"dependencies": []}, 1, "python", "error"),
        ({"dependencies": [{"name": "unlisted", "skip_reason": "Not in registry"}]},
         0, "python", "incomplete"),
        ({"dependencies": [{"name": "affected", "vulns": [{"id": "CVE-example"}]}]},
         1, "python", "vulnerable"),
        ({"error": {"message": "Registry unavailable"}}, 1, "frontend", "error"),
    ],
)
def test_external_auditor_failures_remain_visible(tmp_path, report, exit_code, name, expected):
    """An actual failed/skipped auditor process must retain its evidence and block a clean result."""
    command = [sys.executable, "-c", "import sys; print(sys.argv[1]); sys.exit(int(sys.argv[2]))",
               json.dumps(report), str(exit_code)]
    receipt = run_auditor(command, tmp_path, name, cwd=tmp_path)
    assert receipt["status"] == expected
    assert receipt["exit_code"] == exit_code
    assert json.loads((tmp_path / f"{name}.stdout").read_text()) == report


def test_missing_auditor_is_an_error(tmp_path):
    """A missing local tool cannot silently produce a clean dependency audit."""
    receipt = run_auditor([str(tmp_path / "missing-auditor")], tmp_path, "python", cwd=tmp_path)
    assert receipt == {"status": "error", "error": "FileNotFoundError"}
