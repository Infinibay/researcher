"""CI gate helpers for INFINIBAY flows — test output parsing and recording."""

from __future__ import annotations

import logging
import re
import sqlite3

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


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
