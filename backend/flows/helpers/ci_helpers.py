"""CI gate helpers for INFINIBAY flows — test output parsing, execution, and recording."""

from __future__ import annotations

import logging
import re
import shlex
import sqlite3
import subprocess

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def execute_ci_command(repo_path: str, test_cmd: str) -> dict:
    """Run a test command via subprocess and return a structured CI outcome.

    Bypasses pod/sandbox — the CI gate is a flow-level check, not an agent action.
    """
    try:
        parts = shlex.split(test_cmd)
        result = subprocess.run(
            parts,
            shell=False,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=repo_path,
        )
        return _handle_ci_result({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return _handle_ci_result({"error": "CI command timed out after 600s"})
    except FileNotFoundError:
        return _handle_ci_result({"error": f"CI command not found: {test_cmd}"})
    except Exception as e:
        return _handle_ci_result({"error": f"CI execution failed: {e}"})


def _handle_ci_result(result: dict) -> dict:
    """Translate raw subprocess result into structured CI outcome."""
    if "error" in result:
        return {
            "ci_passed": False,
            "ci_output": result["error"],
            "test_count": 0,
            "test_pass": 0,
            "exit_code": 1,
        }

    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    exit_code = result.get("exit_code", 1)
    output = stdout + "\n" + stderr
    test_count, test_pass = parse_ci_output(output)

    return {
        # Exit 0 = tests passed, exit 5 = no tests collected (not a failure)
        "ci_passed": exit_code in (0, 5),
        "ci_output": output[:3000],
        "test_count": test_count,
        "test_pass": test_pass,
        "exit_code": exit_code,
    }


def parse_ci_output(output: str) -> tuple[int, int]:
    """Parse pytest summary output and return (test_count, test_pass).

    Scans for pytest's summary line (e.g. "5 passed, 1 failed in 12.3s")
    and extracts passed/failed counts.  Returns (0, 0) if the pattern is
    not found (e.g. collection error or non-pytest output).
    """
    passed = 0
    failed = 0

    m_passed = re.search(r"(\d+) passed", output)
    if m_passed:
        passed = int(m_passed.group(1))

    m_failed = re.search(r"(\d+) failed", output)
    if m_failed:
        failed = int(m_failed.group(1))

    m_error = re.search(r"(\d+) error", output)
    if m_error:
        failed += int(m_error.group(1))

    test_count = passed + failed
    return test_count, passed


def record_ci_result(
    project_id: int,
    cycle: int,
    test_output: str,
    test_pass: int,
    test_count: int,
    branch_name: str,
) -> None:
    """Insert a CI gate result row into the code_quality table.

    Uses ``branch_name`` as ``file_path`` (a sentinel for a whole-suite CI run).
    Never raises — wraps in try/except and logs a warning on failure so that
    a recording failure does not block the flow.
    """
    try:
        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO code_quality
                       (project_id, cycle, file_path, test_count, test_pass,
                        test_output, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (project_id, cycle, branch_name, test_count, test_pass,
                 test_output[:5000]),
            )
            conn.commit()

        execute_with_retry(_insert)
    except Exception:
        logger.warning(
            "record_ci_result: failed for project %d branch %s",
            project_id, branch_name,
            exc_info=True,
        )
